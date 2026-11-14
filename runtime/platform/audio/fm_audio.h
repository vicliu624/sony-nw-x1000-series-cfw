#ifndef HB_FM_AUDIO_H
#define HB_FM_AUDIO_H
#include <stdint.h>
/* Commands matched to the pinned Japanese kernel, not host OSS headers. */
#define FM_AUDIO_GET_CODEC_POWERDOWN 0x8004610eu
#define FM_AUDIO_SET_MUTE 0x40046101u
#define FM_AUDIO_GET_MUTE 0x80046102u
#define FM_AUDIO_SET_SOURCE 0x40046103u
#define FM_AUDIO_GET_SOURCE 0x80046104u
#define FM_AUDIO_SET_OUTPUT 0x40046105u
#define FM_AUDIO_GET_OUTPUT 0x80046106u
#define FM_AUDIO_SET_PCM 0xc0044d04u
#define FM_AUDIO_GET_PCM 0x80044d04u
#define FM_AUDIO_SET_ADC 0xc0044d0au
#define FM_AUDIO_GET_ADC 0x80044d0au
struct fm_audio_transport {void *context;int (*control)(void *,uint32_t,int32_t *);};
struct fm_audio {struct fm_audio_transport io;int32_t saved[5];int dirty,playing,restore_failed;};
/* Requires caller-owned audio transport and completed Sony audio handoff.
 * No device opening or inference that handoff succeeded is performed here. */
int fm_audio_prepare(struct fm_audio *,struct fm_audio_transport);
int fm_audio_play(struct fm_audio *);
int fm_audio_silence(struct fm_audio *);
int fm_audio_restore(struct fm_audio *);
#endif
