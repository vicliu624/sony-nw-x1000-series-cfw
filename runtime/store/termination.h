#ifndef HB_STORE_TERMINATION_H
#define HB_STORE_TERMINATION_H
/* Single-process external app scope. Handler only sets a sig_atomic_t token;
 * no I/O, cleanup or exit inside the handler. Restores the previous handler
 * pointer, not an arbitrary prior sigaction mask/flags. Use only in an owned
 * external app process, not injected into Sony processes. No USB policy. */
int hb_store_termination_begin(void);
int hb_store_termination_end(void);
volatile int *hb_store_termination_flag(void);
#endif
