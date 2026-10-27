#ifndef HB_TERMINAL_FIREWALL_H
#define HB_TERMINAL_FIREWALL_H
typedef int (*hb_terminal_firewall_run)(char *const []);
struct hb_terminal_firewall {int active;};
int hb_terminal_firewall_open(struct hb_terminal_firewall *,hb_terminal_firewall_run);
int hb_terminal_firewall_close(struct hb_terminal_firewall *,hb_terminal_firewall_run);
int hb_terminal_firewall_native(char *const []);
#endif
