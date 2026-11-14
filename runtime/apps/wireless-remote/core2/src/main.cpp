/* Core2 + Faces Gamepad3 development frontend; hardware qualification pending. */
#include <M5Unified.h>
#include <M5Faces.h>
#include "remote_version.h"
#include "tx_frame_observation.h"
#include "link_transport.h"
#include <cstdio>
#include <cstring>
#include "esp_app_desc.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_now.h"
#include "esp_wifi.h"
#include "esp_random.h"
#include "esp_timer.h"
#include "nvs.h"

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "../../receiver.h"
#include "../../session_wire.h"
#include "../../control.h"
#include "../../transport_goal.h"
#include "../../playback_icon.h"
#include "../../on_demand_link.h"
#include "../../artwork_client.h"
#include "../../artwork_image.h"
#include "cover_renderer.h"
#include "esp_heap_caps.h"
#include "../../mode_wire.h"
#include "../../library_client.h"
#include "../../pairing_proof.h"
#include "../../pairing_auto.h"
#include "driver/gpio.h"
#include "esp_rom_sys.h"

static auto &display = M5.Display;
static M5Canvas canvas(&M5.Display);
static M5Canvas cover_canvas(&M5.Display);
static wr_artwork_client *artwork;
static bool cover_attempted, cover_decoded;
/* Explicit console profiling only. Fixed RAM counters; no timer/air traffic. */
static struct {
    bool active, quiet, cancelled;
    uint32_t request, replies, renders;
    uint64_t started, sent, finished, rtt_sum, rtt_min, rtt_max;
    uint64_t queue_sum, queue_max, render_sum, render_max, decode;
} cover_profile;
static M5Faces_Gamepad3 pad;
enum remote_page {
    REMOTE_PAGE_PLAYER,
    REMOTE_PAGE_LIBRARY,
    REMOTE_PAGE_MODES,
    REMOTE_PAGE_PAIRING,
    REMOTE_PAGE_COUNT
};
enum remote_action {
    REMOTE_ACTION_NONE,
    REMOTE_ACTION_PREVIOUS,
    REMOTE_ACTION_NEXT,
    REMOTE_ACTION_VOLUME_UP,
    REMOTE_ACTION_VOLUME_DOWN,
    REMOTE_ACTION_PLAY_PAUSE
};
static unsigned page = REMOTE_PAGE_PLAYER;
static unsigned focus[3] = {2, 0, 0};
static bool confirm_unpair;
static bool choose_unpair;
static bool channel_focused, channel_edit;
static uint8_t channel_preview;
static bool saved_pairing;
static constexpr char pairing_namespace[] = "walkman-remote";
static constexpr char pairing_key[] = "pair-v1";
static constexpr size_t pairing_bytes = 160;
static TickType_t mode_hint_until;
static bool pad_ready;
static uint8_t pad_previous = 0xff;
static bool lcd_ready;
static bool radio_ready;
static int8_t tx_power;
static uint8_t radio_channel = 8;
static uint8_t mac[6];
static char command[192];
static size_t used;
static bool discard_line;
static wr_receiver receiver;
static walkman_remote::ControllerLink radio_link;
static bool link_fault_reported;
static wr_mode play_mode;
static bool have_mode;
struct packet {
    uint8_t source[6],
        data[WR_ARTWORK_REPLY_MAX > WR_LIBRARY_REPLY_BYTES ? WR_ARTWORK_REPLY_MAX
                                                           : WR_LIBRARY_REPLY_BYTES],
        channel;
    unsigned bytes;
    uint64_t arrived;
    bool broadcast;
};
static wr_library_client library;
static uint32_t library_parent_offset;
static QueueHandle_t packets;
static TickType_t last_status;
static wr_demand_link link_demand = {0, 0, 1, 0};
static unsigned deferred_key;
static uint64_t requested_session;
static bool awaiting_resume;
static bool stale;
static uint32_t received_frames, accepted_status, wrong_source, bad_auth, bad_session, old_sequence;
/* Wi-Fi callbacks and the UI task share only bounded counter updates/copies.
 * No logging, allocation, radio operation or protocol processing holds this lock. */
