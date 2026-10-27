#ifndef HB_STORE_SOCKET_STEP_H
#define HB_STORE_SOCKET_STEP_H
enum hb_socket_result {HB_SOCKET_ERROR=-1,HB_SOCKET_RETRY=-2,HB_SOCKET_TIMEOUT=-3,HB_SOCKET_CANCELLED=-4};
/* One bounded poll plus nonblocking recv/send; never changes descriptor flags.
 * Returns byte count (read0=EOF) or enum error. Up to64KiB, timeout0..1000ms.
 * Caller owns TLS EOF rules, aggregate deadline, retries and descriptor close. */
int hb_socket_read_step(int fd,unsigned char *,unsigned capacity,unsigned timeout_ms,volatile int *stop);
int hb_socket_write_step(int fd,const unsigned char *,unsigned bytes,unsigned timeout_ms,volatile int *stop);
#endif
