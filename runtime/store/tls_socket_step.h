#ifndef HB_STORE_TLS_SOCKET_STEP_H
#define HB_STORE_TLS_SOCKET_STEP_H
#include "bearssl.h"
#include "deadline.h"
enum hb_tls_socket_result {HB_TLS_SOCKET_WAIT,HB_TLS_SOCKET_PROGRESS,HB_TLS_SOCKET_APPDATA,HB_TLS_SOCKET_CLOSED,
 HB_TLS_SOCKET_TIMEOUT=-1,HB_TLS_SOCKET_CANCELLED=-2,HB_TLS_SOCKET_IO=-3,HB_TLS_SOCKET_PROTOCOL=-4,HB_TLS_SOCKET_EOF=-5,HB_TLS_SOCKET_INPUT=-6,HB_TLS_SOCKET_DEADLINE=-7,HB_TLS_SOCKET_CLOCK=-8};
/* One record-layer I/O step on an already configured engine/socket. Caller
 * handles application buffers, aggregate deadline, trust setup and close.
 * EOF before TLS close-notify is distinct from an orderly engine close. */
int hb_tls_socket_step(br_ssl_engine_context *,int fd,unsigned timeout_ms,volatile int *stop);
/* Reuses one caller-owned deadline. Checks before/after I/O; wait_cap may be0
 * when a scheduler drives both endpoints. Does not reset deadline on progress. */
int hb_tls_socket_deadline_step(br_ssl_engine_context *,int fd,struct hb_transfer_deadline *,unsigned wait_cap_ms,volatile int *stop);
#endif
