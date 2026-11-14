"""Build an offline full-radio research image. No loader/device/updater access.

Exact stock identity, reserved pool/scatter edits and all three hooks are atomic
build inputs. Preserves every other original loaded byte and helper identity.
"""

from dataclasses import replace
from pathlib import Path
import argparse, hashlib, json, struct, subprocess
from elftools.elf.elffile import ELFFile
from marvell_firmware import Record, parse, serialize
from prepare_espnow_radio_candidate import (
    ROOT,
    STOCK_SHA,
    HELPER_SHA,
    RESERVED_START,
    RESERVED_END,
    BSS_START,
    BSS_END,
    memory,
)

STOCK_WORD_CASE_START = 0x88D6
STOCK_WORD_ENTRY = 0x88D8
STOCK_WORD_CASE_END = 0x88F2

SOURCES = [
    "runtime/platform/espnow/" + n
    for n in (
        "radio_packet.c",
        "radio_full_rx.c",
        "radio_full_tx.c",
        "radio_tx_completion.c",
        "radio_completion_hook.S",
        "radio_word_command.c",
        "radio_command_hook.S",
    )
]
HEADERS = [
    "runtime/platform/espnow/" + n
    for n in (
        "radio_packet.h",
        "radio_full_rx.h",
        "radio_full_tx.h",
        "radio_tx_completion.h",
        "xnow_bulk_protocol.h",
    )
]
FRAME_SOURCES = [
    "runtime/platform/espnow/" + n
    for n in (
        "radio_packet.c",
        "radio_full_rx.c",
        "radio_frame_tx.c",
        "radio_tx_completion.c",
        "radio_completion_hook.S",
        "radio_frame_command.c",
        "radio_command_hook.S",
    )
]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def literal_jump(address, target):
    if not target & 1:
        raise ValueError("Thumb target missing state bit")
    # Two distinct alignments; both replace exactly ten original bytes.
    if address & 3 == 2:
        return struct.pack("<HHHI", 0x4B01, 0x4718, 0x46C0, target)
    if address & 3 == 0:
        return struct.pack("<HHIH", 0x4B00, 0x4718, target, 0x46C0)
    raise ValueError("unaligned Thumb patch")


