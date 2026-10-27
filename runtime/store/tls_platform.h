#ifndef HB_STORE_TLS_PLATFORM_H
#define HB_STORE_TLS_PLATFORM_H
enum hb_tls_platform_result { HB_TLS_PLATFORM_OK,HB_TLS_PLATFORM_IO=-1,HB_TLS_PLATFORM_CANCELLED=-2,HB_TLS_PLATFORM_TIME=-3 };
struct hb_tls_time {unsigned days,seconds;unsigned long long unix_seconds;};
/* Reads exactly 48 bytes from a character /dev/urandom, no fallback or logging.
 * On failure/cancel, clears the entire output. Does not qualify boot entropy. */
int hb_tls_seed(unsigned char out[48],volatile int *stop);
/* Original signed 32-bit time() range, converted to BearSSL's year-zero epoch.
 * Failure leaves output unchanged. No fabricated date or RTC repair. */
int hb_tls_current_time(struct hb_tls_time *);
#endif
