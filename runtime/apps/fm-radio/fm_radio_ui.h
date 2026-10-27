#ifndef HB_FM_RADIO_UI_H
#define HB_FM_RADIO_UI_H
#include "fm_radio.h"
enum fm_page {FM_MAIN,FM_FAVORITES,FM_STATIONS,FM_INPUT,FM_ERROR};
struct fm_ui {struct fm_radio *radio;enum fm_page page;unsigned offset;char input[9];unsigned length;int input_error;int simulated;int storage_notice;int touch_down,touch_x,touch_y;};
void fm_ui_init(struct fm_ui *,struct fm_radio *);
/* Return 1 requests exit; other taps alter only app-owned state. */
int fm_ui_tap(struct fm_ui *,int x,int y);
int fm_parse_mhz(const char *,int *khz);
#endif
