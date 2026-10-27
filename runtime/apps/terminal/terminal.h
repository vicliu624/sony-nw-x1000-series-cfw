#ifndef HB_TERMINAL_H
#define HB_TERMINAL_H
#define HB_TERM_PORT 2323
/* Native implementation; never invoked by --help/--version/--selftest. */
int hb_terminal_open(const char *directory, unsigned port, int test_mode);
void hb_terminal_tick(void);
int hb_terminal_close(void);
const char *hb_terminal_code(void);
const char *hb_terminal_status(void);
void hb_terminal_addresses(char out[3][24]);
unsigned hb_terminal_uid(void);
unsigned hb_terminal_gid(void);
int hb_terminal_protocol_selftest(void);
#endif
