#ifndef HB_FM_RADIO_H
#define HB_FM_RADIO_H
#define FM_MAX_STATIONS 64
#define FM_NAME_BYTES 48
/* Frequencies are integer kHz. Limits describe a backend, never unlock hardware. */
struct fm_band { int low, high, step; };
struct fm_station { int khz, strength; char name[FM_NAME_BYTES]; };
struct fm_backend {
 void *context;
 int (*tune)(void *, int khz);
 /* 1 valid station, 0 no station, negative failure. No invented RSSI. */
 int (*sample)(void *, int *strength);
};
struct fm_radio {
 struct fm_band band;
 struct fm_backend backend;
 int frequency, scanning, next, restore, threshold, error;
 struct fm_station favorites[FM_MAX_STATIONS], stations[FM_MAX_STATIONS];
 struct fm_station pending[FM_MAX_STATIONS];
 unsigned favorite_count, station_count, pending_count;
};
int fm_init(struct fm_radio *, struct fm_band, struct fm_backend);
int fm_tune(struct fm_radio *, int khz);
int fm_step(struct fm_radio *, int direction);
int fm_favorite(struct fm_radio *, const char *name);
int fm_remove_favorite(struct fm_radio *, unsigned index);
int fm_scan_start(struct fm_radio *, int threshold);
/* At most one tuning/sample pair per call; caller supplies settling time. */
int fm_scan_tick(struct fm_radio *);
int fm_scan_cancel(struct fm_radio *);
#endif