struct radio_counters {
    uint32_t tx_attempts, tx_queued, tx_rejected, tx_completed, tx_failed, resume_attempts;
    uint32_t rx_callbacks, rx_bad_size, rx_bad_type, rx_queue_drop;
    uint32_t last_filtered_bytes, last_filtered_magic;
    int32_t last_submit;
    uint32_t tx_frames_observed, tx_protected_frames, tx_ccmp_observed;
    wr_tx_frame_observation last_tx_frame;
    uint8_t last_tx_body_length;
};
static radio_counters radio_counts = {};
static portMUX_TYPE radio_counts_lock = portMUX_INITIALIZER_UNLOCKED;
static esp_err_t send_callback_result = ESP_ERR_INVALID_STATE;
static bool radio_tx_idle() {
    portENTER_CRITICAL(&radio_counts_lock);
    bool idle = radio_counts.tx_queued == radio_counts.tx_completed + radio_counts.tx_failed;
    portEXIT_CRITICAL(&radio_counts_lock);
    return idle;
}
static esp_err_t radio_send(const uint8_t *address, const uint8_t *data, size_t bytes) {
    /* Pairing/link broadcasts are authenticated by their own protocols. All
     * player traffic waits for a fresh native encryption key, including boot. */
    if (receiver.paired && !radio_link.ready() &&
        (!address || std::memcmp(address, "\xff\xff\xff\xff\xff\xff", 6)))
        return ESP_ERR_INVALID_STATE;
    bool resume = bytes == WR_SESSION_BYTES && !std::memcmp(data, "WRQ2", 4);
    portENTER_CRITICAL(&radio_counts_lock);
    radio_counts.tx_attempts++;
    if (resume)
        radio_counts.resume_attempts++;
    portEXIT_CRITICAL(&radio_counts_lock);
    esp_err_t result = esp_now_send(address, data, bytes);
    portENTER_CRITICAL(&radio_counts_lock);
    radio_counts.last_submit = result;
    (result == ESP_OK ? radio_counts.tx_queued : radio_counts.tx_rejected)++;
    portEXIT_CRITICAL(&radio_counts_lock);
    return result;
}
static void sent(const esp_now_send_info_t *info, esp_now_send_status_t result) {
    wr_tx_frame_observation frame = {};
    bool observed = info && info->data && wr_tx_frame_observe(info->data, info->data_len, &frame);
    portENTER_CRITICAL(&radio_counts_lock);
    (result == ESP_NOW_SEND_SUCCESS ? radio_counts.tx_completed : radio_counts.tx_failed)++;
    if (observed) {
        radio_counts.tx_frames_observed++;
        radio_counts.tx_protected_frames += frame.protected_frame;
        radio_counts.tx_ccmp_observed += frame.ccmp_present;
        radio_counts.last_tx_frame = frame;
        radio_counts.last_tx_body_length = info->data_len;
    }
    portEXIT_CRITICAL(&radio_counts_lock);
}
static uint32_t command_serial, pending_command;
static wr_transport_goal transport_goal;
static bool redraw_pending;
static void render_status();
static uint32_t last_command_operation, last_command_result, last_ack_ms;
static TickType_t command_started;
static const char *command_state = "D-PAD: FOCUS  A: SELECT  B: BACK";
static void draw_status();
static uint64_t library_now();
static void observe_artwork(uint64_t now);
static void cancel_pairing();
static void request_connection(unsigned key = REMOTE_ACTION_NONE) {
    if (!radio_ready || !receiver.paired)
        return;
    if (key && !deferred_key)
        deferred_key = key;
    stale = true;
    observe_artwork(library_now());
    wr_demand_request(&link_demand);
    if (!radio_link.ready() && !radio_link.negotiating())
        (void)radio_link.connect(library_now());
    command_state = "CHECKING PLAYER - ONE REQUEST";
    draw_status();
}
static bool pairing_active;
static uint32_t pairing_invite_queued, pairing_invite_rejected, pairing_rx;
static bool pairing_offer, pairing_approved, pairing_committed;
static wr_pairing_transcript pairing_peer;
static uint8_t pairing_receipt[WR_PAIRING_CONFIRM_BYTES];
static uint8_t pairing_secret[16], pairing_nonce[16];
static uint8_t pairing_private[32], pairing_public[32];
static TickType_t pairing_started, pairing_announced;
static const uint8_t pairing_broadcast[6] = {255, 255, 255, 255, 255, 255};
static uint64_t library_now() { return uint64_t(xTaskGetTickCount()) * portTICK_PERIOD_MS; }
static bool retry_cover() {
    if (!receiver.have_status || stale || !artwork ||
        wr_artwork_client_retry(artwork, library_now()))
        return false;
    cover_attempted = cover_decoded = false;
    if (cover_profile.active) {
        cover_profile.active = false;
        cover_profile.cancelled = true;
    }
    draw_status();
    return true;
}
static bool profile_cover(bool quiet) {
    if (!retry_cover())
        return false;
    cover_profile = {};
    cover_profile.active = true;
    cover_profile.quiet = quiet;
    cover_profile.started = uint64_t(esp_timer_get_time());
    cover_profile.rtt_min = UINT64_MAX;
    return true;
}
static void library_request(xw_media_view view, uint32_t offset, uint64_t revision,
                            const char *container = nullptr) {
    if (!receiver.paired || !receiver.have_status || stale || library.pending)
        return;
    xw_media_query query = {};
    query.view = view;
    query.offset = offset;
    query.limit = 1;
    query.expected_revision = revision;
    if (container) {
        size_t n = std::strlen(container);
        if (n >= sizeof query.container.value)
            return;
        std::memcpy(query.container.value, container, n + 1);
    }
    uint8_t wire[WR_LIBRARY_REQUEST_BYTES];
    if (wr_library_client_begin(&library, receiver.session, &query, library_now(), wire,
                                sizeof wire, receiver.key))
        return;
    if (radio_send(receiver.address, wire, sizeof wire) != ESP_OK) {
        library.pending = 0;
        library.have = 0;
        library.result = XW_PLAYER_IO;
    }
    draw_status();
}
static void select_page(unsigned next) {
    if (next >= REMOTE_PAGE_COUNT)
        return;
    if (next != REMOTE_PAGE_PAIRING && pairing_active && !pairing_committed)
        cancel_pairing();
    confirm_unpair = false;
    choose_unpair = false;
    channel_edit = channel_focused = false;
    page = next;
    if (page == REMOTE_PAGE_LIBRARY && !library.pending &&
        (!library.have || library.session != receiver.session))
        library_request(XW_MEDIA_TRACKS, 0, 0);
    draw_status();
}
static void wipe(void *p, size_t n) {
    volatile uint8_t *b = (volatile uint8_t *)p;
    while (n--)
        *b++ = 0;
}
static void cancel_pairing() {
    if (!pairing_active)
        return;
    pairing_active = false;
    pairing_offer = pairing_approved = pairing_committed = false;
    wipe(pairing_secret, sizeof pairing_secret);
    wipe(pairing_nonce, sizeof pairing_nonce);
    wipe(pairing_private, sizeof pairing_private);
    wipe(pairing_public, sizeof pairing_public);
    wipe(&pairing_peer, sizeof pairing_peer);
    wipe(pairing_receipt, sizeof pairing_receipt);
    /* The link transport also owns broadcasts for the lifetime of ESP-NOW. */
}
static bool start_pairing() {
    if (!radio_ready || receiver.paired || saved_pairing || pairing_active)
        return false;
    esp_now_peer_info_t peer = {};
    std::memcpy(peer.peer_addr, pairing_broadcast, sizeof pairing_broadcast);
    peer.ifidx = WIFI_IF_STA;
    if (!esp_now_is_peer_exist(pairing_broadcast) && esp_now_add_peer(&peer) != ESP_OK)
        return false;
    esp_fill_random(pairing_private, sizeof pairing_private);
    esp_fill_random(pairing_nonce, sizeof pairing_nonce);
    if (wr_pair_curve_public(pairing_public, pairing_private)) {
        wipe(pairing_private, 32);
        return false;
    }
    pairing_active = true;
    pairing_started = xTaskGetTickCount();
    pairing_announced = pairing_started - pdMS_TO_TICKS(1000);
    return true;
}
static void pairing_step() {
    if (!pairing_active)
        return;
    TickType_t now = xTaskGetTickCount();
    if (now - pairing_started >= pdMS_TO_TICKS(pairing_committed ? 15000 : 120000)) {
        bool saved = pairing_committed;
        cancel_pairing();
        command_state = saved ? "PAIRING SAVED" : "PAIRING WINDOW EXPIRED";
        draw_status();
        return;
    }
    if (now - pairing_announced < pdMS_TO_TICKS(1000))
        return;
    pairing_announced = now;
    if (pairing_committed) {
        (void)radio_send(pairing_broadcast, pairing_receipt, sizeof pairing_receipt);
    } else if (pairing_approved) {
        uint8_t frame[WR_PAIRING_CONFIRM_BYTES];
        if (!wr_pair_auto_reply(frame, pairing_secret, &pairing_peer))
            (void)radio_send(pairing_broadcast, frame, sizeof frame);
    } else if (!pairing_offer) {
        uint8_t frame[WR_PAIR_AUTO_INVITE_BYTES];
        if (!wr_pair_auto_invite(frame, radio_channel, pairing_nonce, pairing_public)) {
            if (radio_send(pairing_broadcast, frame, sizeof frame) == ESP_OK)
                pairing_invite_queued++;
            else
                pairing_invite_rejected++;
        }
    }
}
static void receive_pairing_offer(const packet &p) {
    if (!pairing_active || pairing_offer || p.bytes != WR_PAIR_AUTO_OFFER_BYTES)
        return;
    wr_pairing_transcript transcript = {};
    std::memcpy(transcript.walkman, p.source, 6);
    std::memcpy(transcript.controller, mac, 6);
    std::memcpy(transcript.walkman_nonce, p.data + 4, 16);
    std::memcpy(transcript.controller_nonce, pairing_nonce, 16);
    wr_pairing_keys keys;
    if (!wr_pair_auto_offer_read(&keys, pairing_secret, p.data, pairing_private, pairing_public,
                                 &transcript)) {
        pairing_peer = transcript;
        pairing_offer = pairing_approved = true;
        choose_unpair = false;
        wipe(pairing_private, 32);
        pairing_announced = xTaskGetTickCount() - pdMS_TO_TICKS(1000);
        command_state = "PAIRING WITH SELECTED WALKMAN";
        draw_status();
    }
    wipe(&keys, sizeof keys);
}
static bool save_pairing(const char *record) {
    nvs_handle_t store;
    if (nvs_open(pairing_namespace, NVS_READWRITE, &store) != ESP_OK)
        return false;
    esp_err_t result = record ? nvs_set_blob(store, pairing_key, record, pairing_bytes)
                              : nvs_erase_key(store, pairing_key);
    if (!record && result == ESP_ERR_NVS_NOT_FOUND)
        result = ESP_OK;
    if (result == ESP_OK)
        result = nvs_commit(store);
    nvs_close(store);
    if (result == ESP_OK)
        saved_pairing = record != nullptr;
    return result == ESP_OK;
}
static bool unpair() {
    if (!radio_tx_idle())
        return false;
    if (!save_pairing(nullptr))
        return false;
    if (radio_link.close(true) != ESP_OK) {
        radio_ready = false;
        std::puts("REMOTE_PEER_REMOVE_FAILED_RESTART_REQUIRED");
        return false;
    }
    wr_receiver_clear(&receiver);
    wr_library_client_clear(&library);
    wr_demand_complete(&link_demand);
    deferred_key = REMOTE_ACTION_NONE;
    requested_session = 0;
    awaiting_resume = false;
    have_mode = false;
    stale = false;
    pending_command = 0;
    wr_transport_goal_clear(&transport_goal);
    if (packets)
        xQueueReset(packets);
    return true;
}
static void receive(const esp_now_recv_info_t *info, const uint8_t *data, int bytes) {
    portENTER_CRITICAL(&radio_counts_lock);
    radio_counts.rx_callbacks++;
    portEXIT_CRITICAL(&radio_counts_lock);
    if (!info || !info->rx_ctrl || !data || !packets || bytes < 4 ||
        unsigned(bytes) > sizeof(packet::data)) {
        portENTER_CRITICAL(&radio_counts_lock);
        radio_counts.rx_bad_size++;
        portEXIT_CRITICAL(&radio_counts_lock);
        return;
    }
    bool link = bytes == XNOW_LINK_WIRE_BYTES && !std::memcmp(data, "XNL1", 4);
    bool cover = bytes >= WR_ARTWORK_REPLY_HEADER_BYTES && bytes <= int(WR_ARTWORK_REPLY_MAX) &&
                 !std::memcmp(data, "WRAR", 4);
    if (!link && !cover && !wr_status_frame(data, size_t(bytes)) && bytes != WR_HEARTBEAT_BYTES &&
        bytes != WR_CONTROL_BYTES && bytes != WR_SESSION_BYTES && bytes != WR_MODE_BYTES &&
        bytes != WR_LIBRARY_REPLY_BYTES && bytes != WR_PAIRING_CONFIRM_BYTES &&
        bytes != WR_PAIR_AUTO_OFFER_BYTES) {
        uint32_t magic = 0;
        for (unsigned i = 0; i < 4; i++)
            magic |= uint32_t(data[i]) << (8 * i);
        portENTER_CRITICAL(&radio_counts_lock);
        radio_counts.rx_bad_type++;
        radio_counts.last_filtered_bytes = unsigned(bytes);
        radio_counts.last_filtered_magic = magic;
        portEXIT_CRITICAL(&radio_counts_lock);
        return;
    }
    packet p = {};
    p.arrived = uint64_t(esp_timer_get_time());
    p.bytes = unsigned(bytes);
    p.channel = info->rx_ctrl->channel;
    p.broadcast = info->des_addr && !std::memcmp(info->des_addr, pairing_broadcast, 6);
    std::memcpy(p.source, info->src_addr, 6);
    std::memcpy(p.data, data, size_t(bytes));
    if (xQueueSend(packets, &p, 0) != pdTRUE) {
        portENTER_CRITICAL(&radio_counts_lock);
        radio_counts.rx_queue_drop++;
        portEXIT_CRITICAL(&radio_counts_lock);
    }
}
static void reconnect_step() {
    if (!radio_ready || !receiver.paired || !radio_link.ready())
        return;
    if (receiver.have_status && !stale) {
        wr_receiver_cancel_challenge(&receiver);
        wr_demand_complete(&link_demand);
        return;
    }
    int action = wr_demand_step(&link_demand, library_now());
    if (action < 0) {
        wr_receiver_cancel_challenge(&receiver);
        deferred_key = REMOTE_ACTION_NONE;
        awaiting_resume = false;
        radio_link.require_fresh();
        command_state = "NO PLAYER REPLY - PRESS TO CONNECT";
        draw_status();
        return;
    }
    if (!action)
        return;
    wr_receiver_cancel_challenge(&receiver);
    uint8_t challenge[16], wire[WR_SESSION_BYTES];
    esp_fill_random(challenge, sizeof challenge);
    if (!wr_receiver_resume_challenge(&receiver, challenge, wire, sizeof wire) &&
        radio_send(receiver.address, wire, sizeof wire) == ESP_OK) {
        awaiting_resume = true;
    } else {
        wr_receiver_cancel_challenge(&receiver);
        wr_demand_complete(&link_demand);
        deferred_key = REMOTE_ACTION_NONE;
        awaiting_resume = false;
        command_state = "CONNECT REQUEST REJECTED";
        draw_status();
    }
    wipe(challenge, sizeof challenge);
    wipe(wire, sizeof wire);
}
static int digit(char c) {
    return c >= '0' && c <= '9'   ? c - '0'
           : c >= 'a' && c <= 'f' ? c - 'a' + 10
           : c >= 'A' && c <= 'F' ? c - 'A' + 10
                                  : -1;
}
static bool hex(const char *s, uint8_t *out, size_t n) {
    for (size_t i = 0; i < n; i++) {
        int a = digit(s[2 * i]), b = digit(s[2 * i + 1]);
        if (a < 0 || b < 0)
            return false;
        out[i] = uint8_t(a * 16 + b);
    }
    return true;
}
static bool pair_command(const char *s, bool persist, bool from_radio = false) {
    // Fixed-width provisioning; credentials are never echoed to the console.
    if (std::strlen(s) != pairing_bytes || s[12] != ' ' || s[29] != ' ' || s[94] != ' ' ||
        s[127] != ' ')
        return false;
    uint8_t address[6] = {}, session_bytes[8] = {}, key[32] = {}, lmk[16] = {}, pmk[16] = {};
    bool ok = hex(s, address, 6) && hex(s + 13, session_bytes, 8) && hex(s + 30, key, 32) &&
              hex(s + 95, lmk, 16) && hex(s + 128, pmk, 16);
    uint64_t session = 0;
    for (unsigned i = 0; i < 8; i++)
        session = (session << 8) | session_bytes[i];
    wr_receiver candidate = {};
    ok = ok && !wr_receiver_pair(&candidate, address, key, session);
    if (ok && radio_ready && !receiver.paired && (!pairing_active || from_radio) &&
        (!persist || !saved_pairing)) {
        ok = radio_tx_idle() &&
             radio_link.bind(mac, address, key, pmk, radio_send, library_now) == ESP_OK;
        if (ok && persist && !save_pairing(s)) {
            if (radio_link.close(true) != ESP_OK)
                radio_ready = false;
            ok = false;
        }
        if (ok) {
            receiver = candidate;
            link_fault_reported = false;
            wr_demand_complete(&link_demand);
            wr_demand_request(&link_demand);
            deferred_key = REMOTE_ACTION_NONE;
            requested_session = 0;
            awaiting_resume = true;
            (void)radio_link.connect(library_now());
            have_mode = false;
            play_mode = {};
            wr_library_client_clear(&library);
            last_status = 0;
            stale = true;
            command_serial = pending_command = 0;
            wr_transport_goal_clear(&transport_goal);
            xQueueReset(packets);
        }
    } else
        ok = false;
    wr_receiver_clear(&candidate);
    wipe(address, sizeof address);
    wipe(session_bytes, sizeof session_bytes);
    wipe(key, sizeof key);
    wipe(lmk, sizeof lmk);
    wipe(pmk, sizeof pmk);
    return ok;
}
static void receive_pairing_commit(const packet &p) {
    if (!pairing_active || !pairing_approved || pairing_committed ||
        std::memcmp(p.source, pairing_peer.walkman, 6) || !radio_tx_idle())
        return;
    wr_pairing_keys keys = {};
    uint8_t proof[16], receipt[WR_PAIRING_CONFIRM_BYTES];
    if (wr_pairing_prove(proof, pairing_secret, &pairing_peer, WR_PAIRING_WALKMAN) ||
        wr_pairing_finish(&keys, proof, pairing_secret, &pairing_peer, WR_PAIRING_CONTROLLER) ||
        wr_pairing_commit_check(p.data, &keys, &pairing_peer, WR_PAIRING_WALKMAN) ||
        wr_pairing_commit_encode(receipt, &keys, &pairing_peer, WR_PAIRING_CONTROLLER)) {
        wipe(&keys, sizeof keys);
        return;
    }
    char record[pairing_bytes + 1] = {};
    uint8_t session[8];
    for (unsigned i = 0; i < 8; i++)
        session[i] = uint8_t(keys.session >> (56 - 8 * i));
    char *at = record;
    auto field = [&at](const uint8_t *data, size_t size) {
        const char *hex = "0123456789abcdef";
        for (size_t i = 0; i < size; i++) {
            *at++ = hex[data[i] >> 4];
            *at++ = hex[data[i] & 15];
        }
    };
    field(pairing_peer.walkman, 6);
    *at++ = ' ';
    field(session, 8);
    *at++ = ' ';
    field(keys.auth, 32);
    *at++ = ' ';
    field(keys.lmk, 16);
    *at++ = ' ';
    field(keys.pmk, 16);
    bool saved = pair_command(record, true, true);
    wipe(record, sizeof record);
    wipe(&keys, sizeof keys);
    wipe(session, sizeof session);
    if (saved) {
        std::memcpy(pairing_receipt, receipt, sizeof receipt);
        wipe(pairing_secret, sizeof pairing_secret);
        pairing_committed = true;
        pairing_started = xTaskGetTickCount();
        pairing_announced = pairing_started - pdMS_TO_TICKS(1000);
        command_state = "PAIRING SAVED";
    } else {
        cancel_pairing();
        command_state = "COULD NOT SAVE PAIRING";
    }
    draw_status();
}
static void restore_pairing() {
    nvs_handle_t store;
    esp_err_t result = nvs_open(pairing_namespace, NVS_READONLY, &store);
    if (result == ESP_ERR_NVS_NOT_FOUND)
        return;
    if (result != ESP_OK) {
        command_state = "PAIRING STORAGE UNAVAILABLE";
        return;
    }
    char record[pairing_bytes + 1] = {};
    size_t bytes = pairing_bytes;
    result = nvs_get_blob(store, pairing_key, record, &bytes);
    nvs_close(store);
    saved_pairing = result != ESP_ERR_NVS_NOT_FOUND;
    if (saved_pairing) {
        if (result == ESP_OK && bytes == pairing_bytes && pair_command(record, false))
            command_state = "SAVED PAIRING - WAITING FOR PLAYER";
        else
            command_state = "SAVED PAIRING UNAVAILABLE";
    }
    wipe(record, sizeof record);
}
static bool set_channel(unsigned channel) {
    if (!radio_ready || !radio_tx_idle() || radio_link.negotiating() || pairing_active ||
        pending_command || library.pending || channel < 1 || channel > 13)
        return false;
    if (channel == radio_channel)
        return true;
    if (esp_wifi_set_channel(uint8_t(channel), WIFI_SECOND_CHAN_NONE) != ESP_OK)
        return false;
    nvs_handle_t store;
    esp_err_t result = nvs_open(pairing_namespace, NVS_READWRITE, &store);
    if (result == ESP_OK) {
        result = nvs_set_u8(store, "channel", uint8_t(channel));
        if (result == ESP_OK)
            result = nvs_commit(store);
        nvs_close(store);
    }
    if (result != ESP_OK) {
        if (esp_wifi_set_channel(radio_channel, WIFI_SECOND_CHAN_NONE) != ESP_OK)
            radio_ready = false;
        return false;
    }
    radio_channel = uint8_t(channel);
    xQueueReset(packets);
    wr_receiver_cancel_challenge(&receiver);
    wr_demand_complete(&link_demand);
    wr_demand_request(&link_demand);
    if (receiver.paired) {
        radio_link.require_fresh();
        (void)radio_link.connect(library_now());
    }
    deferred_key = REMOTE_ACTION_NONE;
    awaiting_resume = receiver.paired;
    stale = true;
    have_mode = false;
    wr_library_client_clear(&library);
    command_state = receiver.paired ? "WAITING FOR PLAYER ON NEW CHANNEL" : "CHANNEL SAVED";
    draw_status();
    return true;
}
static bool channel_command(const char *value) {
    if (value[0] < '1' || value[0] > '9')
        return false;
    unsigned channel = unsigned(value[0] - '0');
    if (value[1]) {
        if (value[1] < '0' || value[1] > '9' || value[2])
            return false;
        channel = channel * 10 + unsigned(value[1] - '0');
    }
    return set_channel(channel);
}
static void restore_channel() {
    nvs_handle_t store;
    if (nvs_open(pairing_namespace, NVS_READONLY, &store) != ESP_OK)
        return;
    uint8_t saved;
    if (nvs_get_u8(store, "channel", &saved) == ESP_OK && saved >= 1 && saved <= 13)
        radio_channel = saved;
    nvs_close(store);
}
static void submit_control(uint32_t op, int32_t value) {
    if (op >= XW_OP_COUNT || !radio_ready || !receiver.paired || pending_command ||
        command_serial == UINT32_MAX || !receiver.have_status || stale || !radio_link.ready() ||
        !(receiver.status.commands & (1u << op)))
        return;
    wr_control c = {receiver.session, ++command_serial, op, value};
    uint8_t wire[WR_CONTROL_BYTES];
    if (wr_control_encode(wire, sizeof wire, &c, receiver.key))
        return;
    esp_err_t result = radio_send(receiver.address, wire, sizeof wire);
    wipe(wire, sizeof wire);
    if (result != ESP_OK) {
        command_state = "SEND REJECTED - NO RETRY";
        draw_status();
        return;
    }
    wr_transport_goal_begin(&transport_goal, &receiver.status, c.request, op, library_now());
    last_command_operation = op;
    last_command_result = 0xffffffffu;
    last_ack_ms = 0;
    pending_command = c.request;
    command_started = xTaskGetTickCount();
    command_state = "WAITING FOR PLAYER RECEIPT";
    draw_status();
}
static void control_key(unsigned key) {
    if (!radio_ready || !receiver.paired || pending_command || command_serial == UINT32_MAX)
        return;
    if (!receiver.have_status || stale || !radio_link.ready()) {
        request_connection(key);
        return;
    }
    uint32_t op;
    int32_t value = 0;
    if (key == REMOTE_ACTION_PREVIOUS)
        op = XW_OP_PREVIOUS;
    else if (key == REMOTE_ACTION_NEXT)
        op = XW_OP_NEXT;
    else if (key == REMOTE_ACTION_VOLUME_UP) {
        op = XW_OP_STEP_VOLUME;
        value = 1;
    } else if (key == REMOTE_ACTION_VOLUME_DOWN) {
        op = XW_OP_STEP_VOLUME;
        value = -1;
    } else if (key == REMOTE_ACTION_PLAY_PAUSE) {
        if (transport_goal.request)
            return;
        if (!(receiver.status.valid & XW_PF_STATE))
            return;
        if (receiver.status.state == XW_PLAY_PLAYING)
            op = XW_OP_PAUSE;
        else if (receiver.status.state == XW_PLAY_PAUSED ||
                 receiver.status.state == XW_PLAY_STOPPED)
            op = XW_OP_PLAY;
        else
            return;
    } else
        return;
    submit_control(op, value);
}
static void confirm_focus() {
    if (page == REMOTE_PAGE_PLAYER) {
        const unsigned actions[] = {REMOTE_ACTION_VOLUME_DOWN, REMOTE_ACTION_PREVIOUS,
                                    REMOTE_ACTION_PLAY_PAUSE, REMOTE_ACTION_NEXT,
                                    REMOTE_ACTION_VOLUME_UP};
        control_key(actions[focus[REMOTE_PAGE_PLAYER]]);
    } else if (page == REMOTE_PAGE_LIBRARY) {
        unsigned f = focus[REMOTE_PAGE_LIBRARY];
        if (f < 3) {
            library_parent_offset = 0;
            library_request(f == 0   ? XW_MEDIA_TRACKS
                            : f == 1 ? XW_MEDIA_PLAYLISTS
                                     : XW_MEDIA_QUEUE,
                            0, 0);
        } else if (f == 6)
            library_request(library.query.view, 0, 0,
                            library.query.view == XW_MEDIA_PLAYLIST_TRACKS
                                ? library.query.container.value
                                : nullptr);
        else if (library.have && !library.pending) {
            if (f == 3 && library.reply.page.offset)
                library_request(
                    library.query.view, library.reply.page.offset - 1, library.reply.page.revision,
                    library.query.view == XW_MEDIA_PLAYLIST_TRACKS ? library.query.container.value
                                                                   : nullptr);
            else if (f == 5 && library.reply.page.count &&
                     library.reply.page.next_offset < library.reply.page.total)
                library_request(
                    library.query.view, library.reply.page.next_offset, library.reply.page.revision,
                    library.query.view == XW_MEDIA_PLAYLIST_TRACKS ? library.query.container.value
                                                                   : nullptr);
            else if (f == 4 && library.query.view == XW_MEDIA_PLAYLISTS &&
                     library.reply.page.count) {
                library_parent_offset = library.reply.page.offset;
                library_request(XW_MEDIA_PLAYLIST_TRACKS, 0, 0, library.reply.item.id.value);
            } else if (f == 4)
                page = REMOTE_PAGE_PLAYER;
        }
    } else if (page == REMOTE_PAGE_MODES) {
        mode_hint_until = xTaskGetTickCount() + pdMS_TO_TICKS(5000);
        if (!receiver.have_status || stale || !radio_link.ready()) {
            request_connection();
        } else if (!(receiver.status.commands & (1u << XW_OP_SET_PLAY_MODE))) {
            command_state = "MODE CONTROL NOT SUPPORTED";
        } else {
            submit_control(XW_OP_SET_PLAY_MODE, int32_t(focus[REMOTE_PAGE_MODES]));
        }
    } else if (channel_edit) {
        if (set_channel(channel_preview))
            channel_edit = false;
        else
            command_state = "COULD NOT SAVE CHANNEL";
    } else if (channel_focused && !pairing_active && !confirm_unpair) {
        channel_preview = radio_channel;
        channel_edit = true;
        command_state = "Left/Right: adjust   B: cancel";
    } else if (pairing_active) {
        if (pairing_committed)
            return;
        if (pairing_offer && !pairing_approved && choose_unpair) {
            pairing_approved = true;
            pairing_announced = xTaskGetTickCount() - pdMS_TO_TICKS(1000);
            command_state = "WAITING FOR WALKMAN TO FINISH";
        } else {
            cancel_pairing();
            command_state = "PAIRING CANCELED";
        }
    } else if (confirm_unpair) {
        if (choose_unpair)
            command_state = unpair() ? "PAIRING REMOVED" : "COULD NOT REMOVE PAIRING";
        confirm_unpair = false;
        choose_unpair = false;
    } else if (receiver.paired || saved_pairing) {
        confirm_unpair = true;
        choose_unpair = false;
    } else
        command_state = start_pairing() ? "WAITING FOR WALKMAN" : "COULD NOT START PAIRING";
    draw_status();
}
static void navigate(int direction) {
    if (page == REMOTE_PAGE_PAIRING) {
        if (channel_edit)
            channel_preview = uint8_t((int(channel_preview) - 1 + direction + 13) % 13 + 1);
        else if (confirm_unpair || (pairing_offer && !pairing_approved))
            choose_unpair = direction > 0;
        else if (!pairing_active)
            channel_focused = direction > 0;
        draw_status();
        return;
    }
    const unsigned count = page == REMOTE_PAGE_LIBRARY ? 7 : 5;
    focus[page] = unsigned(int(focus[page]) + direction + int(count)) % count;
    draw_status();
}
static void keyboard_init() {
    pad_ready = pad.begin(&M5.In_I2C, M5FACES_BOTTOM3_ADDR, 100000) == M5FACES_OK;
    pad_previous = 0xff;
}
static void keyboard_step() {
    M5.update();
    if (M5.Touch.getCount()) {
        const auto touch = M5.Touch.getDetail();
        if (touch.wasPressed()) {
            if (touch.y >= 215) {
                if (!confirm_unpair && !channel_edit && touch.x >= 0 && touch.x < 320)
                    select_page(unsigned(touch.x) / 80u);
            } else if (page == REMOTE_PAGE_PLAYER && touch.x >= 16 && touch.x < 118 &&
                       touch.y >= 43 && touch.y < 145) {
                const wr_artwork_progress *cover = wr_artwork_client_progress(artwork);
                if (cover && (cover->failed || (cover->complete && !cover_decoded)))
                    (void)retry_cover();
            } else if (page == REMOTE_PAGE_PAIRING && channel_edit && touch.y >= 100 &&
                       touch.y < 140) {
                navigate(touch.x < 160 ? -1 : 1);
            } else if (page == REMOTE_PAGE_PAIRING && touch.y >= 148 && touch.y < 185) {
                if (confirm_unpair || (pairing_offer && !pairing_approved))
                    choose_unpair = touch.x >= 160;
                else if (!pairing_active && !channel_edit)
                    channel_focused = touch.x >= 200;
                confirm_focus();
            } else if (page == REMOTE_PAGE_LIBRARY && touch.y >= 36 && touch.y < 63) {
                focus[REMOTE_PAGE_LIBRARY] = touch.x < 112 ? 0 : touch.x < 208 ? 1 : 2;
                confirm_focus();
            } else if (page == REMOTE_PAGE_LIBRARY && touch.y >= 174 && touch.y < 202) {
                focus[REMOTE_PAGE_LIBRARY] = 3 + unsigned(touch.x < 16    ? 0
                                                          : touch.x > 303 ? 287
                                                                          : touch.x - 16) /
                                                     72;
                confirm_focus();
            } else if (page == REMOTE_PAGE_MODES && touch.y >= 57 && touch.y < 197) {
                focus[REMOTE_PAGE_MODES] = unsigned(touch.y - 57) / 28;
                confirm_focus();
            } else if (page == REMOTE_PAGE_PLAYER && touch.y >= 156 && touch.y < 208) {
                focus[REMOTE_PAGE_PLAYER] = touch.x < 54    ? 0
                                            : touch.x > 266 ? 4
                                            : touch.x < 132 ? 1
                                            : touch.x > 188 ? 3
                                                            : 2;
                confirm_focus();
            }
        }
    }
    if (!pad_ready)
        return;
    pad.update();
    uint8_t raw = pad.getState().raw;
    uint8_t pressed = uint8_t(~raw);
    if ((pressed & (GAMEPAD3_BTN_UP | GAMEPAD3_BTN_DOWN)) ==
            (GAMEPAD3_BTN_UP | GAMEPAD3_BTN_DOWN) ||
        (pressed & (GAMEPAD3_BTN_LEFT | GAMEPAD3_BTN_RIGHT)) ==
            (GAMEPAD3_BTN_LEFT | GAMEPAD3_BTN_RIGHT)) {
        pad_previous = 0xff;
        return;
    }
    uint8_t edges = pad_previous & pressed;
    pad_previous = raw;
    if (edges & GAMEPAD3_BTN_START) {
        focus[REMOTE_PAGE_PLAYER] = 2;
        select_page(REMOTE_PAGE_PLAYER);
        return;
    }
    if (channel_edit && (edges & GAMEPAD3_BTN_B)) {
        channel_edit = false;
        draw_status();
        return;
    }
    if (edges & GAMEPAD3_BTN_B) {
        if (pairing_active && !pairing_committed) {
            cancel_pairing();
            command_state = "PAIRING CANCELED";
            draw_status();
        } else if (confirm_unpair) {
            confirm_unpair = false;
            choose_unpair = false;
            draw_status();
        } else if (page == REMOTE_PAGE_LIBRARY && library.query.view == XW_MEDIA_PLAYLIST_TRACKS &&
                   !library.pending)
            library_request(XW_MEDIA_PLAYLISTS, library_parent_offset, 0);
        else
            select_page(REMOTE_PAGE_PLAYER);
        return;
    }
    if (edges & GAMEPAD3_BTN_SELECT) {
        if (!confirm_unpair && !channel_edit)
            select_page((page + 1) % REMOTE_PAGE_COUNT);
        return;
    }
    if (edges & GAMEPAD3_BTN_A) {
        confirm_focus();
        return;
    }
    if (edges & (GAMEPAD3_BTN_UP | GAMEPAD3_BTN_LEFT))
        navigate(-1);
    else if (edges & (GAMEPAD3_BTN_DOWN | GAMEPAD3_BTN_RIGHT))
        navigate(1);
}

