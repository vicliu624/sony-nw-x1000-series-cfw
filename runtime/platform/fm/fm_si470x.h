#ifndef HB_FM_SI470X_H
#define HB_FM_SI470X_H
#include <stdint.h>
#include "fm_radio.h"
/* Fixed ARM32 V4L1 wire layout, not the development host's unsigned long ABI. */
struct fm_v4l_tuner {
 int32_t tuner;char name[32];uint32_t low,high,flags;uint16_t mode,signal;
};
struct fm_v4l_capability {char name[32];int32_t type,channels,audios,maxw,maxh,minw,minh;};
#define FM_VIDIOCGCAP 0x803c7601u
#define FM_VIDIOCGTUNER 0xc0347604u
#define FM_VIDIOCGFREQ 0x8004760eu
#define FM_VIDIOCSFREQ 0x4004760fu
#define FM_VIDIOCGAUDIO 0x80287610u
#define FM_VIDIOCSAUDIO 0x40287611u
struct fm_v4l_audio {int32_t audio;uint16_t volume,bass,treble,padding;uint32_t flags;char name[16];uint16_t mode,balance,step,reserved;};
#define FM_VIDIOC_PUTREG 0xc020762au
struct fm_v4l_write_register {uint8_t index,reserved;uint16_t value;uint8_t padding[28];};
#define FM_VIDIOC_GETREG 0xc020762bu
struct fm_v4l_register {uint32_t index;uint16_t values[14];};
/* Caller supplies an already-owned transport. This module never opens a device,
 * switches audio, initializes registers, changes NVP, or grants a hardware lease. */
struct fm_tuner_transport {void *context;int (*control)(void *,uint32_t,void *);int (*wait_ms)(void *,unsigned);};
struct fm_si470x {struct fm_tuner_transport io;struct fm_band band;int verified,identity_verified;int last_tuned;unsigned last_channel;unsigned original_config;int config_dirty;};
int fm_si470x_probe(struct fm_si470x *,struct fm_tuner_transport,struct fm_band);
int fm_si470x_restore_band(struct fm_si470x *);
int fm_si470x_quiesce(struct fm_si470x *);
struct fm_backend fm_si470x_backend(struct fm_si470x *);
#endif
