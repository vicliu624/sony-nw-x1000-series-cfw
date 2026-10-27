# WiFi Terminal: user and research guide

This is an **on-demand remote shell**, not an ordinary entertainment app. It
provides the development computer with the player's actual Linux permissions.
The physical test configuration ran as root. Commands can modify the device;
the application's zero-system-install policy does not sandbox arbitrary commands.

## Installation and storage

Device source: runtime/apps/terminal. PC client: tools/terminal_client.py.
Build from the project root in WSL:

```sh
.venv/bin/python tools/build_terminal.py
```

Outputs are in work/terminal-review. The personal experimental ZIP contains:

```text
HOMEBREW/apps/terminal/
  app
  app.ini
  files.sha256
  server-cert.der
  server-key.der
computer/
  terminal_client.py
  server-cert.sha256
```

Only the device directory belongs on visible player storage. Python is required
on the computer, never on the player. The installed development build was about
101KiB in total; inspect its manifest/report for exact size. No kernel, driver,
Sony program, NVP or system-partition file is installed by this app.

The build creates a local EC identity and preserves it across rebuilds. The ZIP
contains that installation's private key: **do not publish the personal package**.
Do not commit work/private-identity, connection codes or device snapshots.
An identity change requires distributing the matching PC certificate fingerprint.

Public CI/market packages deliberately omit that identity. Use
prepare_terminal_identity.py from terminal-computer.zip to create personal files
under HOMEBREW/data/terminal and a matching PC fingerprint before first use. The
app displays PAIRING SETUP REQUIRED until configured. The private data directory
survives replacement of the public application; legacy personal packages remain
supported. See [release instructions](../RELEASES.md).

The native app validates the original user-storage mount before reading its
certificate/key. Session buffers and code are RAM-only. It automatically saves
no command history, account state or logs. HOME/TMPDIR initially point to the
verified user-storage app directory; explicit commands can still write elsewhere.

## Connect interactively

1. Connect the player through Sony's normal Wi-Fi UI; connect the computer to a
   mutually reachable network. This release does not provide hotspot selection.
2. Safely eject/disconnect USB storage before using the app.
3. Open WiFi Terminal in the homebrew launcher. Read the displayed IPv4 address,
   TCP port2323, EUID/EGID and two lines totaling32 hexadecimal code characters.
4. From the project root, run:

   ```powershell
   py -3 tools/terminal_client.py <player-ip> --pin work/terminal-review/server-cert.sha256
   ```

   Alternatively use the packaged computer directory, where the pin file is next
   to the client and is selected by default.
5. Enter the current code at the private prompt. It changes when the app restarts.

The client verifies the exact SHA-256 certificate pin **before** transmitting the
code. Transport is TLS1.2 ECDHE-ECDSA/AES128-GCM. This is a dedicated protocol,
not SSH: `ssh root@<ip>` will not connect to it.

The session uses a real PTY and /bin/sh. `cd`, terminal resizing and Ctrl-C work
through that PTY. Ctrl-] disconnects locally; `exit` ends the shell. Select
STOP AND RETURN on the player to close the service and return to the launcher.
The server prints actual UID/EUID/GID, not assumed privileges.

## Computer-side automation

Save the current code in a private ignored computer file, for example
`.tmp/private/terminal-code.txt`. Do not put it in command arguments or source.

```powershell
py -3 tools/terminal_client.py <player-ip> --pin work/terminal-review/server-cert.sha256 --code-file .tmp/private/terminal-code.txt --command "id; uname -a; cat /proc/mounts"
```

Command output goes to stdout; connection errors go to stderr. The process returns
the remote command's exit status. `--timeout 60` changes the default30-second
deadline. Text command size is bounded and output is limited to64MiB. Commands
run in a subshell so an explicit exit can be captured.

This mode still uses a PTY: stdout/stderr are merged and line endings may be CRLF.
Encode binary data as text before transfer. Do not assume printf exists: the
player's small BusyBox ash lacks it, so client framing uses echo. Native C printf
is unrelated to availability of a shell printf command.

Read-only research helpers are explicit PC commands, not automatic app startup
actions. Review their command lists before use. Keep raw reports in ignored work
or .tmp; do not publish usernames, network identity, account traces or private keys.

## Firewall and failure behavior

Stock INPUT policy drops new TCP sessions while allowing ping. The app temporarily
inserts **one TCP2323 ACCEPT rule** using stock /sbin/iptables, and removes its
matching rule during normal cleanup. It does not disable the firewall or change
its policy/NVP/config files. Outbound QQ HTTPS does not need this rule.

FIREWALL OPEN FAILED means the service could not establish this prerequisite.
FIREWALL RESTORE FAILED means cleanup did not confirm rule removal. Forced kills
or crashes cannot guarantee cleanup; the listener closes but a rule may remain
until reset/restart. Full Home/USB/sleep cleanup is not hardware-qualified.

One client is serviced at a time. Authentication expires after20 seconds; failed
attempts have cooldown, with30 seconds after repeated failures. Authenticated idle
sessions expire after30 minutes without terminal data. Frames and queues are bounded.
Normal disconnect/exit signals the foreground group and shell, escalates if needed
and reaps its child. Programs deliberately detached from the session are outside
that process-group cleanup guarantee.

Troubleshoot by layer: address/route, TCP, TLS/pin, code, then shell/command. Ping
success is not TCP success. A pin mismatch is a refusal, not a request to turn off
verification. DISCONNECTED after a completed one-shot command can be normal.

## Established and outstanding validation

Real hardware: UI startup, pinned TLS, actual root shell, multiple connections,
read-only queries, output and explicit remote exit status7. PC/ARM fixtures also
cover wrong pin/code, fragmented frames, output, resizing, Ctrl-C, invalid frames
and cleanup. Windows entry checks are distinct from full console-key qualification.

Still validate long-duration stability, forced termination, firewall restoration,
USB/sleep integration and any new hardware action. Root access does not establish
early-boot control or a recovery console when Linux cannot boot. Do not use this
app as evidence that flashing or arbitrary raw writes are safe.
