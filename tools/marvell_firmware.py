"""Strict PC-only parser for the inspected SD8686 download container.

Command/address/length are LE32. Header and payload CRCs are BE32,
MSB-first polynomial 0x04c11db7, initial zero, no final xor. No device access.
Other Marvell families/formats are not implicitly supported.
"""
from dataclasses import dataclass
import struct


def crc32(data: bytes) -> int:
    value = 0
    for byte in data:
        value ^= byte << 24
        for _ in range(8):
            value = ((value << 1) ^ (0x04C11DB7 if value & 0x80000000 else 0)) & 0xffffffff
    return value


@dataclass(frozen=True)
class Record:
    command: int
    address: int
    data: bytes


def parse(blob: bytes) -> list[Record]:
    records = []
    offset = 0
    while offset < len(blob):
        if len(blob) - offset < 16:
            raise ValueError('truncated header')
        header = blob[offset:offset + 12]
        command, address, size = struct.unpack('<III', header)
        if crc32(header) != struct.unpack_from('>I', blob, offset + 12)[0]:
            raise ValueError(f'header CRC at {offset:#x}')
        offset += 16
        if command == 4:
            if address or size or offset != len(blob):
                raise ValueError('invalid terminator or trailing data')
            records.append(Record(command, address, b''))
            return records
        if command != 1 or size < 4 or size > 512 or size > len(blob) - offset:
            raise ValueError('unsupported command or invalid payload length')
        payload = blob[offset:offset + size - 4]
        if address + len(payload) > 0x100000000:
            raise ValueError('address wrap')
        if crc32(payload) != struct.unpack_from('>I', blob, offset + size - 4)[0]:
            raise ValueError(f'payload CRC at {offset:#x}')
        records.append(Record(command, address, payload))
        offset += size
    raise ValueError('missing terminator')


def serialize(records: list[Record]) -> bytes:
    out = bytearray()
    for i, record in enumerate(records):
        if record.command == 4:
            if i != len(records) - 1 or record.address or record.data:
                raise ValueError('invalid terminator')
            size = 0
        elif record.command == 1 and len(record.data) <= 508:
            size = len(record.data) + 4
        else:
            raise ValueError('unsupported record')
        if not 0 <= record.address <= 0xffffffff or record.address + len(record.data) > 0x100000000:
            raise ValueError('invalid address')
        header = struct.pack('<III', record.command, record.address, size)
        out.extend(header + struct.pack('>I', crc32(header)))
        if record.command == 1:
            out.extend(record.data + struct.pack('>I', crc32(record.data)))
    result = bytes(out)
    parse(result)
    return result
