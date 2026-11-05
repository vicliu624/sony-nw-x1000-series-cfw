/* Private GUI-owner composition. Not a public SDK ABI. */
#ifndef XW_SOURCE_INTENT_H
#define XW_SOURCE_INTENT_H
#include "audio_check_async.h"
#include "stock_source.h"
struct xw_source_intent {
    struct xw_audio_check_async check;
    struct xw_stock_gui *gui;
    struct xw_media_id id;
    struct xw_stock_source_result receipt;
    uint64_t generation,last;
    unsigned bound,terminal,cancelled;
    int result;
};
int xw_source_intent_init(struct xw_source_intent *,struct xw_stock_gui *);
/* Explicit owner polling only: the worker never submits a command. Generations
 * must increase for new intents, including retries after cancellation/source
 * loss. Same-generation polling cannot change the ID or replay a submission.
 * NULL cancels without undoing an already submitted original request. Native
 * ACCEPTED/UNCERTAIN is admission bookkeeping, not playback completion.
 * Output stays unchanged while pending or on invalid/stale arguments. */
int xw_source_intent_observe(struct xw_source_intent *,const struct xw_media_id *,uint64_t generation,uint64_t now_ms,struct xw_stock_source_result *);
/* Read a fresh provider snapshot after submission. OK means the target ID is
 * currently observed PLAYING, not that this request caused a change/restart.
 * No cached success, retry or inferred state. Missing fields are UNAVAILABLE;
 * a different track or a known non-playing state is BUSY. Owner only. */
int xw_source_intent_check_target(struct xw_source_intent *,struct xw_player *,uint64_t generation);
/* Stop/drain/destroy check.worker before freeing this structure or its GUI.
 * No call is valid after that worker has been destroyed. */
#endif
