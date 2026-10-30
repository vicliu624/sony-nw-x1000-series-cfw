#include "stock_provider.h"
#include <string.h>
extern unsigned long pthread_self(void);
#define STOCK_BOUND 0x58575031u

static int owner(struct xw_stock_provider *s)
{
    if (!s || s->bound != STOCK_BOUND) return XW_PLAYER_CLOSED;
    return s->owner == pthread_self() ? 0 : XW_PLAYER_BUSY;
}

static int snapshot(void *context, struct xw_player_snapshot *out)
{
    struct xw_stock_provider *s = context;
    struct xw_stock_volume_view volume;
    struct xw_stock_info_view info;
    struct xw_stock_gui_view gui;
    struct xw_player_snapshot value = {0};
    int rc = owner(s);
    if (rc) return rc;
    rc = xw_stock_volume_read(&s->volume, &volume);
    if (rc) return rc;
    value.valid = XW_PF_VOLUME;
    value.volume = volume.step;
    value.volume_min = volume.minimum;
    value.volume_max = volume.maximum;
    rc = xw_stock_info_read(&s->info, &info);
    if (rc && rc != XW_PLAYER_UNAVAILABLE) return rc;
    if (!rc && info.track_id_valid) {
        value.track.id = info.track_id;
        value.valid |= XW_PF_TRACK;
    }
    if (!rc && !info.substate && !info.error && !xw_stock_gui_read(&s->gui,&gui)) {
        /* CtrlInfo defaults to primary0 even before any track is bound. Never
         * turn that into PLAYING. Stable GUI phase and controller status must
         * agree; transition, failure and initialization remain unknown. */
        if (info.primary==0 && info.track_present &&
            gui.active && gui.mode==1 && gui.state==5)
            value.state=XW_PLAY_PLAYING;
        else if (info.primary==1 && info.track_present &&
                 gui.active && gui.mode==2 && gui.state==2)
            value.state=XW_PLAY_PAUSED;
        else if (info.primary==2 && !gui.active)
            value.state=XW_PLAY_STOPPED;
        if (value.state!=XW_PLAY_UNKNOWN) value.valid|=XW_PF_STATE;
    }
    *out = value;
    return 0;
}

static int command(void *context, const struct xw_player_command *request)
{
    struct xw_stock_provider *s = context;
    int rc = owner(s);
    if (rc) return rc;
    switch (request->operation) {
    case XW_OP_PLAY: return xw_stock_gui_set_playing(&s->gui, 1);
    case XW_OP_PAUSE: return xw_stock_gui_set_playing(&s->gui, 0);
    case XW_OP_NEXT: return xw_stock_gui_skip(&s->gui, 1);
    case XW_OP_PREVIOUS: return xw_stock_gui_skip(&s->gui, -1);
    case XW_OP_STEP_VOLUME: return xw_stock_volume_step(&s->volume, request->value);
    default: return XW_PLAYER_UNSUPPORTED;
    }
}

static int close_provider(void *context)
{
    struct xw_stock_provider *s = context;
    int rc = owner(s);
    if (rc) return rc;
    if (s->gui.busy || s->info.busy || s->gui.owner != s->owner ||
        s->info.owner != s->owner || s->volume.owner != s->owner)
        return XW_PLAYER_BUSY;
    rc = xw_stock_gui_unbind(&s->gui);
    if (rc) return rc;
    xw_stock_info_unbind(&s->info);
    xw_stock_volume_unbind(&s->volume);
    s->bound = 0;
    s->owner = 0;
    return 0;
}

int xw_stock_player_bind(struct xw_player *player, struct xw_stock_provider *s)
{
    struct xw_player_provider provider = {0};
    int rc;
    if (!player || !s) return XW_PLAYER_INVALID;
    if (player->initialized || s->bound) return XW_PLAYER_BUSY;
    memset(s, 0, sizeof *s);
    rc = xw_stock_gui_bind(&s->gui);
    if (rc) return rc;
    rc = xw_stock_volume_bind(&s->volume);
    if (rc) {
        xw_stock_gui_unbind(&s->gui);
        return rc;
    }
    rc = xw_stock_info_bind(&s->info);
    if (rc) {
        xw_stock_volume_unbind(&s->volume);
        xw_stock_gui_unbind(&s->gui);
        return rc;
    }
    s->owner = pthread_self();
    s->bound = STOCK_BOUND;
    provider.api = XW_PLAYER_API;
    provider.commands = (1u << XW_OP_PLAY) | (1u << XW_OP_PAUSE) |
        (1u << XW_OP_NEXT) | (1u << XW_OP_PREVIOUS) | (1u << XW_OP_STEP_VOLUME);
    provider.context = s;
    provider.snapshot = snapshot;
    provider.command = command;
    provider.close = close_provider;
    rc = xw_player_bind(player, &provider);
    if (rc) close_provider(s);
    return rc;
}
