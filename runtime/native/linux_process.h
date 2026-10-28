#ifndef HB_LINUX_PROCESS_H
#define HB_LINUX_PROCESS_H
/* Linux process operations. Errors are negative errno values, as provided by
   the existing syscall ABI adapter; no Sony binary addresses are used. */
/* Bind this child to its expected parent lifetime; race-checked. */
int hb_linux_bind_parent_stop(long expected_parent);
long hb_linux_fork(void);
int hb_linux_prepare_child(void);
long hb_linux_set_group(long pid, long group);
long hb_linux_change_directory(const char *directory);
long hb_linux_execute(const char *path, char *const arguments[], char *const environment[]);
void hb_linux_exit(int status) __attribute__((noreturn));
long hb_linux_wait_nohang(long pid, int *status);
long hb_linux_terminate(long pid);
long hb_linux_kill(long pid);
void hb_linux_wait_tick(void);
#endif
