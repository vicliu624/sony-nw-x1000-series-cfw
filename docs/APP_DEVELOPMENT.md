# Developing a native external application

For a generated starter, host preview and a small C facade, begin with the
[SDK quick start](sdk/README.md). The original lower-level path remains available.

The [application specification](APP_SPEC.md) defines local metadata, artwork,
build ownership and installed package formats.

Put the application's source in `runtime/apps/<id>/`. Keep the deployed ID stable;
moving source does not rename `HOMEBREW/apps/<id>` or change save locations.
Each app directory has a short README pointing to its guide and builder.

Use a normal C main through the existing original-libc startup. Do not reference
absolute SpiderApp function addresses from an independent app. The Sony menu hook
is a distinct version-specific integration layer, not a general application SDK.

For graphics, use the shared hb_devices open/present/flush/next_touch/close adapter
and the verified screen layout. Poll cancellation; release resources on all normal,
error and stop paths. Returning from main hands control to the launcher, not a
proof of complete Sony UI restoration. Do not open framebuffer concurrently with
another foreground app just because its device node is accessible.

Start with runtime/apps/graphics-demo, hello or device-info. Use safe help/version/
selftest entries to verify ABI without device access. Hardware actions must not
run accidentally from such entries. Device code never executes a Python script.

Statically include appropriate shared C adapters and dynamically link original
Sony libc. Reuse the fixed wire layouts and narrow ioctl/time bindings; modern
host headers are not proof of original ABI compatibility.

Apps, resources, ROMs, saves and account state belong on verified user storage.
No system or NVP write is an installation prerequisite. Check mount identity,
symlinks, free space, USB ownership and transactional publication. Keep cleanup
bounded and report restoration failures rather than claiming a successful exit.

Validate business logic with useful host/ARM fixtures, then actual package discovery
and safe CLI execution. Simulated hardware results remain distinct from physical
qualification. Do not include test transports or credentials in delivery apps.

The store and launcher use runtime/store and runtime/native shared infrastructure.
Their public reuse does not imply a stable ABI across other Sony model families.
