#ifndef X1000_FRONTEND_H
#define X1000_FRONTEND_H
#define HB_MAX_APPS 32
#define HB_SCREEN_W 240
#define HB_SCREEN_H 432
#define HB_ROWS 6
#define HB_LIST_TOP 48
#define HB_ROW_HEIGHT 52
#define HB_LIST_BOTTOM (HB_LIST_TOP + HB_ROWS * HB_ROW_HEIGHT)
#define HB_NAV_TOP 384
/* Operations are requests to the native adapter, not direct device access. */
enum hb_phase { HB_LIST, HB_RUNNING, HB_STOPPING, HB_RETURNING, HB_ERROR };
enum hb_action { HB_NONE, HB_REDRAW, HB_RELEASE_AND_LAUNCH, HB_TERMINATE_CHILD, HB_RELEASE_AND_RETURN, HB_REACQUIRE_AND_REDRAW };
struct hb_frontend { int count,selected,page,phase,child_active; };
struct hb_touch { unsigned raw_x,raw_y,x,y; int down,in_bounds; };
int hb_touch_decode(const unsigned char packet[11],struct hb_touch *out);
void hb_frontend_init(struct hb_frontend *s,int count);
int hb_frontend_tap(struct hb_frontend *s,int x,int y);
int hb_frontend_swipe(struct hb_frontend *,int,int,int,int);
int hb_frontend_child_exit(struct hb_frontend *s);
int hb_frontend_launch_failed(struct hb_frontend *s);
int hb_frontend_native_stop(struct hb_frontend *s);
int hb_frontend_resources_released(struct hb_frontend *s,int ok);
#endif
