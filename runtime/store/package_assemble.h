#ifndef HB_STORE_PACKAGE_ASSEMBLE_H
#define HB_STORE_PACKAGE_ASSEMBLE_H
#include "download_plan.h"
#include "download_file.h"
enum hb_assemble_state {HB_ASSEMBLE_EMPTY,HB_ASSEMBLE_OPEN,HB_ASSEMBLE_READY,HB_ASSEMBLE_REVIEW};
enum hb_assemble_error {HB_ASSEMBLE_INPUT=-100,HB_ASSEMBLE_IO=-101,HB_ASSEMBLE_EXISTS=-102,HB_ASSEMBLE_SPACE=-103,HB_ASSEMBLE_INCOMPLETE=-104,HB_ASSEMBLE_CANCELLED=-105};
struct hb_package_assembly {
 const struct hb_package_download_plan *plan;
 char folder[512],parent[512],id[33];unsigned char identity[32],seen[128];
 unsigned added;unsigned long long device,inode;volatile int *stop;enum hb_assemble_state state;
};
/* Synchronous quiescent-cache assembler. Plan must remain immutable/alive.
 * Copies sources, never consumes them; caller discards each cache afterward.
 * Existing .bundle-id is never reused. Errors may retain inactive partial tree. */
void hb_package_assembly_init(struct hb_package_assembly *);
int hb_package_assembly_begin(struct hb_package_assembly *,const char *parent,
 const struct hb_package_download_plan *,unsigned long long reserve,volatile int *stop);
int hb_package_assembly_add(struct hb_package_assembly *,unsigned file_index,const struct hb_download_file *);
int hb_package_assembly_finish(struct hb_package_assembly *,struct hb_bundle *workspace);
/* Explicit same-process discard of this owned inactive tree only. Preflights
 * every entry; unknown, linked or oversized entries refuse all deletion.
 * No adoption of previous-process directories; quiescent caller required. */
int hb_package_assembly_discard(struct hb_package_assembly *);
#endif
