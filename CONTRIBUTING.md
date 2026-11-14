# Contributing

Start with [architecture](docs/ARCHITECTURE.md) and the
[SDK quick start](docs/sdk/README.md). App developers should not need to learn
Sony's internal addresses, firmware packer or radio loader to build an app.
Native platform work additionally requires [platform knowledge](docs/KNOWLEDGE.md)
and the corresponding service guide.

## Keep changes local

- An app owns its behavior, UI, version, metadata and resources under one
  `runtime/apps/<id>/` directory. Shared adapters belong in the platform/native/
  storage layers; do not copy them into each app.
- Define which module owns a resource and which result confirms its release.
  A caller must not infer cleanup from a timeout, process exit or UI return.
- Put protocol interpretation, system capability management and presentation
  in separate modules. Builders connect implementations; they do not decide
  runtime policy.
- Use an interface when it contains a real ownership/behavior contract. Avoid
  forwarding layers that merely spread one operation across more files.
- Keep changes to Sony-specific bindings separate from application policy.
  Preserve original ABI/image checks and never export raw stock pointers.

## Code conventions

Device code is C/C++ and necessary ARM assembly. Python is PC tooling only.
Use the repository `.clang-format` for edited C/C++ (clang-format 18). Do not
reformat vendored sources or unrelated files as part of a behavioral fix.

Use named states, commands, field offsets and bounds. A verified register or
stock address may be a literal in a private adapter, with its role and input
identity documented there; it must not become application business logic.
Keep one operation/branch per line and name results by their domain. Preserve
the difference between admitted, completed, unavailable and uncertain.

Keep buffers bounded and make ownership visible. Large fixed contexts belong
in static/heap or caller-owned storage, not small ARM/ESP task stacks. Queues
must define their full/drop behavior. Reuse the stock libc/time/stat/signal
adapters; modern headers do not guarantee compatibility with Sony's old ABI.

## Verification

Use [offline regression checks](docs/REGRESSION.md). A fix should exercise the
failing caller path as well as its lower helper. Prefer a test that fails before
the fix and checks the externally relevant contract. A passing shallow fixture
must not be described as complete integration or hardware qualification.
Select the smallest adequate check set using the [engineering workflow](docs/WORKFLOW.md).
Inspect expensive runs with `--plan`; full regression includes unit modules and
does not need another complete unittest discovery afterward.

Update includes, builders, package input lists and fixtures together when moving
source. Old reports retain their original hashes. Keep immutable evidence under
ignored `work/`/`.tmp/`; never rewrite an old report to match new source.

## Versions and documentation

Project, SDK and application versions are independent. Use `VERSION` at each
respective scope. Changed installed bytes require a new application version;
an unchanged public API need not receive an unrelated SDK version bump. Never
publish a replacement payload under an already used version.

Documentation describes current behavior, ownership, API use and known limits.
Do not prepend a new development-session account to a guide. Update the relevant
contract and keep hardware acceptance in the single status table. Preserve
technical findings needed for native work; keep superseded reasoning and private
diagnostics out of active docs. Documentation is English; product translations
and upstream licenses retain their own languages.

Flashing, live account/device activity and publishing are separate explicit
operations. Ordinary checks must not perform them. Preserve Sony binaries,
rollback packages, user keys/counters and existing failure evidence.
