# Engineering workflow

Use the smallest change and verification scope that can establish the requested
behavior. Preserve Sony's hardware and lifecycle mechanisms. This policy governs
development work; it does not authorize device access or package publication.

## Before editing

State the observable failure or requested behavior, acceptance criteria and
affected component. Inspect its current callers, builders and test adapters.
For ABI, structure or protocol changes, include every consumer before compiling.
Keep one focused reproducer. Separate new findings from the current acceptance
criteria instead of continually expanding a nearly completed patch.
Do not create one-off executable helpers, even in ignored storage. A supported
workflow uses maintained purpose-based entry points with explicit inputs; version
numbers identify delivery artifacts, not another implementation of the workflow.
Recover retired candidate recipes from Git history when investigating an old
artifact. Keep its original inputs, resulting package and failure evidence as
data. Use the explicit-input builders and packer in [BUILD.md](BUILD.md) for a
new review.

## Build and verification inputs

The player host builds its selected language composition once per invocation.
The builder validates the stock image and patch spans, and records the resulting
ELF and Settings overlay with their input identities. Its library receipt records
the compiler command, the project headers selected by GCC and the linked Sony
libraries. A changed tracked input invalidates reuse. Independent tests use the
same builder, then execute the refusal cases and ARM replay. Packaging consumes
reviewed outputs through their receipts. Build the localized root once and use
its archive directly for managed layout, capacity and QEMU checks. Use the same
reviewed wireless image for radio replay, the owner build and the system overlay.
For a managed Remote build, run the [shared Wi-Fi build sequence](BUILD.md#shared-wi-fi-candidate)
through the artifact checks. Use that host receipt for both replay and layout
assembly. See [architecture](ARCHITECTURE.md) for module ownership.

## Select verification

| Change | Routine iteration | Checkpoint |
| --- | --- | --- |
| Documentation or workflow | Layout/links and focused tooling tests; no C compilation | Review the resulting text and plan |
| Local implementation fix | Reproducer plus the affected caller/consumer | Relevant component group |
| Radio packet implementation | `tools/test_radio_profiles.py` | Shared owner/retirement checks when those contracts change |
| SDK API or dependency graph | Affected public consumer and ABI checks. Use `tools/test_sdk_services.py --module <name>` for an independent link | SDK group; clean-source/relocation checks when inputs or paths change |
| Application/sleep/USB ownership | Exact transition reproducer and affected integration | Lifecycle plus affected integration groups |
| Reviewed release or broad integration | Inspect the full plan, then execute it once | Additional artifact/hardware checks only in their authorized stage |

Use `tools/test_firmware_regressions.py --suite <group> --plan` before an expensive
aggregate. The default full run includes unit modules and executes identical
commands only once. Different arguments remain separate cases. Do not also run
complete unittest discovery afterward. For a small edit, invoke the relevant
test directly rather than selecting all unit modules.

Every selected test executes again. Duplicate omission applies only within that
one invocation; an old PASS is never a current result. Existing build reuse must
validate sources, headers, flags, compiler and linked inputs. Introduce additional
cache machinery only after measuring a remaining compilation bottleneck.

The SDK application workflow compares pushes and pull requests against their
recorded base before installing tools. It runs the full app matrix for changes
to build inputs, including app guides that enter packages. The job completes
after the diff check for changes such as general documentation. Manual runs
and runs with an unavailable base use the full matrix.

For documentation-only changes, the main workflow runs the repository layout and
gallery checks. Changes to source or other build inputs also run the Python unit
tests and compiled host regressions. Tags, manual runs and unavailable base
commits use the full verification job.

## Stop and expansion rules

- After the selected checks pass, review the diff and finish the iteration.
  Do not add another test, abstraction or optimization merely to be thorough.
- Repeat a check only after a tested input changes, a failure occurs or a named
  unresolved concern requires stronger evidence. Record that reason.
- Run full regression after exploration settles, once per reviewed integration
  checkpoint. A change to a comment or unrelated document does not invalidate
  compiled behavior; documentation still needs its own review.
- After two unsuccessful attempts at the same hypothesis without new evidence,
  revisit the cause or measurement. Continue useful analysis without generating
  a sequence of speculative firmware candidates.
- A new interface, service or abstraction must solve a current coupling,
  duplication or consumer requirement. Keep unrelated refactors and future
  features out of a bug fix. No task-wide renaming or formatting pass by default.
- Prefer one existing technical guide for durable conclusions. Keep intermediate
  notes and failed variants in ignored storage. Do not create a document per test.

## Timing and evidence

Keep per-check durations and total wall time. Compare one baseline and one changed
run for a workflow optimization; repeat only when the measurement is inconclusive.
No arbitrary pass-count target is an acceptance criterion.

The retained dev.36 full run took 1,272 seconds in its checks. Four unit modules
accounted for 172 seconds and were repeated by a subsequent standalone discovery.
The dev.37 radio group's twelve checks took 37 seconds, excluding snapshot/build
setup. These local measurements justify selecting component checks during radio
iteration; they do not predict every machine or establish hardware performance.

On WSL/DrvFS, writing the 4 MiB source ZIP took 14.65 seconds after the source
inventory scan. Validating that ZIP for reuse took 0.17 seconds. Use
`--source-snapshot` for a second focused run on the same checked source.

Current iteration targets are no compilation for documentation/workflow edits
and roughly one minute for the prepared radio group. Treat a slower run as a
profiling prompt, not a reason to remove relevant coverage or source validation.

The system startup wrapper takes about 0.23 seconds to compile on the prepared
WSL host. Preprocessing and hashing its compiler inputs takes about 0.12 seconds
on the same host. Layout assembly compiles it directly. The SDK service matrix
took about 175 seconds in the retained firmware regression. For localized SDK
changes, select the affected module and direct consumers before full validation.
