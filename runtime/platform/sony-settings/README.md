# Private Sony Settings adapters

This module implements the Japanese 1.11 stock menu bindings used by Wireless
Remote. It is private firmware integration, excluded from the public SDK.

| Source | Responsibility |
| --- | --- |
| `bindings.h` | Named menu states, event IDs, object offsets and wording IDs |
| `native_page.c` | Original FSM callbacks, navigation and pairing-result routing |
| `native_page_entry.c` | Settings/Wireless entry dispatch and qualified wording override |
| `native_choice_view.c` | Borrow and restore an existing native choice view |
| `native_settings.c` | Legacy request-only Settings callback used by analysis composition |

`bindings.h` names original object/resource layouts, native function addresses,
event IDs and wording IDs. Derived states for the composed Remote group live
beside that group in `native_page.h`. Consumer timeouts, pairing-code copy
limits, trace tags and activation decisions stay with the consumer adapter.

The main choice confirmation uses row IDs `0xff0000`/`0xff0001`; the original
question dialog returns 1/2. Their named constants remain separate. Pair-select
and forget operations borrow the same question control 43, temporarily install
their own wording SID and restore 14400 only if that operation's SID still owns
the field. This is shared-control ownership, not a dedicated forget-dialog object.

The player integration supplies hash-checked code/resource ports and its GUI
owner. The Remote consumer supplies the request backend. These adapters do not
open a display, process input independently, persist state, start radio hardware
or grant player capabilities. Opening a page only borrows the existing control;
an explicit confirmation submits the selected intent.

A view lease keeps its original SID/count, owner and epoch. Close first marks
the lease as closing. Restoration requires the matching original completion,
an interactive parent, unchanged identity and an inactive, settled control.
Ownership or resource mismatch retains the lease for cleanup instead of
silently resetting native fields.

Builders preserve the original executable registration and compile these files
only in the qualified menu profile. Source moves and naming changes require
fresh receipts and a comparison of the generated program, followed by native
menu, view restoration, backend and owner-lifecycle regression checks. See
[stock bindings](../../../docs/reference/STOCK_LIFECYCLE.md) and
[platform knowledge](../../../docs/KNOWLEDGE.md).
