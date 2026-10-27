# Emulator applications

runtime/apps/emulators contains the shared native app/storage/platform layer,
GBC core adapter/scheduler and Tamagotchi iD adapter. tools/build_emulator_apps.py
produces separate gbc and tamagotchi-id packages. Shared code is intentional;
their manifests and app state remain distinct.

Keep ROMs and save files on user storage and out of Git/packages. The platform
preserves the existing Sony stop/ownership boundary. Audio scheduling uses shared
runtime/platform services and the FM mixer adapter where explicitly linked; this
does not imply simultaneous foreground music and emulation are qualified.

Tamagotchi uses its vendored core under the retained notices; GBC uses the pinned
gnuboy source. Source/CLI fixtures do not prove frame timing, sound, arbitrary ROM
compatibility, physical key behavior or long-session stability. Do not import
A910-specific hardware assumptions from compile-time reference names.