static void draw_idle() { draw_status(); }

static void status() {
    portENTER_CRITICAL(&radio_counts_lock);
    radio_counters diagnostics = radio_counts;
    portEXIT_CRITICAL(&radio_counts_lock);
    const wr_artwork_progress *progress = wr_artwork_client_progress(artwork);
    std::printf(
        "REMOTE_COVER allocated=%u received=%lu total=%lu complete=%u failed=%u decoded=%u\n",
        unsigned(artwork != nullptr), (unsigned long)(progress ? progress->received : 0),
        (unsigned long)(progress ? progress->total : 0), progress ? progress->complete : 0,
        progress ? progress->failed : 0, unsigned(cover_decoded));
    std::printf("REMOTE_COVER_RESULT result=%ld replies=%u timeouts=%u request=%lu sprite=%u\n",
                (long)(progress ? progress->last_result : 0), progress ? progress->replies : 0,
                progress ? progress->timeouts : 0, (unsigned long)(progress ? progress->serial : 0),
                unsigned(cover_canvas.getBuffer() != nullptr));
    unsigned image_width = 0, image_height = 0;
    if (artwork && wr_artwork_client_image_ready(artwork))
        (void)wr_artwork_dimensions(artwork->data, wr_artwork_client_progress(artwork)->total,
                                    &image_width, &image_height);
    std::printf("REMOTE_COVER_PROFILE active=%u quiet=%u cancelled=%u replies=%lu "
                "elapsed_us=%llu rtt_sum_us=%llu rtt_min_us=%llu rtt_max_us=%llu "
                "queue_sum_us=%llu queue_max_us=%llu renders=%lu render_sum_us=%llu "
                "render_max_us=%llu decode_us=%llu width=%u height=%u\n",
                unsigned(cover_profile.active), unsigned(cover_profile.quiet),
                unsigned(cover_profile.cancelled), (unsigned long)cover_profile.replies,
                (unsigned long long)(cover_profile.finished >= cover_profile.started
                    ? cover_profile.finished - cover_profile.started : 0),
                (unsigned long long)cover_profile.rtt_sum,
                (unsigned long long)(cover_profile.replies ? cover_profile.rtt_min : 0),
                (unsigned long long)cover_profile.rtt_max,
                (unsigned long long)cover_profile.queue_sum,
                (unsigned long long)cover_profile.queue_max,
                (unsigned long)cover_profile.renders,
                (unsigned long long)cover_profile.render_sum,
                (unsigned long long)cover_profile.render_max,
                (unsigned long long)cover_profile.decode, image_width, image_height);
    std::printf("REMOTE_LINK policy=on-demand waiting=%u requested=%u deferred=%u\n",
                link_demand.waiting, link_demand.requested, deferred_key);
    std::printf("REMOTE_LINK_KEY bound=%u ready=%u negotiating=%u phase=%u epoch=%llu failed=%u\n",
                unsigned(radio_link.bound()), unsigned(radio_link.ready()),
                unsigned(radio_link.negotiating()), radio_link.phase(),
                (unsigned long long)radio_link.epoch(), unsigned(radio_link.failed()));
    std::printf(
        "REMOTE_MODE valid=%u index=%lu native=%lu sequence=%lu writable=%u pending=%u\n",
        unsigned(have_mode && play_mode.valid && play_mode.session == receiver.session),
        (unsigned long)play_mode.index, (unsigned long)play_mode.native,
        (unsigned long)play_mode.sequence,
        unsigned(receiver.have_status && (receiver.status.commands & (1u << XW_OP_SET_PLAY_MODE))),
        unsigned(last_command_operation == XW_OP_SET_PLAY_MODE && pending_command));
    std::printf("REMOTE_PLAYER state=%lu valid=%lu status_sequence=%lu age_ms=%lu pending=%lu "
                "transport_goal=%lu operation=%lu result=%ld ack_ms=%lu\n",
                (unsigned long)receiver.status.state, (unsigned long)receiver.status.valid,
                (unsigned long)receiver.sequence,
                (unsigned long)((xTaskGetTickCount() - last_status) * portTICK_PERIOD_MS),
                (unsigned long)pending_command, (unsigned long)transport_goal.request,
                (unsigned long)last_command_operation, (long)(int32_t)last_command_result,
                (unsigned long)last_ack_ms);
    std::printf("REMOTE_PAIRING active=%u offer=%u approved=%u committed=%u invite_queued=%lu "
                "invite_rejected=%lu rx=%lu\n",
                unsigned(pairing_active), unsigned(pairing_offer), unsigned(pairing_approved),
                unsigned(pairing_committed), (unsigned long)pairing_invite_queued,
                (unsigned long)pairing_invite_rejected, (unsigned long)pairing_rx);
    std::printf("REMOTE_RX frames=%lu accepted=%lu source=%lu auth=%lu session=%lu sequence=%lu\n",
                (unsigned long)received_frames, (unsigned long)accepted_status,
                (unsigned long)wrong_source, (unsigned long)bad_auth, (unsigned long)bad_session,
                (unsigned long)old_sequence);
    std::printf("REMOTE_RADIO tx_attempts=%lu tx_queued=%lu tx_rejected=%lu tx_completed=%lu "
                "tx_failed=%lu resume_attempts=%lu last_submit=%ld send_callback=%ld "
                "rx_callbacks=%lu rx_bad_size=%lu rx_bad_type=%lu rx_queue_drop=%lu "
                "last_filtered_bytes=%lu last_filtered_magic=0x%08lx\n",
                (unsigned long)diagnostics.tx_attempts, (unsigned long)diagnostics.tx_queued,
                (unsigned long)diagnostics.tx_rejected, (unsigned long)diagnostics.tx_completed,
                (unsigned long)diagnostics.tx_failed, (unsigned long)diagnostics.resume_attempts,
                (long)diagnostics.last_submit, (long)send_callback_result,
                (unsigned long)diagnostics.rx_callbacks, (unsigned long)diagnostics.rx_bad_size,
                (unsigned long)diagnostics.rx_bad_type, (unsigned long)diagnostics.rx_queue_drop,
                (unsigned long)diagnostics.last_filtered_bytes,
                (unsigned long)diagnostics.last_filtered_magic);
    std::printf(
        "REMOTE_TX_FRAME observed=%lu protected=%lu ccmp=%lu control=0x%04x "
        "body_length_byte=%u key_id=%u packet_number=%llu\n",
        (unsigned long)diagnostics.tx_frames_observed,
        (unsigned long)diagnostics.tx_protected_frames, (unsigned long)diagnostics.tx_ccmp_observed,
        unsigned(diagnostics.last_tx_frame.frame_control),
        unsigned(diagnostics.last_tx_body_length), unsigned(diagnostics.last_tx_frame.key_id),
        (unsigned long long)diagnostics.last_tx_frame.packet_number);
    std::printf("REMOTE_RESUME challenge_pending=%u awaiting=%u observed_other_session=%u\n",
                receiver.challenge_pending, unsigned(awaiting_resume),
                unsigned(requested_session != 0));
    std::printf("REMOTE_STATUS version=%s lcd=%u board=%u width=%ld height=%ld radio=%u "
                "tx_power_quarter_dbm=%d paired=%u player_session=%u channel=%u "
                "mac=%02x%02x%02x%02x%02x%02x\n",
                XW_REMOTE_VERSION, lcd_ready, unsigned(display.getBoard()), long(display.width()),
                long(display.height()), radio_ready, int(tx_power), receiver.paired,
                receiver.have_status && !stale, unsigned(radio_channel), mac[0], mac[1], mac[2],
                mac[3], mac[4], mac[5]);
}
static void clipped(const char *text, int x, int y, int width, uint16_t color) {
    canvas.setClipRect(x, y, width, 20);
    canvas.setTextColor(color);
    canvas.drawString(text, x, y);
    canvas.clearClipRect();
}
static void draw_status() { redraw_pending = true; }
static void observe_artwork(uint64_t now) {
    if (!artwork)
        return;
    auto change =
        wr_artwork_client_observe(artwork, &receiver.status, receiver.have_status && !stale, now);
    if (change == WR_ARTWORK_CONTEXT_CHANGED) {
        cover_attempted = cover_decoded = false;
        if (cover_profile.active) {
            cover_profile.active = false;
            cover_profile.cancelled = true;
        }
    }
    if (change != WR_ARTWORK_UNCHANGED && page == REMOTE_PAGE_PLAYER)
        draw_status();
}
static void artwork_step() {
    if (!artwork)
        return;
    uint64_t now = library_now();
    bool online = receiver.have_status && !stale;
    observe_artwork(now);
    wr_artwork_client_tick(artwork, now);
    const wr_artwork_progress *progress = wr_artwork_client_progress(artwork);
    if (cover_profile.active && progress->failed) {
        cover_profile.active = false;
        cover_profile.cancelled = true;
    }
    static unsigned shown_progress = UINT32_MAX;
    unsigned presentation = progress->total ? progress->received * 100u / progress->total : 0;
    presentation |= progress->failed ? 256u : progress->complete ? 512u : 0;
    if (presentation != shown_progress) {
        shown_progress = presentation;
        if (page == REMOTE_PAGE_PLAYER && !(cover_profile.active && cover_profile.quiet))
            draw_status();
    }
    if (wr_artwork_client_image_ready(artwork) && !cover_attempted) {
        cover_attempted = true;
        uint64_t decode_started = cover_profile.active ? uint64_t(esp_timer_get_time()) : 0;
        cover_decoded = walkman_remote::draw_cover(cover_canvas, artwork->data, progress->total);
        if (cover_profile.active) {
            cover_profile.decode = uint64_t(esp_timer_get_time()) - decode_started;
            cover_profile.active = false;
        }
        if (page == REMOTE_PAGE_PLAYER)
            draw_status();
    }
    if (!online || page != REMOTE_PAGE_PLAYER || pending_command || transport_goal.request ||
        library.pending || pairing_active)
        return;
    uint8_t wire[WR_ARTWORK_REQUEST_BYTES];
    if (!wr_artwork_client_request(artwork, now, wire, sizeof wire, receiver.key)) {
        uint64_t sent_at = cover_profile.active ? uint64_t(esp_timer_get_time()) : 0;
        if (radio_send(receiver.address, wire, sizeof wire) != ESP_OK)
            wr_artwork_client_send_rejected(artwork, now);
        else if (cover_profile.active) {
            cover_profile.sent = sent_at;
            cover_profile.request = progress->pending;
        }
    }
}
static void render_status() {
    redraw_pending = false;
    if (!lcd_ready)
        return;
    uint64_t render_started = cover_profile.active ? uint64_t(esp_timer_get_time()) : 0;
    constexpr uint16_t bg = 0x0863, card = 0x10e5, muted = 0x94d4, white = 0xef9d, mint = 0x7f53;
    auto &g = canvas;
    g.fillScreen(bg);
    g.setFont(&lgfx::fonts::efontCN_12);
    g.setTextSize(1);
    const bool online = receiver.have_status && !stale;
    g.setTextColor(white);
    g.drawString("WALKMAN", 16, 10);
    g.setTextColor(muted);
    g.drawString("REMOTE", 84, 10);
    g.fillCircle(264, 16, 3, online ? mint : 0xd4c9);
    g.setTextColor(online ? mint : muted);
    /* Without heartbeats, a cached status cannot prove current radio liveness. */
    g.drawString(receiver.have_status ? (stale ? "CHECK" : "LAST RX") : "NO RX", 274, 10);
    g.drawFastHLine(16, 30, 288, 0x2127);
    const char *mode_names[] = {"Normal", "Repeat", "Shuffle", "Shuffle & Repeat", "Repeat 1 Song"};
    const bool mode_known =
        online && have_mode && play_mode.valid && play_mode.session == receiver.session;
    if (page == REMOTE_PAGE_PAIRING) {
        g.setTextColor(white);
        g.drawString("PAIRED WALKMAN", 18, 42);
        g.setTextColor(muted);
        if (receiver.paired) {
            char address[24];
            const auto *a = receiver.address;
            std::snprintf(address, sizeof address, "%02X:%02X:%02X:%02X:%02X:%02X", a[0], a[1],
                          a[2], a[3], a[4], a[5]);
            g.drawString(address, 18, 66);
        } else
            g.drawString(saved_pairing ? "Saved pairing unavailable" : "No Walkman paired", 18, 66);
        if (channel_edit) {
            char channel[24];
            std::snprintf(channel, sizeof channel, "Channel %u", channel_preview);
            g.drawString("<", 28, 113);
            g.drawString(channel, 122, 113);
            g.drawString(">", 283, 113);
            g.drawRoundRect(16, 148, 288, 34, 6, 0xf5c9);
            g.drawString("Save channel", 32, 159);
            g.drawString(command_state, 18, 196);
        } else if (pairing_offer) {
            const auto *a = pairing_peer.walkman;
            char address[24];
            std::snprintf(address, sizeof address, "%02X:%02X:%02X:%02X:%02X:%02X", a[0], a[1],
                          a[2], a[3], a[4], a[5]);
            g.drawString("WALKMAN REQUEST", 18, 91);
            g.drawString(address, 18, 113);
            if (pairing_committed) {
                g.drawString("Pairing saved", 32, 159);
            } else if (pairing_approved) {
                g.drawRoundRect(16, 148, 288, 34, 6, 0xf5c9);
                g.drawString("Cancel pairing", 32, 159);
            } else {
                g.drawRoundRect(choose_unpair ? 164 : 16, 148, 140, 34, 6, 0xf5c9);
                g.drawString("Cancel", 32, 159);
                g.drawString("Confirm", 180, 159);
            }
        } else if (pairing_active) {
            char address[24];
            std::snprintf(address, sizeof address, "%02X:%02X:%02X:%02X:%02X:%02X", mac[0], mac[1],
                          mac[2], mac[3], mac[4], mac[5]);
            g.drawString("SELECT CORE2 ON YOUR WALKMAN", 18, 91);
            g.drawString(address, 18, 113);
            g.drawRoundRect(16, 148, 288, 34, 6, 0xf5c9);
            g.drawString("Cancel pairing", 32, 159);
        } else if (confirm_unpair) {
            g.drawString("Remove this pairing from the remote?", 18, 109);
            g.drawRoundRect(choose_unpair ? 164 : 16, 148, 140, 34, 6, 0xf5c9);
            g.drawString("Cancel", 32, 159);
            g.drawString("Remove", 180, 159);
        } else if (receiver.paired || saved_pairing) {
            g.drawRoundRect(channel_focused ? 200 : 16, 148, channel_focused ? 104 : 180, 34, 6,
                            0xf5c9);
            g.drawString("Remove pairing", 32, 159);
            g.drawString("Channel", 218, 159);
        } else {
            g.drawRoundRect(channel_focused ? 200 : 16, 148, channel_focused ? 104 : 180, 34, 6,
                            0xf5c9);
            g.drawString("Start pairing", 32, 159);
            g.drawString("Channel", 218, 159);
        }
        if (!channel_edit)
            g.drawString(command_state, 18, 196);
    } else if (page == REMOTE_PAGE_MODES) {
        g.setTextColor(white);
        g.drawString("PLAY MODE", 18, 35);
        for (unsigned i = 0; i < 5; i++) {
            int y = 57 + 28 * i;
            bool selected = mode_known && play_mode.index == i;
            g.fillRoundRect(16, y, 288, 25, 7, selected ? 0x1a69 : card);
            if (focus[REMOTE_PAGE_MODES] == i)
                g.drawRoundRect(16, y, 288, 25, 7, 0xf5c9);
            g.drawCircle(30, y + 12, 4, selected ? mint : muted);
            if (selected)
                g.fillCircle(30, y + 12, 2, mint);
            g.setTextColor(selected ? mint : white);
            g.drawString(mode_names[i], 44, y + 6);
        }
        g.setTextColor(muted);
        g.drawString(xTaskGetTickCount() < mode_hint_until ? command_state
                     : mode_known                          ? "A: set mode   B: back"
                                                           : "Waiting for the stock play mode",
                     18, 202);
    } else if (page == REMOTE_PAGE_LIBRARY) {
        const char *views[] = {"Tracks", "Playlists", "Queue"};
        for (unsigned i = 0; i < 3; i++) {
            int x = 16 + 96 * i;
            g.fillRoundRect(x, 36, 92, 26, 6, card);
            if (focus[REMOTE_PAGE_LIBRARY] == i)
                g.drawRoundRect(x, 36, 92, 26, 6, 0xf5c9);
            bool selected = i == 0   ? library.query.view == XW_MEDIA_TRACKS
                            : i == 1 ? (library.query.view == XW_MEDIA_PLAYLISTS ||
                                        library.query.view == XW_MEDIA_PLAYLIST_TRACKS)
                                     : library.query.view == XW_MEDIA_QUEUE;
            g.setTextColor(selected ? mint : muted);
            g.drawString(views[i], x + 8, 43);
        }
        g.fillRoundRect(16, 69, 288, 98, 9, card);
        const bool available = online && library.have && library.session == receiver.session;
        if (library.pending) {
            g.setTextColor(muted);
            g.drawString("Reading from Walkman...", 28, 89);
        } else if (available && library.reply.page.count) {
            clipped(library.reply.item.title[0] ? library.reply.item.title : "Untitled", 28, 78,
                    264, white);
            clipped(library.reply.item.artist, 28, 100, 264, muted);
            clipped(library.reply.item.album, 28, 120, 264, muted);
            char position[56];
            if (library.reply.page.total == XW_MEDIA_TOTAL_UNKNOWN)
                std::snprintf(position, sizeof position, "Item %lu",
                              (unsigned long)library.reply.page.offset + 1);
            else
                std::snprintf(position, sizeof position, "Item %lu / %lu",
                              (unsigned long)library.reply.page.offset + 1,
                              (unsigned long)library.reply.page.total);
            g.setTextColor(mint);
            g.drawString(position, 28, 145);
        } else {
            const char *message =
                !online                                   ? "Connect your Walkman"
                : available                               ? "No items"
                : library.result == XW_PLAYER_UNSUPPORTED ? "View not supported by player"
                : library.result == XW_PLAYER_STALE       ? "Library changed - choose Reload"
                : library.result                          ? "No result - choose Reload"
                                                          : "Choose a library view";
            g.setTextColor(muted);
            g.drawString(message, 28, 95);
        }
        const char *actions[] = {"Prev",
                                 library.query.view == XW_MEDIA_PLAYLISTS ? "Open" : "Playing",
                                 "Next", "Reload"};
        for (unsigned i = 0; i < 4; i++) {
            int x = 16 + 72 * i;
            g.fillRoundRect(x, 174, 68, 27, 6, card);
            if (focus[REMOTE_PAGE_LIBRARY] == i + 3)
                g.drawRoundRect(x, 174, 68, 27, 6, 0xf5c9);
            g.setTextColor(white);
            g.drawString(actions[i], x + 8, 182);
        }
        g.setTextColor(muted);
        g.drawString("Read only   A: select   B: back", 18, 203);
    } else {
        g.fillRoundRect(16, 43, 102, 102, 12, 0x1a08);
        for (int y = 51; y < 140; y += 8)
            g.drawFastHLine(23, y, 88, 0x2249);
        g.fillCircle(67, 94, 35, 0x0863);
        g.drawCircle(67, 94, 29, 0x318a);
        g.drawCircle(67, 94, 23, 0x2127);
        g.fillCircle(67, 94, 12, mint);
        g.fillCircle(67, 94, 3, 0x0863);
        if (online && cover_decoded && wr_artwork_client_image_ready(artwork))
            cover_canvas.pushSprite(&canvas, 19, 46);
        else if (online) {
            const wr_artwork_progress *cover = wr_artwork_client_progress(artwork);
            if (cover && cover->session) {
                char caption[24];
                if (cover->failed || (cover->complete && !cover_decoded))
                    std::snprintf(caption, sizeof caption, "Tap to retry");
                else if (cover->total)
                    std::snprintf(caption, sizeof caption, "Cover %u%%",
                                  unsigned(cover->received * 100u / cover->total));
                else
                    std::snprintf(caption, sizeof caption, "Reading cover");
                g.fillRoundRect(22, 116, 90, 22, 4, bg);
                g.setTextColor(muted);
                g.drawString(caption, 25, 122);
            }
        }
        const wr_status &v = receiver.status;
        g.setTextColor(mint);
        g.drawString(receiver.have_status ? "LAST RECEIVED" : "NO PLAYER INFO", 134, 43);
        clipped(receiver.have_status && (v.valid & 4) && v.title[0] ? v.title
                : receiver.have_status                              ? "Track info unavailable"
                                                                    : "Press a control to connect",
                134, 65, 171, white);
        clipped(receiver.have_status && (v.valid & 4) ? v.artist : "Waiting for player information",
                134, 85, 171, muted);
        clipped(receiver.have_status && (v.valid & 4) ? v.album : "", 134, 102, 171, muted);
        char volume[40];
        if (online && (v.valid & 32))
            std::snprintf(volume, sizeof volume, "VOL %ld / %ld", long(v.volume), long(v.maximum));
        else
            std::snprintf(volume, sizeof volume, "VOL --");
        g.setTextColor(white);
        g.drawString(volume, 134, 123);
        unsigned bar = 0;
        if (online && (v.valid & 32) && v.maximum > v.minimum)
            bar = unsigned((v.volume - v.minimum) * 78 / (v.maximum - v.minimum));
        g.fillRoundRect(226, 128, 78, 4, 2, 0x2948);
        if (bar)
            g.fillRoundRect(226, 128, bar, 4, 2, mint);
        g.setTextColor(muted);
        g.drawString(mode_known ? mode_names[play_mode.index] : "Mode unavailable", 18, 148);
        for (int x : {34, 104, 160, 216, 286})
            g.fillCircle(x, 184, x == 160 ? 22 : 16, x == 160 ? mint : card);
        const int positions[] = {34, 104, 160, 216, 286};
        g.drawCircle(positions[focus[REMOTE_PAGE_PLAYER]], 184,
                     focus[REMOTE_PAGE_PLAYER] == 2 ? 25 : 19, 0xf5c9);
        g.setTextColor(white);
        g.drawString("-", 31, 178);
        g.drawString("+", 283, 178);
        g.fillTriangle(111, 176, 111, 192, 99, 184, white);
        g.drawFastVLine(96, 176, 16, white);
        g.fillTriangle(209, 176, 209, 192, 221, 184, white);
        g.drawFastVLine(224, 176, 16, white);
        switch (wr_playback_icon_for(&v, online)) {
        case WR_ICON_PLAYING:
            g.fillTriangle(155, 175, 155, 193, 169, 184, bg);
            break;
        case WR_ICON_PAUSED:
            g.fillRect(153, 176, 4, 16, bg);
            g.fillRect(163, 176, 4, 16, bg);
            break;
        case WR_ICON_STOPPED:
            g.fillRect(153, 177, 14, 14, bg);
            break;
        default:
            g.setTextColor(bg);
            g.drawString("?", 156, 178);
            break;
        }
    }
    g.fillRect(0, 215, 320, 25, card);
    const char *tabs[] = {"Playing", "Library", "Modes", "Pairing"};
    for (unsigned i = 0; i < 4; i++) {
        g.setTextColor(page == i ? mint : muted);
        g.drawString(tabs[i], 14 + 80 * i, 222);
        if (page == i)
            g.fillRoundRect(12 + 80 * i, 215, 46, 2, 1, mint);
    }
    canvas.pushSprite(0, 0);
    if (render_started) {
        uint64_t elapsed = uint64_t(esp_timer_get_time()) - render_started;
        cover_profile.renders++;
        cover_profile.render_sum += elapsed;
        if (elapsed > cover_profile.render_max)
            cover_profile.render_max = elapsed;
    }
}

