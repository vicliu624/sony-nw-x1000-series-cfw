# Diagnostics and minimal applications

Source is separated under runtime/apps/diagnostics, graphics-demo, key-check and
hello. Shared PCM ownership probes live with diagnostics; shared adapters remain
under runtime/native and runtime/platform.

Graphics Demo demonstrates ordinary C main, original-libc startup, a private
framebuffer surface, touch handling and return to the launcher. Hello is a console
ABI example. Key Check reports the verified event interface; names/numbers are
Sony-specific. Diagnostics are tools, not a promise of safe arbitrary hardware
experimentation.

Use their builders' safe CLI entries and offline fixtures before any hardware
entry. An inspection option must not implicitly enable an ioctl, power change or
device write. A successful stdout/selftest result does not qualify Sony Home,
USB/sleep handoff, sound or recovery. Do not run an app's graphics entry while
WiFi Terminal owns the display.
