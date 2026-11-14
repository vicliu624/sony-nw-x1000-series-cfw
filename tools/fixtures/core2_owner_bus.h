#ifndef TEST_CORE2_OWNER_BUS_H
#define TEST_CORE2_OWNER_BUS_H
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
void bus_root_start(const uint8_t auth[32], const uint8_t pmk[16], const uint8_t peer[6]);
void bus_root_mac(uint8_t out[6]);
int bus_root_step(uint64_t now, uint8_t *action, size_t capacity, size_t *bytes);
void bus_root_inject(const uint8_t *action, size_t bytes);
void bus_root_complete(void);
size_t bus_root_read(void *output, size_t capacity);
void bus_root_send(unsigned token, const char *data);
int bus_root_ready(void);
unsigned bus_root_installs(void);
void bus_root_stop(unsigned producer_active);
void bus_root_producer_done(void);
int bus_root_finished(void);
void bus_root_finish(void);
#ifdef __cplusplus
}
#endif
#endif
