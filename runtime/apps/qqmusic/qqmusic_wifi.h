#ifndef QQMUSIC_WIFI_H
#define QQMUSIC_WIFI_H
#include <stdint.h>
struct qq_wifi_session {const char *helper;volatile int *stop;int pid,read_fd,control_fd,phase,error,cancelling,wait_status,lease_fd;unsigned used;unsigned char packet[12];uint64_t deadline,route_checked;};
void qq_wifi_init(struct qq_wifi_session *,const char *,volatile int *);
int qq_wifi_ensure(void *);
/* Invalidate preparation promptly; a later ensure waits for drain/reap before
 * starting another attempt. Full close drains before returning to Sony. */
void qq_wifi_cancel(void *);
void qq_wifi_close(void *);
/* Kernel route/address check; not an Internet or QQ authentication test. */
int qq_wifi_route_ready(void);
/* Only original RAM-backed /tmp IPC is permitted for the stock manager. */
int qq_wifi_ipc_guard(void);
#define QQ_WIFI_MAGIC 0x514e4554u
#endif
