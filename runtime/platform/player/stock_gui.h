/* Owner-thread-only Sony request binding. No cross-process pointer protocol. */
#ifndef XW_STOCK_GUI_H
#define XW_STOCK_GUI_H
struct xw_stock_gui {
    unsigned bound, busy;
    unsigned long owner;
};
struct xw_stock_gui_view {
    unsigned mode, state, active;
};
int xw_stock_gui_bind(struct xw_stock_gui *);
/* This reports the Audio component's activity, NOT whether music is playing. */
int xw_stock_gui_audio_active(struct xw_stock_gui *, int *active);
/* Observe original actor phase plus its original activity query. Neither field
 * alone establishes engine playback; combine with owned CtrlInfo status. */
int xw_stock_gui_read(struct xw_stock_gui *, struct xw_stock_gui_view *);
/* direction +1 next, -1 previous. Owner-thread only. ACCEPTED means a fresh
 * controller admission ticket was observed, never playback completion. The
 * Sony GUI may change state even on a lower controller failure: UNCERTAIN must
 * not cause an automatic retry. No request is sent in transitional states. */
int xw_stock_gui_skip(struct xw_stock_gui *, int direction);
/* Explicit desired transport state, never a blind toggle. Already-selected
 * stable GUI modes return ACCEPTED without another request; this is not an
 * observation of raw-engine playback. Transitional modes return BUSY. */
int xw_stock_gui_set_playing(struct xw_stock_gui *, int playing);
/* Optional JP1.11 mode path. Canonical indices are XW_MODE_*; native settings
 * persistence remains Sony's. ACCEPTED is native queue admission plus observed
 * cached preference, not engine completion or durable-save acknowledgement. */
int xw_stock_gui_play_mode_supported(struct xw_stock_gui *);
int xw_stock_gui_set_play_mode(struct xw_stock_gui *, int canonical_mode);
int xw_stock_gui_unbind(struct xw_stock_gui *);
#endif