def construct(stock, payload):
    if digest(stock) != STOCK_SHA:
        raise ValueError("unqualified original radio image")
    records = parse(stock)
    if serialize(records) != stock:
        raise ValueError("original container roundtrip")
    original = memory(records)
    reservation = bytearray(1900)
    covered = set()
    sections = []
    word_hook = None
    with Path(payload).open("rb") as f:
        elf = ELFFile(f)
        if elf["e_machine"] != "EM_ARM" or not elf.little_endian:
            raise ValueError("payload architecture")
        table = elf.get_section_by_name(".symtab")
        if table is None:
            raise ValueError("missing symbols")
        symbols = {s.name: s["st_value"] for s in table.iter_symbols() if s.name}
        for section in elf.iter_sections():
            if not section["sh_flags"] & 2 or not section["sh_size"]:
                continue
            a = section["sh_addr"]
            end = a + section["sh_size"]
            if section.name == ".word_hook":
                if a != STOCK_WORD_ENTRY or end > STOCK_WORD_CASE_END or section["sh_type"] == "SHT_NOBITS":
                    raise ValueError("command0x86 case boundary exceeded")
                word_hook = section.data()
                continue
            if (
                section.name not in (".text", ".state")
                or section["sh_type"] == "SHT_NOBITS"
                or not RESERVED_START <= a < end <= RESERVED_END
            ):
                raise ValueError("unexpected/out-of-range payload section")
            addresses = set(range(a, end))
            if covered & addresses:
                raise ValueError("overlapping payload sections")
            covered |= addresses
            reservation[a - RESERVED_START : end - RESERVED_START] = section.data()
            sections.append((section.name, a, end))
    if {n for n, _, _ in sections} != {".text", ".state"}:
        raise ValueError("missing code/state section")
    text = next((a, b) for n, a, b in sections if n == ".text")
    state_section = next((a, b) for n, a, b in sections if n == ".state")
    entries = {
        name: symbols[name]
        for name in (
            "xnow_radio_full_receive",
            "xnow_radio_word_command_entry",
            "xnow_radio_completion_entry",
        )
    }
    bulk_marker = symbols.get("xnow_radio_bulk_commands")
    bulk_value = None
    frame_marker = symbols.get("xnow_radio_frame_commands")
    if frame_marker is not None:
        if bulk_marker is not None:
            raise ValueError("ambiguous transfer profiles")
        bulk_marker = frame_marker
    if bulk_marker is not None:
        if bulk_marker & 3 or not text[0] <= bulk_marker < bulk_marker + 4 <= text[1]:
            raise ValueError("invalid immutable bulk-command feature marker")
        bulk_value = struct.unpack_from(
            "<I", reservation, bulk_marker - RESERVED_START
        )[0]
        allowed = (
            (0x314D5246,) if frame_marker is not None else (0x314B4C42, 0x324B4C42)
        )
        if bulk_value not in allowed:
            raise ValueError("unknown transfer-command feature marker")
    for name, entry in entries.items():
        if word_hook is not None and name == "xnow_radio_word_command_entry":
            if entry != STOCK_WORD_ENTRY + 1:
                raise ValueError("invalid in-place command entry")
            continue
        if not entry & 1 or not text[0] <= entry & ~1 < text[1]:
            raise ValueError("invalid code entry")
    controls = {}
    control_bytes = set()
    descriptions = [
        ("xnow_full_tx", 40, 0x3254584E),
        ("xnow_full_rx", 64, 0x3252584E),
        ("xnow_tx_completion", 24, 0),
    ]
    diagnostics = ("xnow_rx_seen", "xnow_rx_eligible")
    if any(name in symbols for name in diagnostics):
        if not all(name in symbols for name in diagnostics):
            raise ValueError("incomplete RX diagnostics")
        descriptions.extend((name, 4, 0) for name in diagnostics)
    for name, n, magic in descriptions:
        a = symbols[name]
        addresses = set(range(a, a + n))
        if (
            a & 3
            or not state_section[0] <= a < a + n <= state_section[1]
            or control_bytes & addresses
        ):
            raise ValueError("control overlap/range")
        initial = bytes(reservation[a - RESERVED_START : a + n - RESERVED_START])
        if initial != struct.pack("<I", magic) + bytes(n - 4):
            raise ValueError("control not clean/disabled")
        control_bytes |= addresses
        controls[name] = {"address": a, "bytes": n}
    if control_bytes != set(range(*state_section)):
        raise ValueError("unexpected extra state")
    patches = [
        (
            0x163EE,
            bytes.fromhex("0422"),
            bytes.fromhex("0322"),
            "large pool count4 ->3",
        ),
        (
            0xC00026B0,
            struct.pack("<I", 0xA315),
            struct.pack("<I", entries["xnow_radio_full_receive"]),
            "Action RX veneer",
        ),
        (
            0x88D6,
            bytes.fromhex("207863781b0218430128"),
            literal_jump(0x88D6, entries["xnow_radio_word_command_entry"]),
            "host-command0x86 STORE/LOAD hook",
        ),
        (
            0xD51C,
            bytes.fromhex("80b5f3f720ef80bd"),
            struct.pack("<HHI", 0x4B00, 0x4718, entries["xnow_radio_completion_entry"]),
            "common management release observer including pre-MAC rejection",
        ),
        (
            0x17328,
            struct.pack("<II", BSS_START, BSS_END - BSS_START),
            struct.pack("<II", BSS_START, RESERVED_START - BSS_START),
            "BSS zero range before reservation",
        ),
        (
            0x17338,
            struct.pack("<II", 0x17340, 0),
            struct.pack("<II", RESERVED_END, BSS_END - RESERVED_END),
            "BSS zero range after reservation",
        ),
    ]
    if word_hook is not None:
        # The former STORE/LOAD case ends immediately before case88f2. Its
        # replacement returns to the same stock dispatcher, never the old tail.
        before = bytes.fromhex("207863781b021843012803d1a06861680860fee460680068a060fae4")
        after = bytes.fromhex("c046") + word_hook
        after += bytes.fromhex("c046") * ((len(before) - len(after)) // 2)
        patches[2] = (STOCK_WORD_CASE_START, before, after, "replace complete command0x86 case within original bounds")
    changes = {}
    plan = []
    for a, before, after, purpose in patches:
        if (
            len(before) != len(after)
            or bytes(original[a + i] for i in range(len(before))) != before
        ):
            raise ValueError("patch precondition: " + purpose)
        for i, v in enumerate(after):
            if a + i in changes:
                raise ValueError("patch overlap")
            changes[a + i] = v
        plan.append(
            {
                "address": a,
                "before": before.hex(),
                "after": after.hex(),
                "purpose": purpose,
            }
        )
    for i, r in enumerate(records):
        if r.command == 1:
            records[i] = replace(
                r,
                data=bytes(changes.get(r.address + j, v) for j, v in enumerate(r.data)),
            )
    records[-1:-1] = [
        Record(1, RESERVED_START + i, bytes(reservation[i : i + 508]))
        for i in range(0, 1900, 508)
    ]
    candidate = serialize(records)
    loaded = memory(parse(candidate))
    if serialize(parse(candidate)) != candidate:
        raise ValueError("candidate roundtrip")
    if any(loaded[a] != changes.get(a, v) for a, v in original.items()):
        raise ValueError("unplanned original byte change")
    added = set(loaded) - set(original)
    if added != set(range(RESERVED_START, RESERVED_END)):
        raise ValueError("unexpected loaded addition")
    old_zero = set(range(BSS_START, BSS_END))
    new_zero = set(range(BSS_START, RESERVED_START)) | set(range(RESERVED_END, BSS_END))
    if old_zero - new_zero != added or new_zero - old_zero:
        raise ValueError("incorrect BSS exclusion")
    # These aligned immutable spans can be checked after mutable controls change.
    immutable = []
    for a, n in (
        (RESERVED_START, state_section[0] - RESERVED_START),
        (state_section[1], RESERVED_END - state_section[1]),
        (0x163EC, 8),
        (0xC00026B0, 4),
        (0x88D4, 32 if word_hook is not None else 12),
        (0xD51C, 8),
    ):
        if not n:
            continue
        data = bytes(loaded[a + i] for i in range(n))
        immutable.append({"address": a, "bytes": n, "sha256": digest(data)})
    used = max(b for _, _, b in sections) - RESERVED_START
    manifest = {
        "profile": "full-radio-experimental-v2",
        "radio_only": True,
        "original_sha256": STOCK_SHA,
        "candidate_sha256": digest(candidate),
        "payload_elf_sha256": digest(Path(payload).read_bytes()),
        "original_bytes": len(stock),
        "candidate_bytes": len(candidate),
        "reserved_start": RESERVED_START,
        "reserved_end": RESERVED_END,
        "reserved_bytes": 1900,
        "section_bytes": sum(b - a for _, a, b in sections),
        "occupied_span_bytes": used,
        "tail_free_bytes": 1900 - used,
        "entries": entries,
        "controls": controls,
        "patches": plan,
        "immutable_segments": immutable,
        "startup_only_segments": [
            {
                "address": 0x17328,
                "bytes": 24,
                "sha256": digest(bytes(loaded[0x17328 + i] for i in range(24))),
                "runtime_reclaimed": True,
            }
        ],
        "pool_blocks_after": 3,
        "rx_initially_disabled": True,
        "all_other_loaded_bytes_unchanged": True,
        "all_other_bss_zeroing_preserved": True,
        "crc_roundtrip_passed": True,
        "hardware_tested": False,
        "driver_reload_qualified": False,
        "device_written": False,
    }
    if word_hook is not None:
        manifest["in_place_command"] = {
            "start": STOCK_WORD_CASE_START,
            "end": STOCK_WORD_CASE_END,
            "entry": entries["xnow_radio_word_command_entry"],
            "payload_bytes": len(word_hook),
        }
    if bulk_value == 0x314D5246:
        manifest["frame_transactions"] = {
            "marker_address": bulk_marker,
            "marker_value": bulk_value,
            "command": 0x86,
            "submit_action": 2,
            "completion_action": 3,
            "submit_header_bytes": 36,
            "fragment_bytes": 1464,
            "completion_bytes": 44,
            "request_boundary_bytes": 1500,
            "plain_body_max": 1520,
            "protected_body_max": 1536,
            "command_entry_in_stock_case": word_hook is not None,
            "read_vector": {
                "sentinel": 0xC000D5A8,
                "address_mask": 0xFFFF0003,
                "address_region": 0xC0000000,
                "max_entries": 185,
                "entry_bytes": 8,
                "read_only": True,
            },
        }
    elif bulk_marker is not None:
        manifest["bulk_word_commands"] = {
            "marker_address": bulk_marker,
            "marker_value": bulk_value,
            "command": 0x86,
            "get_action": 0x100,
            "set_action": 0x101,
            "max_words": 371,
            "header_bytes": 16,
            "packet_only": True,
            "error_response_bytes": 16,
            "request_boundary_bytes": 1500,
        }
        if bulk_value == 0x324B4C42:
            manifest["bulk_word_commands"]["read_vector"] = {
                "sentinel": 0xC000D5A8,
                "address_mask": 0xFFFF0003,
                "address_region": 0xC0000000,
                "max_entries": 185,
                "entry_bytes": 8,
                "read_only": True,
            }
    return candidate, manifest


def build(
    stock_path,
    helper_path,
    output,
    rx_diagnostics=False,
    bulk_commands=False,
    read_vector=False,
    frame_transactions=False,
):
    if read_vector and not bulk_commands:
        raise ValueError("Read vector requires bulk commands")
    if frame_transactions and (bulk_commands or read_vector):
        raise ValueError("Select frame transactions instead of the bulk profile")
    output = Path(output).resolve()
    if not output.is_relative_to((ROOT / "work").resolve()) or output.exists():
        raise ValueError("output must be a new project work directory")
    stock = Path(stock_path).read_bytes()
    helper = Path(helper_path).read_bytes()
    if digest(stock) != STOCK_SHA or digest(helper) != HELPER_SHA:
        raise ValueError("original input identity")
    output.mkdir(parents=True)
    link = output / "radio.ld"
    link.write_text(
        'ENTRY(xnow_radio_full_receive)\nSECTIONS { . = 0xc000a190; .text : { *(.text*) *(.rodata*) } .state : { *(.state) } ASSERT(.<=0xc000a8fc,"reserved block exceeded") '
        + '.word_hook 0x88d8 : { *(.word_hook) } '
        + '/DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.note*) } }'
    )
    payload = output / "radio.elf"
    flags = [
        "-std=c99",
        "-Os",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-march=armv5te",
        "-mthumb",
        "-mfloat-abi=soft",
        "-ffreestanding",
        "-fno-builtin",
        "-fno-pie",
        "-fno-stack-protector",
        "-nostdlib",
        "-static",
        "-DXNOW_RADIO_INPLACE_WORD_COMMAND",
        "-Wl,--build-id=none",
        "-Wl,-T," + str(link),
    ]
    if rx_diagnostics:
        flags += ["-DXNOW_RADIO_RX_DIAGNOSTICS"]
    if bulk_commands:
        flags += ["-DXNOW_RADIO_BULK_COMMANDS", "-flto", "-fno-inline"]
    if read_vector:
        flags += ["-DXNOW_RADIO_READ_VECTOR"]
    sources = FRAME_SOURCES if frame_transactions else SOURCES
    headers = HEADERS + (
        ["runtime/platform/espnow/xnow_frame_protocol.h"] if frame_transactions else []
    )
    if frame_transactions:
        flags += [
            "-DXNOW_RADIO_BULK_COMMANDS",
            "-DXNOW_RADIO_READ_VECTOR",
            "-DXNOW_RADIO_FRAME_TRANSACTIONS",
            "-flto",
        ]
    subprocess.run(
        ["arm-linux-gnueabi-gcc", *flags, *sources, "-o", str(payload)],
        cwd=ROOT,
        check=True,
    )
    image, manifest = construct(stock, payload)
    manifest["helper_sha256"] = HELPER_SHA
    manifest["compiler"] = subprocess.check_output(
        ["arm-linux-gnueabi-gcc", "--version"], text=True
    ).splitlines()[0]
    manifest["source_hashes"] = {
        p: digest((ROOT / p).read_bytes())
        for p in [
            *sources,
            *headers,
            "tools/build_espnow_full_radio.py",
            "tools/marvell_firmware.py",
        ]
    }
    manifest["rx_diagnostics"] = rx_diagnostics
    if rx_diagnostics:
        with payload.open("rb") as stream:
            symbols = {
                s.name: s["st_value"]
                for s in ELFFile(stream).get_section_by_name(".symtab").iter_symbols()
            }
        manifest["rx_diagnostic_counters"] = {
            name: dict(address=symbols[name], bytes=4)
            for name in ("xnow_rx_seen", "xnow_rx_eligible")
        }
    for name, data in (
        ("candidate/sd8686.bin", image),
        ("candidate/helper_sd.bin", helper),
        ("stock/sd8686.bin", stock),
        ("stock/helper_sd.bin", helper),
    ):
        target = output / name
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(data)
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (output / "README.txt").write_text(
        "OFFLINE FULL-RADIO RESEARCH CANDIDATE. NOT HARDWARE QUALIFIED.\nNo loader/automatic installation supplied. Never use Sony system updater for these files.\nOriginal helper and rollback radio retained. No kernel/module/partition edits.\n"
    )
    return manifest


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--original", type=Path, required=True)
    p.add_argument("--helper", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--rx-diagnostics", action="store_true")
    p.add_argument("--bulk-commands", action="store_true")
    p.add_argument("--read-vector", action="store_true")
    p.add_argument("--frame-transactions", action="store_true")
    a = p.parse_args()
    print(
        json.dumps(
            build(
                a.original,
                a.helper,
                a.output,
                a.rx_diagnostics,
                a.bulk_commands,
                a.read_vector,
                a.frame_transactions,
            ),
            indent=2,
        )
    )
