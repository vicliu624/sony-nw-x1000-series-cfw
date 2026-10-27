#ifndef HB_HOME_KEY_H
#define HB_HOME_KEY_H
struct hb_home_key { int fd; unsigned pressed; };
void hb_home_key_open(struct hb_home_key *);
/* Non-exclusive read: 1 on HOME press (repeat/release ignored), 0 otherwise, -1 if unavailable. */
int hb_home_key_poll(struct hb_home_key *);
int hb_home_key_close(struct hb_home_key *);
#endif
