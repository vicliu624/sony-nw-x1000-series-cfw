# Launcher, store and shared runtime

The launcher is implemented in runtime/native. Store frontend, package transactions,
resolver/TLS and original-libc bridges remain in runtime/store because other apps
share them. They are not loose files mixed with the per-app directory.

The launcher dynamically discovers HOMEBREW/apps/<id>/app.ini, verifies package
identity/integrity/ELF and owns child lifecycle and display release/reacquisition.
Default entry and Sony return remain tied to the original manager/proxy protocol.

The store contains local install and network-controller implementations, with
explicit publisher/trust configuration. A setup/review composition may display
configuration requirements rather than a usable public catalog. Do not claim
deployment merely because a local TLS fixture installed a package.

Builders include build_libc_frontend.py, build_store_app.py and
build_network_store_app.py. Prefer original-libc device/process and librt monotonic
clock profiles where supported; retain explicit legacy profiles for research.

Installation uses verified user storage, staged writes, hashes and rollback/error
states. Packages do not each receive a Sony Home entry. Do not bypass TLS checks,
trust synthetic CAs, infer USB exclusivity from a masked zero state, or use a new
chroot/container/security architecture as a prerequisite for ordinary homebrew.
