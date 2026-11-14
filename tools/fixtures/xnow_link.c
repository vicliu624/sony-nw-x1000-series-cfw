#include "runtime/platform/espnow/xnow_link.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static const uint8_t root_mac[6] = {2, 0, 0, 0, 0, 1};
static const uint8_t controller_mac[6] = {2, 0, 0, 0, 0, 2};
static uint8_t authentication[32];
static uint8_t saved_hello[XNOW_LINK_WIRE_BYTES], saved_confirm[XNOW_LINK_WIRE_BYTES];
struct entropy { unsigned value; int fail; struct xnow_link *stop; };
static int random_bytes(void *context, uint8_t *out, size_t bytes)
{
    struct entropy *source = context;
    if (source->stop) xnow_link_stop(source->stop);
    memset(out, source->value++, bytes);
    return source->fail;
}

static void initialize(struct xnow_link *root, struct xnow_link *controller,
                       struct entropy *r, struct entropy *c)
{
    memset(root, 0, sizeof *root);
    memset(controller, 0, sizeof *controller);
    assert(!xnow_link_init(root, XNOW_LINK_ROOT, root_mac, controller_mac,
                           authentication, r, random_bytes));
    assert(!xnow_link_init(controller, XNOW_LINK_CONTROLLER, controller_mac, root_mac,
                           authentication, c, random_bytes));
}

static unsigned take(struct xnow_link *link, uint8_t wire[XNOW_LINK_WIRE_BYTES])
{
    unsigned kind = 0;
    uint64_t ticket = 0;
    assert(!xnow_link_take(link, wire, XNOW_LINK_WIRE_BYTES, &kind, &ticket));
    assert(ticket && wire[5] == kind);
    return kind;
}

static uint64_t install(struct xnow_link *link, uint64_t now)
{
    uint64_t serial = 0;
    uint8_t key[16];
    assert(!xnow_link_key_pending(link, &serial, key) && serial);
    assert(!xnow_link_key_installed(link, serial, 1, now));
    assert(xnow_link_key_pending(link, &serial, key) == XNOW_LINK_IGNORED);
    return serial;
}

static void handshake(struct xnow_link *root, struct xnow_link *controller, uint64_t now)
{
    uint8_t wire[XNOW_LINK_WIRE_BYTES], duplicate[XNOW_LINK_WIRE_BYTES];
    assert(!xnow_link_connect(controller, now));
    assert(take(controller, wire) == XNOW_LINK_HELLO);
    memcpy(saved_hello, wire, sizeof saved_hello);
    assert(!xnow_link_receive(root, controller_mac, wire, sizeof wire, now + 1));
    assert(take(root, wire) == XNOW_LINK_OFFER);
    memcpy(duplicate, wire, sizeof wire);
    assert(!xnow_link_receive(controller, root_mac, wire, sizeof wire, now + 2));
    assert(take(controller, wire) == XNOW_LINK_CONFIRM);
    memcpy(saved_confirm, wire, sizeof saved_confirm);
    assert(!xnow_link_receive(controller, root_mac, duplicate, sizeof duplicate, now + 3));
    assert(take(controller, duplicate) == XNOW_LINK_CONFIRM);
    assert(!memcmp(wire, duplicate, sizeof wire));
    assert(xnow_link_receive(root, controller_mac, wire, sizeof wire, now + 4) == XNOW_LINK_PENDING);
    uint64_t root_serial = install(root, now + 5);
    assert(!xnow_link_data_ready(root));
    assert(take(root, wire) == XNOW_LINK_READY);
    /* A lost Ready must be recoverable by the same confirmation, without a
     * second peer-key installation or a reset of packet-number state. */
    assert(!xnow_link_receive(root, controller_mac, duplicate, sizeof duplicate, now + 6));
    assert(take(root, duplicate) == XNOW_LINK_READY);
    assert(!memcmp(wire, duplicate, sizeof wire) && root->key_serial == root_serial);
    assert(xnow_link_receive(controller, root_mac, wire, sizeof wire, now + 7) == XNOW_LINK_PENDING);
    install(controller, now + 8);
    assert(xnow_link_data_ready(controller));
    assert(!memcmp(root->active_key, controller->active_key, 16));
    assert(xnow_link_receive(controller, root_mac, wire, sizeof wire, now + 9) == XNOW_LINK_IGNORED);
    assert(xnow_link_peer_confirmed(root, root_serial + 1) == XNOW_LINK_IGNORED);
    assert(!xnow_link_data_ready(root));
    assert(!xnow_link_peer_confirmed(root, root_serial));
    assert(xnow_link_data_ready(root));
}

