# Paired Codex companion

Pet 0.4.0 provides a native C++ computer bridge and a native C player client. No new
firmware, Python interpreter on the player, Codex API key or model request is
required. This is a status/notification connection, not a remote shell or a way
to approve Codex actions.

## What it follows

The computer watches one explicitly selected local Codex rollout. It reads the
file without modifying Codex configuration, authentication, databases or thread
history. Start, completion, interruption and structured user-question events
drive the companion. It exports a short title, status, question and final-answer
excerpt, not reasoning records, arbitrary tool output or other conversations.

The current adapter was checked against the installed Codex CLI
0.165.0-alpha.1.2 / desktop rollout schema. Local rollout records are not a stable
public integration API. Unknown records are ignored; unsupported/unavailable
sources report unknown rather than inventing progress. Waiting recognizes
request_user_input and request_user_input_async; not every OS dialog, UAC prompt
or Codex approval surface has an equivalent supported rollout event.

The official [App Server guide](https://learn.chatgpt.com/docs/app-server) describes
thread/turn notifications and runtime status. On the development machine the
desktop's running server did not expose a usable shared control endpoint. The
bridge therefore uses the read-only local adapter, not a second server claiming
to observe the desktop's live threads, and never resumes a thread to subscribe.

## First pairing

Initial pairing is deliberately explicit: create an identity on the computer and
copy its small player pairing file over USB. Subsequent status updates use the
LAN. After this identity bootstrap, the player automatically discovers the paired computer on its IPv4 LAN. Touchscreen-PIN pairing is not implemented.

1. Build the native bridge, or use the computer executable in the local package.
2. Run the preparation tool on the computer. `--list` prints recent local thread
   IDs/titles only on that computer:

   ```powershell
   python tools/prepare_pet_pairing.py --list
   python tools/prepare_pet_pairing.py --thread <selected-thread-uuid> --title "My task" --output work/pet-pairing/my-computer
   ```

   The one-time preparation tool uses computer-side Python and OpenSSL. Normal
   operation runs pet-bridge.exe, which is C++. Outputs must use a fresh project
   work directory; an existing personal identity is never silently overwritten.
3. Copy the generated PLAYER/HOMEBREW/data/pet/link.pair to that exact visible
   storage location. Install the whole matching HOMEBREW/apps/pet app folder.
   Safely eject USB before running the app.
4. Start computer/Start Codex Pet.cmd. The computer and player must be mutually
   reachable, normally through the same trusted Wi-Fi. If Windows asks for
   network access, use the private network you intend to use. The tool does not
   create firewall rules, enable a Codex listener or install a background service.
5. Open BSOD Pet. The menu's top-left Codex label opens connection controls.
   Tap the character to view the selected task/question/result. The read button
   returns to the room and acknowledges the reminder locally. Questions must be
   answered on the computer; reading one on the player does not approve anything.

The generated computer folder contains private key/token material; keep it
private. Certificate/key paths in computer.json are relative to that file, while
the selected rollout path is absolute. The computer folder can move together.
Changing only the computer IPv4 address does not require a new player pairing file. Changing the selected rollout/title in computer.json and restarting the bridge also preserves the identity. A different computer identity requires explicit new pairing. Stop the old bridge before starting a new
configuration on the same address/port.

## Connection and interaction loop

- A valid pairing auto-connects on app entry. Without pairing, the local pet still
  works and the connection page explains setup.
- Working uses the laptop animation. Completion, supported questions and errors
  have different reactions. Touch opens details; long Chinese excerpts paginate.
- Repeated snapshots do not reset the page the user is reading. A new revision or
  selected thread resets the detail view. An already completed task at the first
  synchronization is treated as historical rather than replaying a new alert.
- Treat/play reactions temporarily take priority over the linked animation.
  Rest mutes movement; tapping a resting character wakes it.
- Disconnect closes the client for this app session; reconnect reloads pairing.
  Forget requires confirmation, removes only link.pair, and preserves pet saves.
  It does not remotely erase the computer's identity. Regenerate pairing to
  rotate that identity/token. A failed forget/reconnect is visible and retryable.
- Closing the app stops its sockets and releases its buffers. No player-side
  network service, growing event log or system-directory persistence is created.

## Protocol and limits

The computer endpoint defaults to TCP4242 on all local IPv4 interfaces when using the new discovery configuration. The player initiates the connection, so it needs no inbound firewall
exception. Existing Sony Wi-Fi/route setup is used without changing drivers.

TLS1.2 verifies the exact paired certificate hash and its public key before
sending the 256-bit pairing token. This private pin is the trust anchor, not the
device's old RTC or a public CA. Ordinary HTTPS validation elsewhere is unchanged.
The status endpoint accepts no shell, prompt, file-path or approval operation.

The client sends `PET1`, a 32-byte token and an unpredictable 64-bit nonce. A reply
has a two-byte big-endian length and a bounded PTSNAP01 record. Integers and string
lengths are explicitly encoded; no native C layout is transmitted. The response
must match the current nonce, limits and UTF-8 rules. Maximum frame size is 2048
bytes; title is at most 96 bytes, question/result excerpts at most 768 bytes each.

Connections are reused for two-second polls, up to thirty requests before a fresh
connection. Network operations are nonblocking on the player with bounded pump
iterations, a five-second active deadline and exponential offline retry delays from two to thirty seconds. A snapshot
is current for at most ten seconds after receipt. A working rollout with no file
updates for ninety seconds becomes unknown, avoiding an indefinitely busy pet
after a stopped computer agent. Waiting/completed history is retained as such.

link.pair is PETPAIR1 + NUL-terminated IPv4[16] + port(u16be) + certificate length
(u16be) + token[32] + computer name[64] + certificate DER. Header size is124 bytes,
maximum file4220 bytes. It is read only through the verified pet user-data
directory with file type/device/link/size checks. The token is never printed.

## Build and verification

```powershell
cmake -S runtime/apps/pet/computer -B work/pet-bridge/windows -G "Visual Studio 17 2022" -A x64
cmake --build work/pet-bridge/windows --config Release
ctest --test-dir work/pet-bridge/windows -C Release --output-on-failure
python tools/test_pet_bridge_tls.py
```

The CMake build uses the existing verified BearSSL0.6 source under work. JSON
parsing is nlohmann/json3.12.0, computer-side only; MIT notices are retained.
Windows binaries use the static MSVC runtime. Player code uses the original Sony
libc plus the existing checked TLS/ABI adapters, never a modern time64 alias.

Linux/WSL checks include test_pet_link_native.py: the actual ARM client under
ARM926 QEMU and Sony libc communicates with the native C++ service, including a
persistent-session update and wrong-identity rejection. Its optional
`--real-rollout <selected-path>` mode reads an actual local session without
writing it. That full chain delivered the current desktop session's working
state. Native Windows TLS tests separately cover bad-token/bad-pin rejection.
Controller fixtures cover paired and unpaired paths, details/read handling and
stop cleanup. None of these are physical-player qualification.

Still requiring NW-X1060 tests: actual Wi-Fi reachability, touch responsiveness,
HOME/USB/suspend handoff, long-session stability and power/performance. No updater
or firmware image is produced for this feature.

## Authenticated address discovery (0.4.0)

Existing PETPAIR1 files remain valid. Their IPv4 field is now only a cached hint;
new pairing preparation does not require --address and may store0.0.0.0 there.
Use a matching computer bridge with discovery=true and listen=0.0.0.0 so a DHCP
address change does not prevent the service from starting or receiving requests.
The normal discovery port is UDP4243; TCP may use another configured port, which
is returned in the authenticated discovery response.

The player sends PTFIND01, a fresh8-byte nonce and HMAC-SHA256 using its pairing
key. Only a matching bridge replies. PTHERE01 includes that nonce, the TCP port,
the certificate SHA256 and another MAC. Responses must match the nonce, pairing
key, certificate identity and current connected subnet. The player then performs
the existing exact-pinned TLS handshake before authenticating the status request.
No machine name, task, transcript or raw pairing key is broadcast.

The UDP responder is a bounded worker in the existing computer process. It does
not install a service, create firewall rules or change Codex settings. One bridge
owns the discovery port; a second instance on the same port reports a bind error.
On Windows the application needs private-network UDP access as well as TCP.

Stock X1000 INPUT policy may drop unicast responses to broadcast requests.
Discovery therefore first tries broadcast and the cached address, then issues
normal outbound unicast discovery requests within the directly connected subnet.
Their reply tuple matches the existing ESTABLISHED conntrack rule. No player
firewall policy, rule, NVP, interface or raw-packet socket is changed. Each window
prioritizes the local /24 and rotates a bounded additional /24 for larger networks,
with at most sixteen small probes per pump and a capped /16 search area. It is
intended for the same IPv4 LAN, not routed VLAN/Internet discovery. Larger subnets
may take longer; AP client isolation can prevent communication entirely.

Discovery stops once the paired peer is found; only the address/port in RAM is
updated. The on-storage pairing file is not rewritten. Offline retries back off,
while manual reconnect starts immediately. Existing fixed-address0.3 bridges
remain a cached-address fallback, but both sides must be updated for discovery.
The ARM926/original-libc test deliberately invalidates the stored address and
port, discovers the peer, then moves the bridge to a different IP/port while the
same client stays running. Reconnection succeeds without modifying link.pair.
MAC, nonce, identity and malformed-packet tests also pass. Real-player discovery
and Windows private-firewall behavior still require a device test.
