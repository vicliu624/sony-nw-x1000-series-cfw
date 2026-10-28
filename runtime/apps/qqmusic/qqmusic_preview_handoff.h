#ifndef HB_QQMUSIC_PREVIEW_HANDOFF_H
#define HB_QQMUSIC_PREVIEW_HANDOFF_H
#include <stdint.h>
struct qq_preview_image {uint64_t bytes;unsigned char sha256[32];};
/* Builder-supplied identities from the reviewed mode1 entry and stock manager.
 * Never learn/accept the current device hashes automatically. A missing policy
 * refuses. This checks software provenance/quiescence, not a sound lease. */
struct qq_preview_handoff_policy {
 struct qq_preview_image spider,launcher,proxy,manager;
};
struct qq_preview_handoff_receipt {
 unsigned self,app,launcher,proxy,manager;
 uint64_t app_birth,launcher_birth,proxy_birth,manager_birth;
};
/* Read-only: fixed system/app/proc files. No audio open, ioctl, process signal,
 * mount write, account access or persistent output. role0 is QQ main; role1
 * is the separately executed preview helper with QQ main as its parent.
 * Success must still be followed by verified user-workspace guard and actual
 * exclusive driver acquisition before any sound configuration. */
int qq_preview_handoff_check(const struct qq_preview_handoff_policy *,unsigned role,
 struct qq_preview_handoff_receipt *);
/* Parser shared by initial and subsequent process-identity checks. */
int qq_preview_process_stat(const char *,unsigned expected_pid,unsigned *parent,uint64_t *birth);
int qq_preview_handoff_recheck(const struct qq_preview_handoff_receipt *);
#endif
