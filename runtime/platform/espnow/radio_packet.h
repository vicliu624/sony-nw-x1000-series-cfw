#ifndef XNOW_RADIO_PACKET_H
#define XNOW_RADIO_PACKET_H
#include <stdint.h>
#define XNOW_RADIO_PACKET_CAPACITY 1760u
int xnow_radio_pool_ready(void);
int xnow_radio_packet_valid(uint32_t);
int xnow_radio_packet_allocate(uint32_t *);
int xnow_radio_packet_release(uint32_t);
#endif
