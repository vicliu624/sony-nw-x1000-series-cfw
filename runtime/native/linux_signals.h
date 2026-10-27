#ifndef HB_LINUX_SIGNALS_H
#define HB_LINUX_SIGNALS_H
/* One stop token per process. Handlers only set the flag; the normal control
   loop closes resources and reaps children. Old-kernel ABI stays in this module. */
int hb_stop_signals_install(volatile int *stop);
/* Child-only: do not carry the launcher flag handler across the exec window. */
int hb_stop_signals_reset_for_exec(void);
#endif
