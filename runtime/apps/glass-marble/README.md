# Aqua Link

Two-screen ESP-NOW water-and-goldfish demo for Japanese NW-X1060 and ESP-Mosaico.
The Mosaico BMI270 drives a calm, volume-conserving surface; both displays render
their own physical viewport. See [the guide](../../../docs/apps/GLASS_MARBLE.md)
for geometry calibration, builds, protocol and qualification limits.

Build the native application from the project root under Linux/WSL:

```sh
.venv/bin/python tools/test_glass_marble.py
.venv/bin/python runtime/apps/glass-marble/build.py
```

The ESP32-S31 firmware project is in `mosaico/`. It requires ESP-IDF 6.2 and
the pinned official BSP. Neither builder installs, flashes or contacts devices.