void setup() {
    Serial.begin(115200);
    auto board = M5.config();
    board.internal_mic = false;
    board.internal_spk = false;
    board.external_spk = false;
    M5.begin(board);
    display.setRotation(1);
    display.setBrightness(96);
    canvas.setPsram(true);
    canvas.setColorDepth(16);
    lcd_ready = canvas.createSprite(320, 240) != nullptr;
    cover_canvas.setPsram(true);
    cover_canvas.setColorDepth(16);
    cover_canvas.createSprite(walkman_remote::cover_side, walkman_remote::cover_side);
    artwork = (wr_artwork_client *)heap_caps_calloc(1, sizeof(wr_artwork_client),
                                                    MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    draw_idle();
    keyboard_init();

    ESP_ERROR_CHECK(esp_netif_init());
    esp_err_t loop_result = esp_event_loop_create_default();
    if (loop_result != ESP_OK && loop_result != ESP_ERR_INVALID_STATE)
        ESP_ERROR_CHECK(loop_result);
    wifi_init_config_t config = WIFI_INIT_CONFIG_DEFAULT();
    config.nvs_enable = 0;
    esp_err_t result = esp_wifi_init(&config);
    if (result == ESP_OK)
        result = esp_wifi_set_storage(WIFI_STORAGE_RAM);
    if (result == ESP_OK)
        result = esp_wifi_set_mode(WIFI_MODE_STA);
    if (result == ESP_OK)
        result = esp_wifi_start();
    if (result == ESP_OK)
        result = esp_wifi_set_ps(WIFI_PS_NONE);
    restore_channel();
    if (result == ESP_OK)
        result = esp_wifi_set_channel(radio_channel, WIFI_SECOND_CHAN_NONE);
    if (result == ESP_OK)
        result = esp_now_init();
    radio_ready = result == ESP_OK;
    if (wr_pair_curve_self_test()) {
        radio_ready = false;
        std::puts("PAIR_CURVE_SELFTEST_FAILED");
    } else
        std::puts("PAIR_CURVE_SELFTEST_PASS");
    packets = xQueueCreate(4, sizeof(packet));
    if (!packets)
        radio_ready = false;
    if (radio_ready && esp_now_register_recv_cb(receive) != ESP_OK)
        radio_ready = false;
    if (radio_ready)
        send_callback_result = esp_now_register_send_cb(sent);
    if (radio_ready && send_callback_result != ESP_OK)
        radio_ready = false;
    if (radio_ready) {
        // Pinned IDF documents 8 quarter-dBm as its minimum accepted TX limit.
        if (esp_wifi_set_max_tx_power(8) != ESP_OK)
            std::puts("REMOTE_TX_LIMIT_REJECTED");
        if (esp_wifi_get_max_tx_power(&tx_power) != ESP_OK)
            tx_power = -1;
        esp_wifi_get_mac(WIFI_IF_STA, mac);
    }
    restore_pairing();
    draw_idle();
    status();
    for (;;) {
        uint8_t bytes[64];
        int count = 0;
        while (Serial.available() && count < int(sizeof bytes))
            bytes[count++] = uint8_t(Serial.read());
        for (int i = 0; i < count; ++i) {
            char c = char(bytes[i]);
            if (c == '\r')
                continue;
            if (c == '\n') {
                command[used] = 0;
                if (discard_line)
                    std::puts("REMOTE_COMMAND_REJECTED");
                else if (!std::strcmp(command, "status"))
                    status();
                else if (!std::strcmp(command, "connect"))
                    request_connection();
                else if (!std::strcmp(command, "cover-retry")) {
                    if (retry_cover()) {
                        std::puts("REMOTE_COVER_RETRY");
                    } else
                        std::puts("REMOTE_COVER_NO_CONFIRMED_TRACK");
                } else if (!std::strcmp(command, "cover-profile") ||
                           !std::strcmp(command, "cover-profile-quiet")) {
                    bool quiet = !std::strcmp(command, "cover-profile-quiet");
                    std::puts(profile_cover(quiet) ? "REMOTE_COVER_PROFILE_STARTED"
                                                  : "REMOTE_COVER_NO_CONFIRMED_TRACK");
                } else if (!std::strcmp(command, "pair-start")) {
                    select_page(REMOTE_PAGE_PAIRING);
                    bool started = start_pairing();
                    command_state =
                        started ? "SELECT CORE2 ON YOUR WALKMAN" : "COULD NOT START PAIRING";
                    draw_status();
                    std::puts(started ? "REMOTE_PAIRING_STARTED" : "REMOTE_PAIRING_REJECTED");
                } else if (!std::strncmp(command, "channel ", 8))
                    std::puts(channel_command(command + 8) ? "REMOTE_CHANNEL_SAVED"
                                                           : "REMOTE_CHANNEL_REJECTED");
                else if (!std::strcmp(command, "redraw")) {
                    draw_status();
                    std::puts("REMOTE_REDRAW_DONE");
                } else if (!std::strncmp(command, "pair ", 5)) {
                    std::puts(pair_command(command + 5, true) ? "REMOTE_PAIRED_SAVED"
                                                              : "REMOTE_PAIR_REJECTED");
                    draw_idle();
                } else if (!std::strcmp(command, "unpair")) {
                    std::puts(unpair() ? "REMOTE_UNPAIRED" : "REMOTE_UNPAIR_REJECTED");
                    draw_idle();
                } else
                    std::puts("COMMANDS status | connect | cover-retry | redraw | channel 1-13 | "
                              "pair | unpair");
                wipe(command, sizeof command);
                discard_line = false;
                used = 0;
            } else if (!discard_line && c >= 32 && c < 127 && used + 1 < sizeof command)
                command[used++] = c;
            else
                discard_line = true;
        }
        packet p;
        while (packets && xQueueReceive(packets, &p, 0) == pdTRUE) {
            if (p.channel != radio_channel)
                continue;
            if (radio_link.receive(p.source, p.broadcast, p.data, p.bytes, library_now())) {
                if (radio_link.negotiating()) {
                    stale = true;
                    observe_artwork(library_now());
                }
                continue;
            }
            if ((p.bytes == WR_PAIRING_CONFIRM_BYTES && !std::memcmp(p.data, "WPC1", 4)) ||
                (p.bytes == WR_PAIR_AUTO_OFFER_BYTES && !std::memcmp(p.data, "WPO2", 4))) {
                pairing_rx++;
                if (!std::memcmp(p.data, "WPC1", 4))
                    receive_pairing_commit(p);
                else
                    receive_pairing_offer(p);
                continue;
            }
            if (!radio_link.ready() || p.broadcast)
                continue;
            received_frames++;
            if (wr_status_frame(p.data, p.bytes) && receiver.paired) {
                wr_status decoded;
                if (std::memcmp(p.source, receiver.address, 6))
                    wrong_source++;
                else if (wr_status_verify(&decoded, p.data, p.bytes, receiver.key))
                    bad_auth++;
                else if (decoded.session != receiver.session) {
                    bad_session++;
                    if (decoded.session != requested_session) {
                        requested_session = decoded.session;
                        request_connection();
                    }
                } else if (decoded.sequence <= receiver.sequence)
                    old_sequence++;
            }
            if (p.bytes == WR_SESSION_BYTES && !std::memcmp(p.data, "WRP2", 4)) {
                wr_session_progress progress;
                int changed =
                    wr_receiver_resume_reply(&receiver, p.source, p.data, p.bytes, &progress);
                if (changed >= 0) {
                    awaiting_resume = false;
                    wr_demand_reply(&link_demand, library_now());
                    if (changed || command_serial < progress.control)
                        command_serial = progress.control;
                    uint32_t library_serial = changed || library.serial < progress.library
                                                  ? progress.library
                                                  : library.serial;
                    pending_command = 0;
                    wr_transport_goal_clear(&transport_goal);
                    stale = true;
                    command_state = "CONNECTED - WAITING FOR STATUS";
                    observe_artwork(library_now());
                    have_mode = false;
                    play_mode = {};
                    wr_library_client_clear(&library);
                    library.session = receiver.session;
                    library.serial = library_serial;
                    draw_status();
                }
            } else if (awaiting_resume) {
                continue;
            } else if (artwork && p.bytes >= WR_ARTWORK_REPLY_HEADER_BYTES &&
                       p.bytes <= WR_ARTWORK_REPLY_MAX && !std::memcmp(p.data, "WRAR", 4) &&
                       receiver.paired && !std::memcmp(p.source, receiver.address, 6)) {
                uint32_t before = wr_artwork_client_progress(artwork)->received;
                uint64_t dequeued_at = cover_profile.active ? uint64_t(esp_timer_get_time()) : 0;
                if (!wr_artwork_client_accept(artwork, library_now(), p.data, p.bytes,
                                              receiver.key)) {
                    wr_transport_goal_peer_response(&transport_goal, receiver.session);
                    auto progress = wr_artwork_client_progress(artwork);
                    if (cover_profile.active && progress->received > before &&
                        progress->serial == cover_profile.request && cover_profile.sent &&
                        p.arrived >= cover_profile.sent) {
                        uint64_t rtt = p.arrived - cover_profile.sent;
                        uint64_t queue = dequeued_at - p.arrived;
                        cover_profile.replies++;
                        cover_profile.rtt_sum += rtt;
                        if (rtt < cover_profile.rtt_min) cover_profile.rtt_min = rtt;
                        if (rtt > cover_profile.rtt_max) cover_profile.rtt_max = rtt;
                        cover_profile.queue_sum += queue;
                        if (queue > cover_profile.queue_max) cover_profile.queue_max = queue;
                        if (progress->complete) cover_profile.finished = p.arrived;
                    }
                }
            } else if (p.bytes == WR_LIBRARY_REPLY_BYTES && !std::memcmp(p.data, "WLBR", 4) &&
                       receiver.paired && !std::memcmp(p.source, receiver.address, 6)) {
                if (!wr_library_client_accept(&library, p.data, p.bytes, receiver.key)) {
                    wr_transport_goal_peer_response(&transport_goal, receiver.session);
                    if (page == REMOTE_PAGE_LIBRARY)
                        draw_status();
                }
            } else if (p.bytes == WR_MODE_BYTES && !std::memcmp(p.data, "WRM1", 4) &&
                       receiver.paired && !std::memcmp(p.source, receiver.address, 6)) {
                wr_mode received;
                if (!wr_mode_decode(&received, p.data, p.bytes, receiver.key) &&
                    received.session == receiver.session &&
                    (!have_mode || received.sequence > play_mode.sequence)) {
                    play_mode = received;
                    have_mode = true;
                    wr_transport_goal_peer_response(&transport_goal, receiver.session);
                    draw_status();
                }
            } else if (p.bytes == WR_CONTROL_BYTES && receiver.paired &&
                       !std::memcmp(p.source, receiver.address, 6)) {
                wr_control_receipt receipt;
                if (!wr_receipt_decode(&receipt, p.data, p.bytes, receiver.key) &&
                    receipt.session == receiver.session && pending_command &&
                    receipt.request == pending_command) {
                    pending_command = 0;
                    last_command_result = (uint32_t)receipt.result;
                    last_ack_ms = (xTaskGetTickCount() - command_started) * portTICK_PERIOD_MS;
                    wr_transport_goal_receipt(&transport_goal, &receipt);
                    command_state =
                        receipt.result == XW_PLAYER_ACCEPTED &&
                                last_command_operation == XW_OP_SET_PLAY_MODE
                            ? "MODE REQUEST ACCEPTED"
                        : receipt.result == XW_PLAYER_ACCEPTED  ? "ACCEPTED - WAIT FOR STATUS"
                        : receipt.result == XW_PLAYER_OK        ? "PLAYER COMMAND RETURNED OK"
                        : receipt.result == XW_PLAYER_UNCERTAIN ? "UNCERTAIN - NOT REPEATED"
                                                                : "PLAYER REJECTED COMMAND";
                    draw_status();
                }
            } else {
                int accepted = wr_receiver_accept(&receiver, p.source, p.data, p.bytes);
                if (accepted == WR_RECEIVER_RESYNC) {
                    request_connection();
                    continue;
                }
                if (accepted)
                    continue;
                accepted_status++;
                bool changed = stale || p.bytes != WR_HEARTBEAT_BYTES;
                last_status = xTaskGetTickCount();
                stale = false;
                observe_artwork(library_now());
                wr_demand_complete(&link_demand);
                if (wr_transport_goal_observe(&transport_goal, &receiver.status)) {
                    command_state = "PLAYBACK STATE CONFIRMED";
                    changed = true;
                }
                if (changed)
                    draw_status();
            }
        }
        if (pending_command && xTaskGetTickCount() - command_started > pdMS_TO_TICKS(3000)) {
            bool check_link = wr_transport_goal_needs_link_check(&transport_goal);
            pending_command = 0;
            last_command_result = uint32_t(XW_PLAYER_UNCERTAIN);
            if (check_link)
                stale = true;
            if (check_link)
                radio_link.require_fresh();
            wr_transport_goal_clear(&transport_goal);
            command_state =
                check_link ? "NO RECEIPT - PRESS TO RECONNECT" : "NO RECEIPT - PEER RESPONDED";
            draw_status();
        }
        if (wr_transport_goal_expire(&transport_goal, library_now())) {
            if (wr_transport_goal_needs_link_check(&transport_goal))
                stale = true;
            if (stale)
                radio_link.require_fresh();
            command_state = "PLAYER STATE NOT CONFIRMED";
            draw_status();
        }
        if (wr_library_client_tick(&library, library_now()) && page == REMOTE_PAGE_LIBRARY)
            draw_status();
        int link_progress = radio_link.step(library_now(), radio_tx_idle());
        if (link_progress == 1) {
            // Old requests are uncertain; only unsent user intent may continue.
            if (pending_command)
                last_command_result = uint32_t(XW_PLAYER_UNCERTAIN);
            pending_command = 0;
            wr_transport_goal_clear(&transport_goal);
            wr_receiver_cancel_challenge(&receiver);
            wr_demand_complete(&link_demand);
            wr_demand_request(&link_demand);
            awaiting_resume = true;
            requested_session = 0;
            stale = true;
            have_mode = false;
            wr_library_client_clear(&library);
            observe_artwork(library_now());
            command_state = "LINK READY - CHECKING PLAYER";
            draw_status();
        } else if (link_progress == 2 || (link_progress < 0 && !link_fault_reported)) {
            link_fault_reported = link_progress < 0;
            wr_receiver_cancel_challenge(&receiver);
            wr_demand_complete(&link_demand);
            deferred_key = REMOTE_ACTION_NONE;
            awaiting_resume = false;
            stale = true;
            command_state = link_progress < 0 ? "RADIO KEY FAILED - RESTART REQUIRED"
                                              : "NO LINK REPLY - PRESS TO CONNECT";
            draw_status();
        }
        reconnect_step();
        if (deferred_key && receiver.have_status && !stale && !link_demand.waiting) {
            unsigned key = deferred_key;
            deferred_key = REMOTE_ACTION_NONE;
            control_key(key);
        }
        pairing_step();
        keyboard_step();
        artwork_step();
        if (redraw_pending)
            render_status();
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}

void loop() { delay(10); }
