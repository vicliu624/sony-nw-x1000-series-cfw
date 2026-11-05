#ifndef WR_NATIVE_CHOICE_VIEW_H
#define WR_NATIVE_CHOICE_VIEW_H
#include <stdint.h>
/* Private prototype for one existing choice view; no new Root slot/object.
 * Requires qualified owner/resource/code ports, not an external SDK handle. */
struct wr_native_choice_view {
 uintptr_t root,view;unsigned long owner;
 uint32_t original_sid,original_count;unsigned held,closing,epoch,acknowledged;
};
int wr_native_choice_view_begin(struct wr_native_choice_view *,unsigned long);
int wr_native_choice_view_end(struct wr_native_choice_view *);
/* Only a qualified original close/new-scene completion may acknowledge.
 * An inactive view snapshot alone must not be treated as that event. */
int wr_native_choice_view_acknowledge(struct wr_native_choice_view *,uint32_t);
int wr_native_choice_view_poll(struct wr_native_choice_view *);
/* Bounded owner tick: read native destination state, then acknowledge/restore.
 * Does not synthesize ready events or change native navigation. */
int wr_native_choice_view_observe(struct wr_native_choice_view *);
#endif
