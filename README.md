# Sony NW-X1000 Series Firmware Research

Native homebrew, localization and firmware research for the **Japanese Sony
NW-X1050 and NW-X1060**. The physical test unit is an NW-X1060 on the Japanese
1.11 platform. International NWZ-X images are comparison inputs, not interchangeable
installation packages. Device additions use C/C++ and necessary ARM assembly;
Python runs only on the development computer.

## Documentation

- [Current status and validation limits](docs/STATUS.md)
- [Platform knowledge and research handoff](docs/KNOWLEDGE.md)
- [Physical hardware observations](docs/HARDWARE.md)
- [Build environment and commands](docs/BUILD.md)
- [CI, release packages and the application repository](docs/RELEASES.md)
- [Architecture and layout](docs/ARCHITECTURE.md)
- [Application development](docs/APP_DEVELOPMENT.md)
- [Packages and storage rules](docs/APP_PACKAGES.md)
- [Localization and sleep incident](docs/LOCALIZATION.md)
- [System footprint](docs/SYSTEM_FOOTPRINT.md)
- [Third-party notices](THIRD_PARTY.md)

## Applications

| Application | Source | Guide |
| --- | --- | --- |
| WiFi Terminal | runtime/apps/terminal | [Terminal](docs/apps/TERMINAL.md) |
| Pocket FM | runtime/apps/fm-radio | [FM](docs/apps/FM_RADIO.md) |
| QQ Music | runtime/apps/qqmusic | [QQ Music](docs/apps/QQ_MUSIC.md) |
| Device Info | runtime/apps/device-info | [Device Info](docs/apps/DEVICE_INFO.md) |
| EBook | runtime/apps/ebook | [EBook](docs/apps/EBOOK.md) |
| Dictionary | runtime/apps/dictionary | [Dictionary](docs/apps/DICTIONARY.md) |
| GBC / Tamagotchi iD | runtime/apps/emulators | [Emulators](docs/apps/EMULATORS.md) |
| Language | runtime/apps/language | [Localization](docs/LOCALIZATION.md) |
| Diagnostics / graphics / keys / hello | Separate runtime/apps folders | [Examples](docs/apps/DIAGNOSTICS.md) |
| Launcher / store | runtime/native, runtime/store | [Store/runtime](docs/apps/STORE.md) |

One Sony Home entry opens the external launcher. Apps, resources and app data live
on visible user storage; app installation should not reflash the system.

## Evidence and local files

The terminal has executed authenticated commands on the physical player. This
does not qualify all apps, RF reception, sound, USB/sleep handoff or recovery.
Candidate 11 had an intermittent sleep incident; candidate 12's cache change has
not established physical sleep stability. QQ Music's complete real-account
download/import/playback chain and FM extended-band audio remain unverified.

The repository is hosted at https://github.com/vicliu624/sony-nw-x1000-series-cfw.
The Git boundary excludes `.tmp/`, `work/`, `firmware/`,
`dist/` and `bundles/`. Do not force-add their contents.

Old experiment logs/design previews are preserved in `.tmp/history/docs/`, and
superseded source snapshots in `.tmp/history/archive/`. Their hashes describe
their original state. Reusable build inputs and rollback evidence remain in
`work/` and `firmware/`; they were not deleted as disposable files.

Keep maintainable English documentation in `docs/`. Multilingual translations,
dictionary content and reader samples are product data. Never commit proprietary
Sony files, private keys, connection codes, account material, music, ROMs or saves.
Retain upstream notices and provenance.