static void initial_and_reboot(void)
{
    struct xnow_link root, controller;
    struct entropy r = {1, 0, NULL}, c = {101, 0, NULL};
    initialize(&root, &controller, &r, &c);
    handshake(&root, &controller, 10);
    uint8_t old_key[16];
    memcpy(old_key, root.active_key, 16);
    for (unsigned i = 0; i < 16; i++) printf("%02x", old_key[i]);
    putchar('\n');
    assert(!xnow_link_tick(&root, 10000) && !root.outgoing);
    assert(!xnow_link_tick(&controller, 10000) && !controller.outgoing);
    assert(xnow_link_init(&root, XNOW_LINK_ROOT, root_mac, controller_mac,
                          authentication, &r, random_bytes) == XNOW_LINK_BUSY);
    /* Controller reboot: persisted identity is unchanged, entropy is fresh. */
    xnow_link_stop(&controller);
    memset(&controller, 0, sizeof controller);
    assert(!xnow_link_init(&controller, XNOW_LINK_CONTROLLER, controller_mac, root_mac,
                           authentication, &c, random_bytes));
    handshake(&root, &controller, 10010);
    assert(memcmp(root.active_key, old_key, 16));
    memcpy(old_key, root.active_key, 16);
    /* Root reboot: announcement starts a fresh attempt without prematurely
     * discarding the controller's last installed key. */
    xnow_link_stop(&root);
    memset(&root, 0, sizeof root);
    assert(!xnow_link_init(&root, XNOW_LINK_ROOT, root_mac, controller_mac,
                           authentication, &r, random_bytes));
    uint8_t wire[XNOW_LINK_WIRE_BYTES];
    assert(!xnow_link_announce(&root, 20000));
    assert(take(&root, wire) == XNOW_LINK_ANNOUNCE);
    assert(!xnow_link_receive(&controller, root_mac, wire, sizeof wire, 20001));
    assert(xnow_link_data_ready(&controller));
    assert(take(&controller, wire) == XNOW_LINK_HELLO);
    assert(!xnow_link_receive(&root, controller_mac, wire, sizeof wire, 20002));
    take(&root, wire);
    assert(!xnow_link_receive(&controller, root_mac, wire, sizeof wire, 20003));
    take(&controller, wire);
    assert(xnow_link_receive(&root, controller_mac, wire, sizeof wire, 20004) == XNOW_LINK_PENDING);
    uint64_t serial = install(&root, 20005);
    take(&root, wire);
    assert(xnow_link_receive(&controller, root_mac, wire, sizeof wire, 20006) == XNOW_LINK_PENDING);
    install(&controller, 20007);
    assert(!memcmp(root.active_key, controller.active_key, 16) && memcmp(old_key, root.active_key, 16));
    assert(!xnow_link_peer_confirmed(&root, serial));
    puts("LINK_REBOOTS_PASS");
}

static void replay_and_expiry(void)
{
    struct xnow_link root, controller;
    struct entropy r = {7, 0, NULL}, c = {71, 0, NULL};
    initialize(&root, &controller, &r, &c);
    uint8_t hello[XNOW_LINK_WIRE_BYTES], offer[XNOW_LINK_WIRE_BYTES];
    assert(!xnow_link_connect(&controller, 0));
    take(&controller, hello);
    assert(!xnow_link_receive(&root, controller_mac, hello, sizeof hello, 1));
    take(&root, offer);
    struct xnow_link previous = root;
    uint8_t corrupted[XNOW_LINK_WIRE_BYTES];
    memcpy(corrupted, hello, sizeof corrupted);
    corrupted[80] ^= 1;
    assert(xnow_link_receive(&root, controller_mac, corrupted, sizeof corrupted, 1) == XNOW_LINK_AUTH);
    assert(!memcmp(&previous, &root, sizeof root));
    assert(xnow_link_receive(&root, root_mac, hello, sizeof hello, 1) == XNOW_LINK_INVALID);
    uint64_t serial = 9;
    uint8_t key[16];
    assert(xnow_link_key_pending(&root, &serial, key) == XNOW_LINK_IGNORED);
    assert(!xnow_link_receive(&root, controller_mac, hello, sizeof hello, 2));
    uint8_t duplicate[XNOW_LINK_WIRE_BYTES];
    take(&root, duplicate);
    assert(!memcmp(offer, duplicate, sizeof offer));
    assert(xnow_link_tick(&controller, 4000) == XNOW_LINK_EXPIRED);
    assert(xnow_link_receive(&controller, root_mac, offer, sizeof offer, 4001) == XNOW_LINK_IGNORED);
    assert(xnow_link_tick(&root, 4001) == XNOW_LINK_EXPIRED);
    assert(!xnow_link_connect(&controller, 4010));
    take(&controller, hello);
    assert(!xnow_link_receive(&root, controller_mac, hello, sizeof hello, 4011));
    take(&root, offer);
    assert(!xnow_link_receive(&controller, root_mac, offer, sizeof offer, 4012));
    take(&controller, hello);
    assert(xnow_link_receive(&root, controller_mac, hello, sizeof hello, 4013) == XNOW_LINK_PENDING);
    assert(!xnow_link_key_pending(&root, &serial, key));
    assert(xnow_link_key_installed(&root, serial, 1, 8011) == XNOW_LINK_EXPIRED);
    assert(!xnow_link_data_ready(&root) && root.stopped);
    puts("LINK_REPLAY_EXPIRY_PASS");
}

