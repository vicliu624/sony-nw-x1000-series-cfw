#ifndef HB_EMU_PCM_OUTPUT_H
#define HB_EMU_PCM_OUTPUT_H
#include "../apps/fm-radio/fm_audio.h"
#include <stdint.h>
#define HB_PCM_RESET 0x00005000u
#define HB_PCM_SPEED 0xc0045002u
#define HB_PCM_FORMAT 0xc0045005u
#define HB_PCM_CHANNELS 0xc0045006u
#define HB_PCM_FRAGMENT 0xc004500au
#define HB_PCM_S16_LE 0x10
#define HB_PCM_HZ 22050
#define HB_PCM_QUEUE 8192u
/* All operations return negative errno on failure; no raw kernel/MMIO calls. */
struct hb_pcm_ops {
  void *context;
  int (*open)(void *, const char *, int);
  int (*close)(void *, int);
  int (*control)(void *, int, uint32_t, void *);
  long (*write)(void *, int, const void *, unsigned);
};
enum hb_pcm_stage {
  PCM_IDLE,
  PCM_MIXER_OPEN,
  PCM_CODEC_POWER,
  PCM_ROUTE_READ,
  PCM_INTERNAL_MUTE,
  PCM_DSP_OPEN,
  PCM_SET_FORMAT,
  PCM_SET_CHANNELS,
  PCM_SET_RATE,
  PCM_SET_BUFFER,
  PCM_SET_MUTE,
  PCM_SET_MIX,
  PCM_SET_ADC,
  PCM_SET_SOURCE,
  PCM_SET_OUTPUT,
  PCM_WRITE,
  PCM_UNMUTE,
  PCM_CLEANUP,
  PCM_STOP
};
struct hb_pcm_output {
  struct hb_pcm_ops io;
  struct fm_audio route;
  volatile int *stop;
  int dsp, mixer, failed, enabled;
  unsigned head, used, volume, dropped;
  unsigned stage, fault_stage;
  int fault_code, fault_value;
  uint8_t queue[HB_PCM_QUEUE];
};
const char *hb_pcm_stage_name(unsigned);
void hb_pcm_init(struct hb_pcm_output *);
int hb_pcm_start(struct hb_pcm_output *, struct hb_pcm_ops, volatile int *);
int hb_pcm_submit_u8(void *, const unsigned char *, unsigned);
int hb_pcm_flush(struct hb_pcm_output *);
int hb_pcm_pause(struct hb_pcm_output *);
int hb_pcm_close(struct hb_pcm_output *);
void hb_pcm_volume(struct hb_pcm_output *, unsigned);
struct hb_pcm_ops hb_pcm_posix_ops(void);
#endif
