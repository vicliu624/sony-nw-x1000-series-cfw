#ifndef XNOW_RADIO_PACKET_H
#define XNOW_RADIO_PACKET_H
#include <stdint.h>
#define XNOW_RADIO_PACKET_CAPACITY 1760u
#define XNOW_RADIO_PACKET_HEADROOM 32u
#define XNOW_RADIO_ACTION_SUBTYPE 13u
/* Radio protocol results, not Linux errno or native SDK result values. */
enum xnow_radio_packet_result {
    XNOW_RADIO_PACKET_OK = 0,
    XNOW_RADIO_PACKET_REJECTED = -1,
    XNOW_RADIO_PACKET_BUSY = -2,
    XNOW_RADIO_PACKET_NOMEM = -3,
    XNOW_RADIO_PACKET_IDENTITY = -4,
    XNOW_RADIO_PACKET_ARGUMENT = -5,
    XNOW_RADIO_PACKET_OPERATION = -6,
    XNOW_RADIO_PACKET_TICKET = -7
};
enum { XNOW_RADIO_MANAGEMENT_QUEUE = 0x1571d, XNOW_RADIO_PACKET_FREE = 0x1360 };
int xnow_radio_pool_ready(void);
int xnow_radio_packet_valid(uint32_t);
int xnow_radio_packet_allocate(uint32_t *);
int xnow_radio_packet_release(uint32_t);

/* Same original management queue/notification/free as d800. The optional
 * tracking callback runs before free exposes a rejected block for reuse. */
__attribute__((always_inline)) static inline int
xnow_radio_packet_submit(uint32_t packet, void (*before_reject_free)(uint32_t)) {
    typedef int (*stock_packet_operation)(void *);
    int queued =
        ((stock_packet_operation)(uintptr_t)XNOW_RADIO_MANAGEMENT_QUEUE)((void *)(uintptr_t)packet);
    if (queued != 1)
        return 0;
    if (before_reject_free)
        before_reject_free(packet);
    (void)((stock_packet_operation)(uintptr_t)XNOW_RADIO_PACKET_FREE)((void *)(uintptr_t)packet);
    return XNOW_RADIO_PACKET_REJECTED;
}
#endif
