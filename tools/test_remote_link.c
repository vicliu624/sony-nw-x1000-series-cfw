#include "../runtime/apps/wireless-remote/link.h"
#include "../runtime/apps/wireless-remote/player_status.h"
#include "../runtime/apps/wireless-remote/receiver.h"
#include "../runtime/apps/wireless-remote/control.h"
#include "../runtime/apps/wireless-remote/mode_wire.h"
#include "../runtime/apps/wireless-remote/session_wire.h"
#include "../runtime/apps/wireless-remote/pairing_proof.h"
#include "../runtime/apps/wireless-remote/transport_goal.h"
#include "../runtime/apps/wireless-remote/playback_icon.h"
#include <assert.h>
#include <string.h>
#include <stdio.h>
static void compact_tests(void) {
    struct wr_status s = {0}, decoded, before;
    uint8_t key[32] = {1}, wire[WR_SIGNED_STATUS_BYTES], copy[WR_SIGNED_STATUS_BYTES];
    s.session = 17;
    s.sequence = 3;
    s.state = XW_PLAY_PAUSED;
    s.valid = 1;
    strcpy(s.id, "0123456789abcdef");
    int n = wr_status_pack(wire, sizeof wire, &s, key);
    assert(n == 84 && !memcmp(wire, "WRS2", 4));
    assert(wr_status_frame(wire, n) && !wr_status_verify(&decoded, wire, n, key) &&
           !memcmp(&decoded, &s, sizeof s));
    before = decoded;
    for (int i = 0; i < n; i++) {
        memcpy(copy, wire, n);
        copy[i] ^= 1;
        assert(wr_status_verify(&decoded, copy, n, key) &&
               !memcmp(&decoded, &before, sizeof before));
    }
    for (int i = 0; i < n; i++)
        assert(wr_status_verify(&decoded, wire, i, key));
    /* Authenticated but structurally invalid lengths, NUL and UTF-8. */
    memcpy(copy, wire, n);
    copy[44] = 65;
    assert(!wr_auth_tag(copy + n - 16, copy, n - 16, key) &&
           wr_status_verify(&decoded, copy, n, key));
    memcpy(copy, wire, n);
    copy[52] = 0;
    assert(!wr_auth_tag(copy + n - 16, copy, n - 16, key) &&
           wr_status_verify(&decoded, copy, n, key));
    memcpy(copy, wire, n);
    copy[52] = 0xff;
    assert(!wr_auth_tag(copy + n - 16, copy, n - 16, key) &&
           wr_status_verify(&decoded, copy, n, key));
    strcpy(s.title, "歌曲 / Song");
    strcpy(s.artist, "Artist");
    strcpy(s.album, "Album");
    n = wr_status_pack(wire, sizeof wire, &s, key);
    assert(n > 84 && n < 128 && !wr_status_verify(&decoded, wire, n, key) &&
           !memcmp(&decoded, &s, sizeof s));
    assert(wr_status_pack(copy, n - 1, &s, key) < 0);
    memset(s.id, 'x', 64);
    s.id[64] = 0;
    memset(s.title, 'y', 255);
    s.title[255] = 0;
    memset(s.artist, 'z', 255);
    s.artist[255] = 0;
    memset(s.album, 'a', 255);
    s.album[255] = 0;
    n = wr_status_pack(wire, sizeof wire, &s, key);
    assert(n == WR_SIGNED_STATUS_BYTES && !memcmp(wire, "WRS1", 4));
    assert(!wr_status_verify(&decoded, wire, n, key) && !memcmp(&decoded, &s, sizeof s));
    puts("compact status: authenticated exact lengths, 84-byte pairing-size collision, UTF-8, "
         "mutation and legacy fallback passed");
}
static void heartbeat_goal_tests(void) {
    struct wr_status indicator = {0};
    indicator.valid = XW_PF_STATE;
    indicator.state = XW_PLAY_PLAYING;
    assert(wr_playback_icon_for(&indicator, 1) == WR_ICON_PLAYING);
    indicator.state = XW_PLAY_PAUSED;
    assert(wr_playback_icon_for(&indicator, 1) == WR_ICON_PAUSED);
    indicator.state = XW_PLAY_STOPPED;
    assert(wr_playback_icon_for(&indicator, 1) == WR_ICON_STOPPED);
    assert(wr_playback_icon_for(&indicator, 0) == WR_ICON_UNKNOWN);
    indicator.valid = 0;
    assert(wr_playback_icon_for(&indicator, 1) == WR_ICON_UNKNOWN);
    struct wr_receiver r = {0};
    uint8_t peer[6] = {2, 1, 2, 3, 4, 5}, key[32] = {1}, wire[WR_SIGNED_STATUS_BYTES];
    assert(!wr_receiver_pair(&r, peer, key, 17));
    assert(!wr_heartbeat_sign(wire, sizeof wire, 17, 1, 1, key));
    assert(wr_receiver_accept(&r, peer, wire, WR_HEARTBEAT_BYTES));
    struct wr_status s = {0};
    s.session = 17;
    s.sequence = 2;
    s.valid = 1;
    s.state = XW_PLAY_PLAYING;
    int n = wr_status_pack(wire, sizeof wire, &s, key);
    assert(n > 0 && !wr_receiver_accept(&r, peer, wire, n));
    assert(!wr_heartbeat_sign(wire, sizeof wire, 17, 3, 2, key));
    assert(!wr_receiver_accept(&r, peer, wire, WR_HEARTBEAT_BYTES) && r.sequence == 3 &&
           r.status.state == XW_PLAY_PLAYING);
    assert(wr_receiver_accept(&r, peer, wire, WR_HEARTBEAT_BYTES));
    for (unsigned i = 0; i < WR_HEARTBEAT_BYTES; i++) {
        wire[i] ^= 1;
        assert(wr_receiver_accept(&r, peer, wire, WR_HEARTBEAT_BYTES));
        wire[i] ^= 1;
    }
    assert(!wr_heartbeat_sign(wire, sizeof wire, 17, 5, 4, key));
    assert(wr_receiver_accept(&r, peer, wire, WR_HEARTBEAT_BYTES) == WR_RECEIVER_RESYNC &&
           r.sequence == 3);
    struct wr_transport_goal g = {0};
    wr_transport_goal_begin(&g, &r.status, 1, XW_OP_PAUSE, 100);
    struct wr_control_receipt receipt = {17, 1, XW_PLAYER_ACCEPTED};
    wr_transport_goal_receipt(&g, &receipt);
    assert(g.request == 1);
    assert(!wr_transport_goal_observe(&g, &r.status) && g.request);
    s.sequence = 4;
    s.state = XW_PLAY_UNKNOWN;
    s.valid = 0;
    assert(!wr_transport_goal_observe(&g, &s) && g.request);
    s.valid = 1;
    s.state = XW_PLAY_PAUSED;
    assert(wr_transport_goal_observe(&g, &s) && !g.request);
    wr_transport_goal_begin(&g, &s, 2, XW_OP_PLAY, 100);
    assert(!wr_transport_goal_expire(&g, 5099) && g.request);
    assert(wr_transport_goal_expire(&g, 5100) && !g.request);
    puts("heartbeat/transport goal: authenticated liveness, replay rejection, receipt != completed "
         "state, bounded no-retry timeout passed");
}
static void command_response_tests(void) {
    struct wr_status initial = {0}, received;
    initial.session = 17;
    initial.sequence = 20;
    initial.valid = XW_PF_STATE;
    initial.state = XW_PLAY_PLAYING;
    struct wr_transport_goal goal = {0};
    struct wr_control_receipt receipt = {17, 1, XW_PLAYER_ACCEPTED};
    /* A real receipt proves a response, not the requested playback transition. */
    wr_transport_goal_begin(&goal, &initial, 1, XW_OP_PAUSE, 100);
    assert(wr_transport_goal_needs_link_check(&goal));
    wr_transport_goal_receipt(&goal, &receipt);
    assert(goal.request && !wr_transport_goal_needs_link_check(&goal));
    assert(wr_transport_goal_expire(&goal, 5100) && !goal.request);
    assert(!wr_transport_goal_needs_link_check(&goal));
    /* Lost receipt, but a newer matching-session state reaches the target. The
     * frontend may show uncertainty for the receipt without dropping this state. */
    wr_transport_goal_begin(&goal, &initial, 2, XW_OP_PAUSE, 6000);
    received = initial;
    received.sequence++;
    received.state = XW_PLAY_PAUSED;
    assert(wr_transport_goal_observe(&goal, &received) && !goal.request);
    assert(!wr_transport_goal_needs_link_check(&goal));
    /* A current non-target state also proves a response, without confirming the
     * desired transition. Foreign or stale traffic supplies no such evidence. */
    wr_transport_goal_begin(&goal, &initial, 3, XW_OP_PAUSE, 7000);
    received = initial;
    received.session++;
    assert(!wr_transport_goal_observe(&goal, &received) &&
           wr_transport_goal_needs_link_check(&goal));
    received = initial;
    assert(!wr_transport_goal_observe(&goal, &received) &&
           wr_transport_goal_needs_link_check(&goal));
    receipt.request = 2;
    wr_transport_goal_receipt(&goal, &receipt);
    assert(wr_transport_goal_needs_link_check(&goal));
    received.sequence++;
    assert(!wr_transport_goal_observe(&goal, &received) &&
           !wr_transport_goal_needs_link_check(&goal));
    assert(wr_transport_goal_expire(&goal, 12000) && !wr_transport_goal_needs_link_check(&goal));
    /* Volume/skip have receipt deadlines too, even though they have no PLAY/PAUSE
     * target. A rejected operation is still a real peer response. */
    wr_transport_goal_begin(&goal, &initial, 4, XW_OP_STEP_VOLUME, 13000);
    assert(!goal.request && wr_transport_goal_needs_link_check(&goal));
    receipt.request = 4;
    receipt.result = XW_PLAYER_IO;
    wr_transport_goal_receipt(&goal, &receipt);
    assert(!wr_transport_goal_needs_link_check(&goal));
    wr_transport_goal_begin(&goal, &initial, 5, XW_OP_PAUSE, 14000);
    assert(wr_transport_goal_expire(&goal, 19000) && wr_transport_goal_needs_link_check(&goal));
    wr_transport_goal_clear(&goal);
    assert(!wr_transport_goal_needs_link_check(&goal));
    wr_transport_goal_begin(&goal, &initial, 6, XW_OP_PAUSE, 20000);
    wr_transport_goal_peer_response(&goal, initial.session + 1);
    assert(wr_transport_goal_needs_link_check(&goal));
    wr_transport_goal_peer_response(&goal, initial.session);
    assert(!wr_transport_goal_needs_link_check(&goal) && goal.request == 6);
    assert(wr_transport_goal_expire(&goal, 25000) && !wr_transport_goal_needs_link_check(&goal));
    puts("COMMAND_RESPONSE_PASS: receipt, observed state and missing peer response have distinct "
         "outcomes; no control replay");
}
static void session_tests(void) {
    uint8_t key[32] = {1}, peer[6] = {2, 1, 2, 3, 4, 5}, challenge[16] = {1}, request[64],
            reply[64], copy[64], decoded[16];
    struct wr_receiver r = {0};
    assert(!wr_receiver_pair(&r, peer, key, 7));
    r.sequence = 99;
    r.have_status = 1;
    assert(!wr_receiver_challenge(&r, challenge, request, sizeof request));
    assert(!wr_session_request_read(decoded, request, 64, key) && !memcmp(decoded, challenge, 16));
    assert(!wr_session_reply(reply, 64, decoded, 8, key));
    struct wr_receiver before = r;
    for (unsigned i = 0; i < 64; i++) {
        memcpy(copy, reply, 64);
        copy[i] ^= 1;
        assert(wr_receiver_session_reply(&r, peer, copy, 64) == -1 &&
               !memcmp(&r, &before, sizeof r));
    }
    uint8_t wrong[6] = {2, 2, 2, 3, 4, 5};
    assert(wr_receiver_session_reply(&r, wrong, reply, 64) == -1 && !memcmp(&r, &before, sizeof r));
    assert(wr_receiver_session_reply(&r, peer, request, 64) == -1);
    assert(wr_receiver_session_reply(&r, peer, reply, 64) == 1 && r.session == 8 && !r.sequence &&
           !r.have_status && !r.challenge_pending);
    before = r;
    assert(wr_receiver_session_reply(&r, peer, reply, 64) == -1 && !memcmp(&r, &before, sizeof r));
    assert(wr_receiver_challenge(&r, challenge, request, 64) == -1);
    challenge[0] = 2;
    r.sequence = 100;
    r.have_status = 1;
    assert(!wr_receiver_challenge(&r, challenge, request, 64));
    assert(!wr_session_reply(reply, 64, challenge, 8, key));
    assert(!wr_receiver_session_reply(&r, peer, reply, 64) && r.sequence == 100 && r.have_status);
    challenge[0] = 3;
    assert(!wr_receiver_challenge(&r, challenge, request, 64));
    assert(!wr_session_reply(reply, 64, challenge, 9, key));
    wr_receiver_cancel_challenge(&r);
    before = r;
    assert(wr_receiver_session_reply(&r, peer, reply, 64) == -1 && !memcmp(&r, &before, sizeof r));
    challenge[0] = 4;
    assert(!wr_receiver_challenge(&r, challenge, request, 64));
    before = r;
    assert(wr_receiver_session_reply(&r, peer, reply, 64) == -1 && !memcmp(&r, &before, sizeof r));
    assert(!wr_session_reply(reply, 64, challenge, 9, key) &&
           wr_receiver_session_reply(&r, peer, reply, 64) == 1);
    uint64_t value = 42;
    memset(challenge, 0, 16);
    assert(wr_session_request(request, 64, challenge, key) == -1 &&
           wr_session_reply(reply, 64, challenge, 0, key) == -1);
    assert(wr_session_reply_read(&value, reply, 63, challenge, key) == -1 && value == 42);
    challenge[0] = 5;
    assert(!wr_session_resume_request(request, 64, challenge, key));
    assert(!wr_session_resume_request_read(decoded, request, 64, key) &&
           !memcmp(decoded, challenge, 16));
    assert(wr_session_request_read(decoded, request, 64, key) == -1);
    struct wr_session_progress progress = {300, 123, 456}, received = {0};
    assert(!wr_session_resume_reply(reply, 64, challenge, 0x100000009ULL, &progress, key));
    assert(!wr_session_resume_reply_read(&value, &received, reply, 64, challenge, key));
    assert(value == 0x100000009ULL && received.status == 300 && received.control == 123 &&
           received.library == 456);
    challenge[0] = 6;
    assert(wr_session_resume_reply_read(&value, &received, reply, 64, challenge, key) == -1 &&
           received.control == 123);
    challenge[0] = 5;
    reply[36] ^= 1;
    assert(wr_session_resume_reply_read(&value, &received, reply, 64, challenge, key) == -1 &&
           received.control == 123);
    assert(!wr_receiver_resume_challenge(&r, challenge, request, 64));
    before = r;
    assert(wr_receiver_resume_reply(&r, peer, reply, 64, &received) == -1 &&
           !memcmp(&r, &before, sizeof r));
    assert(!wr_session_resume_reply(reply, 64, challenge, r.session, &progress, key));
    assert(!wr_receiver_resume_reply(&r, peer, reply, 64, &received));
    assert(r.sequence == 300 && !r.have_status && !r.challenge_pending);
    assert(wr_receiver_resume_reply(&r, peer, reply, 64, &received) == -1);
    wr_receiver_clear(&r);
}
static void pairing_tests(void) {
    uint8_t secret[16], walkman[16], controller[16];
    struct wr_pairing_transcript t = {{2, 1, 2, 3, 4, 5}, {2, 6, 7, 8, 9, 10}, {0}, {0}};
    for (unsigned i = 0; i < 16; i++) {
        secret[i] = i + 1;
        t.walkman_nonce[i] = i + 16;
        t.controller_nonce[i] = i + 32;
    }
    const char hex[] = "0102030405060708090a0B0c0D0e0F10";
    uint16_t text[32];
    for (unsigned i = 0; i < 32; i++)
        text[i] = (uint16_t)hex[i];
    uint8_t decoded_code[16];
    assert(!wr_pairing_parse_code(decoded_code, text, 32) && !memcmp(decoded_code, secret, 16));
    assert(wr_pairing_parse_code(decoded_code, text, 31) == -1);
    text[0] = 0xff10;
    assert(wr_pairing_parse_code(decoded_code, text, 32) == -1 &&
           !memcmp(decoded_code, secret, 16));
    uint8_t invitation[WR_PAIRING_INVITE_BYTES], nonce[16];
    unsigned channel = 0;
    assert(!wr_pairing_invite(invitation, 11, t.controller_nonce));
    assert(!wr_pairing_invite_read(&channel, nonce, invitation) && channel == 11 &&
           !memcmp(nonce, t.controller_nonce, 16));
    invitation[5] = 1;
    assert(wr_pairing_invite_read(&channel, nonce, invitation) == -1 && channel == 11);
    assert(!wr_pairing_prove(walkman, secret, &t, WR_PAIRING_WALKMAN));
    assert(!wr_pairing_prove(controller, secret, &t, WR_PAIRING_CONTROLLER));
    assert(
        !memcmp(walkman, "\x15\xc8\x6e\x1c\xea\x82\x1a\x01\x49\x18\xcd\xc4\x2f\xe4\xaa\xf2", 16));
    struct wr_pairing_keys a, b;
    assert(!wr_pairing_finish(&a, controller, secret, &t, WR_PAIRING_WALKMAN));
    assert(!wr_pairing_finish(&b, walkman, secret, &t, WR_PAIRING_CONTROLLER));
    assert(!memcmp(a.auth, b.auth, 32) && !memcmp(a.pmk, b.pmk, 16) && !memcmp(a.lmk, b.lmk, 16));
    assert(a.session == UINT64_C(0xbb98684df2173a4e) && b.session == a.session);
    uint8_t confirmation[WR_PAIRING_CONFIRM_BYTES];
    assert(!wr_pairing_confirmation(confirmation, secret, &t, WR_PAIRING_WALKMAN));
    assert(!wr_pairing_confirmation_read(&a, confirmation, secret, &t, WR_PAIRING_CONTROLLER));
    assert(wr_pairing_confirmation_read(&a, confirmation, secret, &t, WR_PAIRING_WALKMAN) == -1);
    assert(!wr_pairing_confirmation(confirmation, secret, &t, WR_PAIRING_CONTROLLER));
    assert(!wr_pairing_confirmation_read(&a, confirmation, secret, &t, WR_PAIRING_WALKMAN));
    confirmation[20] ^= 1;
    assert(wr_pairing_confirmation_read(&a, confirmation, secret, &t, WR_PAIRING_WALKMAN) == -1);
    assert(memcmp(a.pmk, a.lmk, 16) && memcmp(a.auth, a.pmk, 16));
    assert(wr_pairing_finish(&a, walkman, secret, &t, WR_PAIRING_WALKMAN) == -1);
    t.controller_nonce[0]++;
    assert(wr_pairing_finish(&a, controller, secret, &t, WR_PAIRING_WALKMAN) == -1);
    t.controller_nonce[0]--;
    t.controller[1]++;
    assert(wr_pairing_finish(&a, controller, secret, &t, WR_PAIRING_WALKMAN) == -1);
    t.controller[1]--;
    secret[0]++;
    assert(wr_pairing_finish(&a, controller, secret, &t, WR_PAIRING_WALKMAN) == -1);
    assert(a.session == b.session && !memcmp(a.auth, b.auth, 32));
    secret[0]--;
    struct wr_walkman_pairing walkman_pairing = {0};
    assert(!wr_walkman_pairing_open(&walkman_pairing, t.walkman, 11, 1000));
    assert(!wr_pairing_invite(invitation, 8, t.controller_nonce));
    assert(wr_walkman_pairing_observe(&walkman_pairing, t.controller, invitation, sizeof invitation,
                                      1100) == -1);
    assert(!wr_pairing_invite(invitation, 11, t.controller_nonce));
    assert(!wr_walkman_pairing_observe(&walkman_pairing, t.controller, invitation,
                                       sizeof invitation, 1200));
    assert(wr_walkman_pairing_offer(&walkman_pairing, secret, t.walkman_nonce, confirmation,
                                    4200) == -1);
    assert(!wr_walkman_pairing_observe(&walkman_pairing, t.controller, invitation,
                                       sizeof invitation, 4300));
    assert(
        !wr_walkman_pairing_offer(&walkman_pairing, secret, t.walkman_nonce, confirmation, 4400));
    assert(!wr_pairing_confirmation_read(&b, confirmation, secret, &t, WR_PAIRING_CONTROLLER));
    assert(!wr_pairing_confirmation(confirmation, secret, &t, WR_PAIRING_CONTROLLER));
    assert(wr_walkman_pairing_confirm(&walkman_pairing, t.walkman, confirmation,
                                      sizeof confirmation, &a, 4500) == -1);
    assert(!wr_walkman_pairing_confirm(&walkman_pairing, t.controller, confirmation,
                                       sizeof confirmation, &a, 4500));
    assert(a.session == b.session && walkman_pairing.phase == WR_PAIRING_VERIFIED);
    assert(!wr_pairing_commit_encode(confirmation, &a, &t, WR_PAIRING_WALKMAN));
    assert(!wr_pairing_commit_check(confirmation, &b, &t, WR_PAIRING_WALKMAN));
    assert(wr_pairing_commit_check(confirmation, &b, &t, WR_PAIRING_CONTROLLER) == -1);
    assert(!wr_pairing_commit_encode(confirmation, &b, &t, WR_PAIRING_CONTROLLER));
    assert(!wr_pairing_commit_check(confirmation, &a, &t, WR_PAIRING_CONTROLLER));
    confirmation[51] ^= 1;
    assert(wr_pairing_commit_check(confirmation, &a, &t, WR_PAIRING_CONTROLLER) == -1);
    assert(!memcmp(walkman_pairing.secret, (uint8_t[16]){0}, 16));
    assert(wr_walkman_pairing_confirm(&walkman_pairing, t.controller, confirmation,
                                      sizeof confirmation, &a, 4500) == -1);
    wr_walkman_pairing_close(&walkman_pairing);
    assert(!wr_walkman_pairing_open(&walkman_pairing, t.walkman, 11, 1000));
    assert(wr_walkman_pairing_observe(&walkman_pairing, t.controller, invitation, sizeof invitation,
                                      121000) == -1);
    assert(walkman_pairing.phase == WR_PAIRING_CLOSED);
}
static unsigned mode_dispatches;
static int mode_snapshot(void *context, struct xw_player_snapshot *out) {
    (void)context;
    memset(out, 0, sizeof *out);
    return 0;
}
static int mode_dispatch(void *context, const struct xw_player_command *command) {
    (void)context;
    assert(command->operation == XW_OP_SET_PLAY_MODE);
    assert(command->value >= XW_MODE_NORMAL && command->value < XW_MODE_COUNT);
    mode_dispatches++;
    return XW_PLAYER_ACCEPTED;
}
static int mode_close(void *context) {
    (void)context;
    return 0;
}
static void mode_control_tests(void) {
    struct xw_player player = {0};
    struct xw_player_provider provider = {
        XW_PLAYER_API, 1u << XW_OP_SET_PLAY_MODE, 0, mode_snapshot, mode_dispatch, 0, mode_close};
    struct wr_control_ledger ledger = {0};
    struct wr_control decoded;
    struct wr_control_receipt receipt;
    uint8_t key[32] = {1}, wire[WR_SIGNED_STATUS_BYTES];
    assert(!xw_player_bind(&player, &provider));
    for (unsigned index = 0; index < XW_MODE_COUNT; index++) {
        struct wr_control request = {19, index + 1, XW_OP_SET_PLAY_MODE, (int32_t)index};
        assert(!wr_control_encode(wire, sizeof wire, &request, key));
        assert(!wr_control_decode(&decoded, wire, WR_CONTROL_BYTES, key));
        assert(decoded.operation == 7 && decoded.value == (int32_t)index);
        assert(!wr_control_dispatch(&ledger, &player, 19, &decoded, &receipt) &&
               receipt.result == XW_PLAYER_ACCEPTED);
        assert(mode_dispatches == index + 1);
        assert(!wr_control_dispatch(&ledger, &player, 19, &decoded, &receipt) &&
               mode_dispatches == index + 1);
        decoded.value = (int32_t)((index + 1) % XW_MODE_COUNT);
        assert(wr_control_dispatch(&ledger, &player, 19, &decoded, &receipt) &&
               mode_dispatches == index + 1);
    }
    struct wr_control rejected = {19, 10, XW_OP_PLAY_ITEM, 0};
    assert(wr_control_encode(wire, sizeof wire, &rejected, key));
    rejected.operation = XW_OP_SET_PLAY_MODE;
    rejected.value = 5;
    assert(wr_control_encode(wire, sizeof wire, &rejected, key));
    rejected.value = 4;
    assert(!wr_control_encode(wire, sizeof wire, &rejected, key));
    wire[16] = XW_OP_PLAY_ITEM;
    assert(!wr_auth_tag(wire + 32, wire, 32, key));
    assert(wr_control_decode(&decoded, wire, WR_CONTROL_BYTES, key));
    struct wr_status status = {0}, copy;
    status.session = 19;
    status.sequence = 1;
    status.commands = 128;
    int bytes = wr_status_pack(wire, sizeof wire, &status, key);
    assert(bytes > 0 && !wr_status_verify(&copy, wire, (size_t)bytes, key) && copy.commands == 128);
    status.commands = 256;
    assert(wr_status_pack(wire, sizeof wire, &status, key) < 0);
    assert(!xw_player_close(&player));
    puts("MODE_CONTROL_WIRE_PASS: all five canonical modes, capability bit7, unchanged WRC1, no "
         "duplicate execution and explicit PLAY_ITEM refusal");
}
int main(void) {
    mode_control_tests();
    compact_tests();
    heartbeat_goal_tests();
    command_response_tests();
    session_tests();
    pairing_tests();
    struct wr_status s = {0}, out, old;
    uint8_t wire[WR_STATUS_BYTES];
    s.session = 0x123456789abcdefULL;
    s.sequence = 1;
    s.valid = 39;
    s.commands = 63;
    s.state = 3;
    s.volume = 9;
    s.maximum = 30;
    s.metadata_flags = 7;
    strcpy(s.id, "opaque-track");
    strcpy(s.title, "Test \xe7\x8c\xab");
    strcpy(s.artist, "Artist");
    strcpy(s.album, "Album");
    assert(!wr_status_encode(wire, sizeof wire, &s));
    assert(!wr_status_decode(&out, wire, sizeof wire));
    assert(out.session == s.session && out.volume == 9 && !strcmp(out.title, s.title));
    old = out;
    for (size_t n = 0; n < sizeof wire; n++)
        assert(wr_status_decode(&out, wire, n) == -1);
    assert(!memcmp(&out, &old, sizeof out));
    wire[109] = 0xc0;
    assert(wr_status_decode(&out, wire, sizeof wire) == -1 && !memcmp(&out, &old, sizeof out));
    assert(!wr_status_encode(wire, sizeof wire, &s));
    wire[12] = 0;
    assert(wr_status_decode(&out, wire, sizeof wire) == -1);
    s.volume = 31;
    memset(wire, 0xa5, sizeof wire);
    assert(wr_status_encode(wire, sizeof wire, &s) == -1 && wire[0] == 0xa5);
    struct xw_player_snapshot snap;
    memset(&snap, 0, sizeof snap);
    snap.valid = 39;
    snap.state = XW_PLAY_PLAYING;
    snap.volume = 9;
    snap.volume_max = 30;
    snap.track.flags = 7;
    strcpy(snap.track.title, "Real snapshot adapter");
    assert(!wr_player_status(&out, &snap, 1, 1, 63) && out.state == 3 &&
           !strcmp(out.title, snap.track.title));
    snap.track.title[200] = 'X';
    assert(!wr_player_status(&out, &snap, 1, 1, 63) && !out.title[200]);
    snap.valid = 0;
    assert(!wr_player_status(&out, &snap, 1, 2, 63) && !out.valid && !out.title[0] && !out.volume);
    uint8_t signed_wire[WR_SIGNED_STATUS_BYTES], key[32] = {1}, address[6] = {2, 1, 2, 3, 4, 5};
    struct wr_receiver r = {0};
    assert(!wr_receiver_pair(&r, address, key, 1));
    assert(!wr_status_sign(signed_wire, sizeof signed_wire, &out, key));
    /* Independently generated Python stdlib HMAC vector for this exact frame. */
    const uint8_t expected[16] = {0xe1, 0x12, 0x94, 0xab, 0x24, 0x6e, 0x95, 0xe2,
                                  0xea, 0xf7, 0x88, 0xc4, 0xf2, 0xb9, 0x37, 0xff};
    assert(!memcmp(signed_wire + WR_STATUS_BYTES, expected, sizeof expected));
    assert(!wr_receiver_accept(&r, address, signed_wire, sizeof signed_wire) && r.have_status &&
           r.sequence == 2);
    assert(wr_receiver_accept(&r, address, signed_wire, sizeof signed_wire) == -1);
    out.sequence = 3;
    assert(!wr_status_sign(signed_wire, sizeof signed_wire, &out, key));
    signed_wire[50] ^= 1;
    assert(wr_receiver_accept(&r, address, signed_wire, sizeof signed_wire) == -1 &&
           r.sequence == 2);
    assert(!wr_status_sign(signed_wire, sizeof signed_wire, &out, key));
    address[5] ^= 1;
    assert(wr_receiver_accept(&r, address, signed_wire, sizeof signed_wire) == -1);
    address[5] ^= 1;
    assert(!wr_receiver_accept(&r, address, signed_wire, sizeof signed_wire));
    uint8_t ctrl_wire[WR_CONTROL_BYTES];
    struct wr_control command = {1, 1, XW_OP_STEP_VOLUME, -1}, decoded;
    assert(!wr_control_encode(ctrl_wire, sizeof ctrl_wire, &command, key));
    assert(!wr_control_decode(&decoded, ctrl_wire, sizeof ctrl_wire, key) && decoded.value == -1 &&
           decoded.request == 1);
    ctrl_wire[24] = 1;
    assert(wr_control_decode(&decoded, ctrl_wire, sizeof ctrl_wire, key) == -1);
    struct wr_control_receipt receipt = {1, 1, XW_PLAYER_UNCERTAIN}, decoded_receipt;
    assert(!wr_receipt_encode(ctrl_wire, sizeof ctrl_wire, &receipt, key));
    assert(!wr_receipt_decode(&decoded_receipt, ctrl_wire, sizeof ctrl_wire, key) &&
           decoded_receipt.result == XW_PLAYER_UNCERTAIN);
    assert(wr_control_decode(&decoded, ctrl_wire, sizeof ctrl_wire, key) == -1);
    struct wr_mode mode = {1, 1, 1, 5, 4}, received_mode;
    uint8_t mode_wire[WR_MODE_BYTES];
    assert(!wr_mode_encode(mode_wire, sizeof mode_wire, &mode, key));
    assert(!wr_mode_decode(&received_mode, mode_wire, sizeof mode_wire, key) &&
           received_mode.index == 4);
    struct wr_mode prior_mode = received_mode;
    mode_wire[20] ^= 1;
    assert(wr_mode_decode(&received_mode, mode_wire, sizeof mode_wire, key) == -1 &&
           !memcmp(&received_mode, &prior_mode, sizeof prior_mode));
    mode.native = 4;
    assert(wr_mode_encode(mode_wire, sizeof mode_wire, &mode, key) == -1);
    mode.valid = 0;
    mode.native = mode.index = 0;
    assert(!wr_mode_encode(mode_wire, sizeof mode_wire, &mode, key) &&
           !wr_mode_decode(&received_mode, mode_wire, sizeof mode_wire, key) &&
           !received_mode.valid);
    wr_receiver_clear(&r);
    for (size_t i = 0; i < sizeof r; i++)
        assert(!((unsigned char *)&r)[i]);
    puts("REMOTE_LINK_PASS: bounded UTF8 status, SDK adapter, authenticated reception, replay "
         "rejection and key cleanup");
    return 0;
}
