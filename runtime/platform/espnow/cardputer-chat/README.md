# Cardputer ESP-NOW Chat

Local experimental peer for the original M5Stack Cardputer, not ADV. It uses
the physical keyboard and a240x135 landscape display, with no software keyboard.
The UI shares the X1060 app's dark palette, left/right message bubbles, compact
composer and channel badge. Text wraps by pixel width. A small outgoing marker
is muted while pending, teal after application ACK and amber if unconfirmed.
Peer discovery is not proof of successful application delivery.

ENTER sends a draft; Fn+P requests discovery again when no message is in flight.
The footer shows the96-byte limit. The most recent messages occupy a clipped
viewport; eight messages and the draft remain in RAM only. Long drafts scroll
horizontally. There is currently no history scrolling or Unicode keyboard/font.
Transport carries UTF-8 bytes, but this renderer uses the shared ASCII font.

chat_ui.h renders into one fixed64800-byte RGB565 buffer, then the main loop
pushes one complete image only when dirty. No frame buffer is allocated per
message or key event. Source font licensing is recorded in runtime/native/ui_font.h
and third_party/qqmusic-stb/Noto-OFL.txt. PC tools/preview_cardputer_chat.py runs
the same renderer with synthetic messages and memory-boundary checks, producing
previews under work/espnow-cardputer-ui. Those pictures are not RF test evidence.

Build with PlatformIO from this folder or use its -d option. Outputs stay under
project work/. Building does not flash COM17. Preserve the known-running raw
laboratory peer before a supervised chat-firmware test. Version0.1.0-dev.2 has
been installed on COM17 and passed live serial smoke checks for submission,
timeout, input bounds and continued responsiveness. It also restarted into the
waiting state. The raw peer and full-flash backup are preserved. Physical LCD
appearance, physical keyboard input and complete native X1060 app-to-app
communication remain unqualified. Live evidence is under ignored
work/espnow-cardputer-ui/live-chat-dev2-20261028-01/.
