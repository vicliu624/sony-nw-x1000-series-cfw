#include "status_sender.h"
#include <string.h>
static int library_finish(struct wr_sender *s, struct wr_library_reply *reply) {
    if (wr_library_reply_encode(s->library_reply, sizeof s->library_reply, reply, s->key)) {
        memset(reply, 0, sizeof *reply);
        reply->session = s->session;
        reply->request = s->library_request.request;
        reply->result = XW_PLAYER_PROTOCOL;
        if (wr_library_reply_encode(s->library_reply, sizeof s->library_reply, reply, s->key))
            return -1;
    }
    s->library_ledger.reply = *reply;
    s->library_ready = 1;
    s->library_active = 0;
    s->library_clocked = 0;
    return XNOW_CLIENT_PENDING;
}
void wr_sender_clear(struct wr_sender *s) {
    if (s) {
        volatile uint8_t *p = (volatile uint8_t *)s;
        size_t n = sizeof *s;
        while (n--)
            *p++ = 0;
    }
}
int wr_sender_init(struct wr_sender *s, struct xw_player *player, struct xnow_client *radio,
                   const uint8_t peer[6], const uint8_t key[32], uint64_t session) {
    if (!s || !player || !player->initialized || !radio || !radio->used || radio->fault || !peer ||
        !key || !session || s->active || (peer[0] & 1))
        return -1;
    unsigned p = 0, k = 0;
    for (unsigned i = 0; i < 6; i++)
        p |= peer[i];
    for (unsigned i = 0; i < 32; i++)
        k |= key[i];
    if (!p || !k)
        return -1;
    memset(s, 0, sizeof *s);
    s->player = player;
    s->radio = radio;
    s->session = session;
    s->active = 1;
    memcpy(s->peer, peer, 6);
    memcpy(s->key, key, 32);
    return 0;
}
int wr_sender_sample(struct wr_sender *s) {
    if (!s || !s->active)
        return -1;
    if (s->pending || s->receipt_ready || s->session_ready || s->library_ready || s->artwork_ready)
        return XNOW_CLIENT_PENDING;
    if (s->sequence == UINT32_MAX)
        return -1;
    int rc = xw_player_snapshot(s->player, &s->snapshot);
    if (rc) {
        int transient = rc == XW_PLAYER_BUSY || rc == XW_PLAYER_UNAVAILABLE;
        int live = s->source_alive ? s->source_alive(s->source_context) : rc == XW_PLAYER_BUSY;
        if (!transient || !live)
            return rc;
        /* A live READ channel may temporarily have no AudioC observation. Report
         * invalid fields, never stale title/state, and keep the radio session. */
        memset(&s->snapshot, 0, sizeof s->snapshot);
    }
    struct wr_status next;
    if (wr_player_status(&next, &s->snapshot, s->session, s->sequence + 1,
                         s->player->provider.commands))
        return -1;
    next.sequence = s->status.sequence;
    int changed = !s->have_status || s->force_status || memcmp(&next, &s->status, sizeof next);
    if (s->have_status && s->now < s->last_status_at)
        return -1;
    if (!changed)
        return 0;
    next.sequence = s->sequence + 1;
    int bytes = wr_status_pack(s->wire, sizeof s->wire, &next, s->key);
    if (bytes < 0)
        return -1;
    uint32_t request;
    rc = xnow_client_send(s->radio, s->peer, s->wire, (size_t)bytes, &request);
    if (rc)
        return rc;
    s->status = next;
    s->have_status = 1;
    s->force_status = 0;
    s->last_status_at = s->now;
    if (changed)
        s->snapshot_sequence = next.sequence;
    s->sequence++;
    s->request = request;
    s->pending = 1;
    s->submitted = 0;
    return 0;
}
int wr_sender_step(struct wr_sender *s) {
    if (!s || !s->active)
        return -1;
    if (!s->pending && s->receipt_ready) {
        uint32_t request;
        int sent = xnow_client_send(s->radio, s->peer, s->receipt, sizeof s->receipt, &request);
        if (sent < 0)
            return sent;
        if (!sent) {
            s->request = request;
            s->pending = 1;
            s->submitted = 0;
            s->receipt_ready = 0;
        }
    } else if (!s->pending && s->session_ready) {
        uint32_t request;
        int sent = xnow_client_send(s->radio, s->peer, s->session_reply, sizeof s->session_reply,
                                    &request);
        if (sent < 0)
            return sent;
        if (!sent) {
            s->request = request;
            s->pending = 1;
            s->submitted = 0;
            s->session_ready = 0;
        }
    } else if (!s->pending && s->library_ready) {
        uint32_t request;
        int sent = xnow_client_send(s->radio, s->peer, s->library_reply, sizeof s->library_reply,
                                    &request);
        if (sent < 0)
            return sent;
        if (!sent) {
            s->request = request;
            s->pending = 1;
            s->submitted = 0;
            s->library_ready = 0;
        }
    } else if (!s->pending && s->artwork_ready) {
        uint32_t request;
        int sent =
            xnow_client_send(s->radio, s->peer, s->artwork_reply, s->artwork_reply_bytes, &request);
        if (sent < 0)
            return sent;
        if (!sent) {
            s->request = request;
            s->pending = 1;
            s->submitted = 0;
            s->artwork_ready = 0;
        }
    }
    int rc = xnow_client_step(s->radio);
    if (rc)
        return rc;
    struct xnow_client_event event;
    rc = xnow_client_take(s->radio, &event, s->incoming, sizeof s->incoming);
    if (rc)
        return rc;
    if (event.kind == XNOW_CLIENT_RX) {
        if (s->receipt_ready || event.flags != XNOW_CLIENT_AUTHENTICATED ||
            memcmp(event.address, s->peer, 6))
            return XNOW_CLIENT_AGAIN;
        if (event.bytes == WR_ARTWORK_REQUEST_BYTES && !memcmp(s->incoming, "WRAQ", 4)) {
            struct wr_artwork_request request;
            if (s->artwork_active || s->artwork_ready ||
                wr_artwork_request_decode(&request, s->incoming, event.bytes, s->key) ||
                request.session != s->session)
                return XNOW_CLIENT_AGAIN;
            if (memcmp(&request.id, &s->artwork_request.id, sizeof request.id))
                s->artwork_serial = 0;
            if (request.request < s->artwork_serial)
                return XNOW_CLIENT_AGAIN;
            if (request.request == s->artwork_serial) {
                if (request.session != s->artwork_request.session ||
                    request.offset != s->artwork_request.offset ||
                    memcmp(&request.id, &s->artwork_request.id, sizeof request.id))
                    return XNOW_CLIENT_AGAIN;
                s->artwork_ready = 1;
                return XNOW_CLIENT_PENDING;
            }
            s->artwork_request = request;
            s->artwork_serial = request.request;
            s->artwork_active = 1;
            return XNOW_CLIENT_PENDING;
        }
        if (event.bytes == WR_LIBRARY_REQUEST_BYTES && !memcmp(s->incoming, "WLBQ", 4)) {
            if (s->library_ready || s->library_active)
                return XNOW_CLIENT_AGAIN;
            struct wr_library_request request;
            struct wr_library_reply reply;
            if (wr_library_request_decode(&request, s->incoming, event.bytes, s->key) ||
                wr_library_dispatch(&s->library_ledger, s->player, s->session, &request, &reply))
                return XNOW_CLIENT_AGAIN;
            s->library_request = request;
            if (reply.result == XW_PLAYER_BUSY) {
                s->library_active = 1;
                s->library_clocked = 0;
                return XNOW_CLIENT_PENDING;
            }
            return library_finish(s, &reply);
        }
        if (event.bytes == WR_SESSION_BYTES &&
            (!memcmp(s->incoming, "WRQ1", 4) || !memcmp(s->incoming, "WRQ2", 4))) {
            uint8_t challenge[16];
            if (s->session_ready)
                return XNOW_CLIENT_AGAIN;
            int resume = s->incoming[3] == '2';
            if ((resume ? wr_session_resume_request_read
                        : wr_session_request_read)(challenge, s->incoming, event.bytes, s->key))
                return XNOW_CLIENT_AGAIN;
            /* A request is identified by protocol/challenge, not the media sequence.
             * Quiet or temporarily unavailable media must not suppress a fresh explicit
             * connection attempt. An authenticated duplicate retains its prior reply. */
            if (s->session_replied && s->incoming[3] == s->session_reply[3] &&
                !memcmp(challenge, s->session_reply + 8, sizeof challenge)) {
                s->session_ready = 1;
                s->force_status = 1;
                return XNOW_CLIENT_PENDING;
            }
            if (resume) {
                struct wr_session_progress progress = {
                    s->sequence, s->ledger.have ? s->ledger.last.request : 0,
                    s->library_ledger.have ? s->library_ledger.last.request : 0};
                if (wr_session_resume_reply(s->session_reply, sizeof s->session_reply, challenge,
                                            s->session, &progress, s->key))
                    return -1;
            } else {
                if (wr_session_reply(s->session_reply, sizeof s->session_reply, challenge,
                                     s->session, s->key))
                    return -1;
            }
            if (s->resync_serial == UINT32_MAX)
                return -1;
            s->resync_serial++;
            s->force_status = 1;
            s->artwork_serial = s->artwork_active = s->artwork_ready = 0;
            s->session_ready = s->session_replied = 1;
            s->session_sequence = s->sequence;
            return XNOW_CLIENT_PENDING;
        }
        struct wr_control command;
        struct wr_control_receipt receipt;
        if (wr_control_decode(&command, s->incoming, event.bytes, s->key) ||
            command.session != s->session)
            return XNOW_CLIENT_AGAIN;
        if (wr_control_dispatch(&s->ledger, s->player, s->session, &command, &receipt))
            return XNOW_CLIENT_AGAIN;
        if (command.operation == XW_OP_SET_PLAY_MODE) {
            if (s->mode_refresh_serial == UINT32_MAX)
                return -1;
            s->mode_refresh_serial++;
        }
        if (wr_receipt_encode(s->receipt, sizeof s->receipt, &receipt, s->key))
            return -1;
        /* An explicit command also requests current state. A previous state frame
         * may have been lost, and an idempotent command need not change the player.
         * Coalesce this refresh; never replay the command or add idle traffic. */
        s->force_status = 1;
        s->receipt_ready = 1;
        return XNOW_CLIENT_PENDING;
    }
    if (!s->pending || event.request != s->request)
        return -1;
    if (event.kind == XNOW_CLIENT_ACK) {
        if (event.operation != 4 || event.result)
            return -1;
        s->submitted = 1;
        return XNOW_CLIENT_PENDING;
    }
    if (event.kind != XNOW_CLIENT_TX || !s->submitted || event.result ||
        memcmp(event.address, s->peer, 6))
        return -1;
    s->pending = 0;
    s->submitted = 0;
    return 0;
}
int wr_sender_library_tick(struct wr_sender *s, uint64_t now) {
    if (!s || !s->active)
        return -1;
    if (!s->library_active)
        return 0;
    if (!s->library_clocked) {
        s->library_started = now;
        s->library_next = now;
        s->library_clocked = 1;
        return XNOW_CLIENT_PENDING;
    }
    if (now < s->library_started || now < s->library_next || now - s->library_started >= 2000) {
        struct wr_library_reply reply = {0};
        reply.session = s->session;
        reply.request = s->library_request.request;
        reply.result = XW_PLAYER_UNAVAILABLE;
        return library_finish(s, &reply);
    }
    if (now - s->library_next < 100 || s->pending || s->receipt_ready || s->session_ready ||
        s->library_ready)
        return XNOW_CLIENT_PENDING;
    s->library_next = now;
    struct wr_library_reply reply;
    if (wr_library_dispatch(&s->library_ledger, s->player, s->session, &s->library_request, &reply))
        return -1;
    return reply.result == XW_PLAYER_BUSY ? XNOW_CLIENT_PENDING : library_finish(s, &reply);
}
int wr_sender_mode(struct wr_sender *s, const struct wr_mode *mode) {
    if (!s || !s->active || !mode || mode->session != s->session)
        return -1;
    if (s->pending || s->receipt_ready || s->session_ready || s->library_ready)
        return XNOW_CLIENT_PENDING;
    uint8_t wire[WR_MODE_BYTES];
    if (wr_mode_encode(wire, sizeof wire, mode, s->key))
        return -1;
    uint32_t request;
    int rc = xnow_client_send(s->radio, s->peer, wire, sizeof wire, &request);
    volatile uint8_t *p = wire;
    for (unsigned i = 0; i < sizeof wire; i++)
        p[i] = 0;
    if (rc)
        return rc;
    s->request = request;
    s->pending = 1;
    s->submitted = 0;
    return 0;
}
int wr_sender_artwork_tick(struct wr_sender *s) {
    if (!s || !s->active)
        return -1;
    if (!s->artwork_active || s->pending || s->receipt_ready || s->session_ready ||
        s->library_ready || s->artwork_ready)
        return 0;
    struct wr_artwork_reply reply = {0};
    reply.session = s->session;
    reply.request = s->artwork_request.request;
    reply.chunk.id = s->artwork_request.id;
    reply.chunk.offset = s->artwork_request.offset;
    struct xw_artwork_chunk chunk = {0};
    reply.result = s->artwork_read
                       ? s->artwork_read(s->artwork_context, s->artwork_request.offset, &chunk)
                       : XW_PLAYER_UNSUPPORTED;
    if (!reply.result) {
        if (memcmp(&chunk.id, &s->artwork_request.id, sizeof chunk.id))
            reply.result = XW_PLAYER_STALE;
        else
            reply.chunk = chunk;
    }
    int bytes = wr_artwork_reply_encode(s->artwork_reply, sizeof s->artwork_reply, &reply, s->key);
    if (bytes < 0)
        return -1;
    s->artwork_reply_bytes = (unsigned)bytes;
    s->artwork_ready = 1;
    s->artwork_active = 0;
    return 0;
}
