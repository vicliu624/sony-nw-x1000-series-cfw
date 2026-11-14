# BearSSL Curve25519 build input

The native code-free pairing profile reuses BearSSL 0.6, already prepared by
SDK setup under work/external-tls-probe/bearssl-0.6. Its pinned archive SHA-256 is
6705bba1714961b41a728dfc5debbe348d2966c117649392f8c8139efc83ff14.
The build verifies ec_c25519_m15.c, ccopy.c and their headers against that archive.
Only compiled curve/constant-time-copy code is linked into the player library.
The ESP32 frontend uses the framework's existing Mbed TLS Curve25519 backend.
Both use RFC7748 wire byte order; the tests include its published vectors.

Upstream: https://bearssl.org/ . The unmodified MIT license is retained here and
included with private update materials. No proprietary Sony files are included.