static void retries_and_stop(void)
{
    struct xnow_link root, controller;
    struct entropy r = {3, 0, NULL}, c = {31, 0, NULL};
    initialize(&root, &controller, &r, &c);
    uint8_t first[XNOW_LINK_WIRE_BYTES], second[XNOW_LINK_WIRE_BYTES];
    unsigned kind;
    uint64_t ticket, old_ticket;
    assert(!xnow_link_connect(&controller, 0));
    assert(!xnow_link_take(&controller, first, sizeof first, &kind, &ticket));
    old_ticket = ticket;
    assert(!xnow_link_resubmit(&controller, ticket));
    assert(!xnow_link_take(&controller, second, sizeof second, &kind, &ticket));
    assert(ticket == old_ticket && !memcmp(first, second, sizeof first));
    assert(!xnow_link_tick(&controller, 700));
    assert(!xnow_link_take(&controller, second, sizeof second, &kind, &ticket));
    assert(ticket != old_ticket && !memcmp(first, second, sizeof first));
    assert(xnow_link_resubmit(&controller, old_ticket) == XNOW_LINK_INVALID);
    assert(!xnow_link_tick(&controller, 1400));
    take(&controller, second);
    assert(!xnow_link_tick(&controller, 2100) && !controller.outgoing);
    assert(xnow_link_tick(&controller, 4000) == XNOW_LINK_EXPIRED);
    assert(xnow_link_resubmit(&controller, ticket) == XNOW_LINK_INVALID);
    assert(!xnow_link_connect(&controller, 5000));
    xnow_link_stop(&controller);
    assert(xnow_link_take(&controller, first, sizeof first, &kind, &ticket) == XNOW_LINK_REVOKED);
    assert(!xnow_link_data_ready(&controller));
    for (unsigned i = 0; i < 32; i++) assert(!controller.authentication[i]);
    initialize(&root, &controller, &r, &c);
    c.stop = &controller;
    assert(xnow_link_connect(&controller, 0) == XNOW_LINK_REVOKED);
    assert(!controller.outgoing);
    puts("LINK_RETRY_STOP_PASS");
}

static void active_replay_and_install_failure(void)
{
    struct xnow_link root, controller;
    struct entropy r = {11, 0, NULL}, c = {111, 0, NULL};
    initialize(&root, &controller, &r, &c);
    handshake(&root, &controller, 0);
    uint8_t old_key[16], wire[XNOW_LINK_WIRE_BYTES], pending_key[16];
    memcpy(old_key, root.active_key, 16);
    uint64_t old_epoch = root.active_serial, serial;
    assert(!xnow_link_receive(&root, controller_mac, saved_hello, sizeof saved_hello, 20));
    assert(xnow_link_data_ready(&root) && !memcmp(root.active_key, old_key, 16));
    assert(take(&root, wire) == XNOW_LINK_OFFER);
    assert(xnow_link_key_pending(&root, &serial, pending_key) == XNOW_LINK_IGNORED);
    /* A captured confirmation for the old transcript cannot commit the new
     * offer or install another key. The live encrypted link remains valid. */
    assert(xnow_link_receive(&root, controller_mac, saved_confirm, sizeof saved_confirm, 21) == XNOW_LINK_IGNORED);
    assert(root.key_serial == old_epoch && !memcmp(root.active_key, old_key, 16));
    assert(xnow_link_receive(&controller, root_mac, wire, sizeof wire, 22) == XNOW_LINK_IGNORED);
    assert(xnow_link_tick(&root, 4020) == XNOW_LINK_EXPIRED);
    assert(xnow_link_data_ready(&root) && root.active_serial == old_epoch);
    assert(!xnow_link_receive(&root, controller_mac, saved_confirm, sizeof saved_confirm, 4021));
    assert(take(&root, wire) == XNOW_LINK_READY);
    assert(root.key_serial == old_epoch);

    assert(!xnow_link_connect(&controller, 4030));
    take(&controller, wire);
    assert(!xnow_link_receive(&root, controller_mac, wire, sizeof wire, 4031));
    take(&root, wire);
    assert(!xnow_link_receive(&controller, root_mac, wire, sizeof wire, 4032));
    take(&controller, wire);
    assert(xnow_link_receive(&root, controller_mac, wire, sizeof wire, 4033) == XNOW_LINK_PENDING);
    assert(!xnow_link_key_pending(&root, &serial, pending_key));
    assert(xnow_link_key_installed(&root, serial, -7, 4034) == XNOW_LINK_INSTALL_FAILED);
    assert(root.stopped && !xnow_link_data_ready(&root));
    assert(xnow_link_peer_confirmed(&root, old_epoch) == XNOW_LINK_REVOKED);
    puts("LINK_ACTIVE_REPLAY_INSTALL_FAILURE_PASS");
}

int main(void)
{
    memset(authentication, 0x5a, sizeof authentication);
    initial_and_reboot();
    replay_and_expiry();
    retries_and_stop();
    active_replay_and_install_failure();
    puts("XNOW_LINK_PASS");
    return 0;
}
