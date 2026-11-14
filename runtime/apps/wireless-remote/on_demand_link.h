#ifndef WR_ON_DEMAND_LINK_H
#define WR_ON_DEMAND_LINK_H
#include <stdint.h>
struct wr_demand_link {
    uint64_t started, deadline;
    unsigned requested, waiting;
};
static inline void wr_demand_request(struct wr_demand_link *s) {
    if (s && !s->waiting)
        s->requested = 1;
}
/* 1: one explicit handshake, -1: its bounded timeout, 0: stay silent. */
static inline int wr_demand_step(struct wr_demand_link *s, uint64_t now) {
    if (!s)
        return 0;
    if (s->waiting) {
        if (now < s->started || now >= s->deadline) {
            s->waiting = 0;
            return -1;
        }
        return 0;
    }
    if (!s->requested)
        return 0;
    s->requested = 0;
    s->waiting = 1;
    s->started = now;
    s->deadline = now > UINT64_MAX - 3000 ? UINT64_MAX : now + 3000;
    return 1;
}
static inline void wr_demand_complete(struct wr_demand_link *s) {
    if (s) {
        s->requested = 0;
        s->waiting = 0;
    }
}
static inline void wr_demand_reply(struct wr_demand_link *s, uint64_t now) {
    if (s && s->waiting) {
        s->started = now;
        s->deadline = now > UINT64_MAX - 3000 ? UINT64_MAX : now + 3000;
    }
}
#endif
