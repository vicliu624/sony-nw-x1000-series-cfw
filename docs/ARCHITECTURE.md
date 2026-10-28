# Architecture and layout

Sony Home selects one homebrew application. sysmgrd launches the proxy-class entry
through appproxy. The launcher discovers external packages, releases its device
resources and starts one native child. Apps are not separately registered on Home.

```text
runtime/apps/       Separate app directories, including reader/dictionary cores
runtime/native/     Launcher, process, display/touch and syscall adapters
runtime/platform/   Shared device services, including PCM
runtime/store/      Shared package/network/libc bridges
scripts/            Firmware/resource analysis libraries
tools/              PC builders, offline checks and research utilities
tests/              PC tests
sources/            Provenance and machine-readable research metadata
third_party/        Vendored sources and retained licenses
translations/       Multilingual product text
assets/             Artwork/data inputs
config/             Persistent package-composition configuration
docs/               Curated English documentation
.tmp/               Ignored scratch, old notes and maintenance backups
work/               Ignored reusable inputs and generated evidence
dist/               Ignored local delivery packages
firmware/           Ignored original/proprietary inputs
```

runtime/store intentionally remains shared: several apps use its startup, stat,
DNS/TLS and package code. runtime/native likewise avoids duplicate device adapters.
The gbc and tamagotchi-id directories own entry points, build recipes, versions
and artwork; runtime/apps/emulators contains their shared emulator shell/adapters. Localization bridge/cache code stays with the language application.

Package validation does not grant hardware ownership. A valid ELF, user-storage
path or QEMU result does not establish Sony lifecycle/USB coordination. Installing
an app and replacing a firmware image have different authorization boundaries.

Historical evidence is immutable. A refactor requires new relevant checks; it
does not erase or silently rewrite the old source/artifact hashes. Active builds
must not depend on .tmp/history documents.
