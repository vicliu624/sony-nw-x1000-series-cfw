#ifndef WR_TRANSPORT_GOAL_H
#define WR_TRANSPORT_GOAL_H
#include "control.h"
#include <string.h>
/* Command outcome and peer response are independent observations. The caller
 * supplies authenticated receipts/status only. This object owns no radio,
 * timer, retry, UI or global connection state. */
#define WR_TRANSPORT_CONFIRM_MS 5000u
struct wr_transport_goal {
    uint64_t session, started;
    /* command: latest intent; request: outstanding PLAY/PAUSE state goal. */
    uint32_t command, request, sequence, state;
    unsigned response_seen;
};
static inline void wr_transport_goal_clear(struct wr_transport_goal *g) { memset(g, 0, sizeof *g); }
static inline void wr_transport_goal_begin(struct wr_transport_goal *g, const struct wr_status *s,
                                           uint32_t request, uint32_t operation, uint64_t now) {
    wr_transport_goal_clear(g);
    g->session = s->session;
    g->started = now;
    g->command = request;
    g->sequence = s->sequence;
    if (operation != XW_OP_PLAY && operation != XW_OP_PAUSE)
        return;
    g->request = request;
    g->state = operation == XW_OP_PLAY ? XW_PLAY_PLAYING : XW_PLAY_PAUSED;
}
static inline int wr_transport_goal_observe(struct wr_transport_goal *g,
                                            const struct wr_status *s) {
    if (!g->command || g->session != s->session || s->sequence <= g->sequence)
        return 0;
    g->response_seen = 1;
    if (!g->request || !(s->valid & XW_PF_STATE) || s->state != g->state)
        return 0;
    g->request = 0;
    return 1;
}
static inline void wr_transport_goal_receipt(struct wr_transport_goal *g,
                                             const struct wr_control_receipt *r) {
    if (!g->command || g->command != r->request || g->session != r->session)
        return;
    g->response_seen = 1;
    if (r->result != XW_PLAYER_ACCEPTED && r->result != XW_PLAYER_OK)
        g->request = 0;
}
static inline int wr_transport_goal_needs_link_check(const struct wr_transport_goal *g) {
    return g->command && !g->response_seen;
}
/* A correlated authenticated response from another in-flight read proves peer
 * activity, not execution of this command or completion of its state goal. */
static inline void wr_transport_goal_peer_response(struct wr_transport_goal *g, uint64_t session) {
    if (g->command && g->session == session)
        g->response_seen = 1;
}
static inline int wr_transport_goal_expire(struct wr_transport_goal *g, uint64_t now) {
    if (!g->request || (now >= g->started && now - g->started < WR_TRANSPORT_CONFIRM_MS))
        return 0;
    /* Expiring a state goal does not erase a real response from the peer. */
    g->request = 0;
    return 1;
}
#endif
