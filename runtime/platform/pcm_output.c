/* X1000 PCM, with the proven FM mixer restoration path reused unchanged. */
#include "pcm_output.h"
#include <errno.h>
#include <string.h>
static int fault(struct hb_pcm_output *p, unsigned stage, int code, int value) {
  p->failed = 1;
  if (!p->fault_stage) {
    p->fault_stage = stage;
    p->fault_code = code < 0 ? -code : code;
    p->fault_value = value;
  }
  return -1;
}
const char *hb_pcm_stage_name(unsigned stage) {
  static const char *names[] = {
      "NONE",      "MIXER OPEN", "CODEC POWER",  "READ ROUTE", "INTERNAL MUTE",
      "DSP OPEN",  "PCM FORMAT", "PCM CHANNELS", "PCM RATE",   "PCM BUFFER",
      "MUTE",      "PCM MIX",    "ADC MIX",      "PCM SOURCE", "HEADPHONES",
      "PCM WRITE", "PCM UNMUTE", "RESTORE",      "STOP"};
  return stage < sizeof(names) / sizeof(names[0]) ? names[stage] : "UNKNOWN";
}
static int stopped(const struct hb_pcm_output *p) {
  return p->stop && *p->stop;
}
static int mixer(void *context, uint32_t command, int32_t *value) {
  struct hb_pcm_output *p = context;
  int r = p->mixer < 0 ? -EBADF
                       : p->io.control(p->io.context, p->mixer, command, value);
  if (r < 0)
    fault(p, p->stage, r, (int)command);
  return r;
}
static int setting(struct hb_pcm_output *p, uint32_t command, uint32_t get,
                   int32_t value) {
  int32_t actual = -1, wanted = value;
  if (mixer(p, command, &value) < 0 || mixer(p, get, &actual) < 0)
    return -1;
  if (command == FM_AUDIO_SET_MUTE)
    return (actual & 31) == (wanted & 31) ? 0
                                          : fault(p, p->stage, EPROTO, actual);
  return actual == wanted ? 0 : fault(p, p->stage, EPROTO, actual);
}
void hb_pcm_init(struct hb_pcm_output *p) {
  memset(p, 0, sizeof(*p));
  p->dsp = p->mixer = -1;
  p->volume = 35;
}
void hb_pcm_volume(struct hb_pcm_output *p, unsigned percent) {
  p->volume = percent > 100 ? 100 : percent;
}
int hb_pcm_close(struct hb_pcm_output *p) {
  p->stage=PCM_CLEANUP;
  int failed = 0;
  if (p->route.dirty && fm_audio_silence(&p->route))
    failed = 1;
  if (p->dsp >= 0) {
    if (p->io.control(p->io.context, p->dsp, HB_PCM_RESET, 0) < 0)
      failed = 1;
    if (p->io.close(p->io.context, p->dsp) < 0)
      failed = 1;
    p->dsp = -1;
  }
  p->head = p->used = 0;
  p->enabled = 0;
  /* Keep the mixer/snapshot available for a bounded caller retry on failure. */
  if (p->route.dirty && fm_audio_restore(&p->route)) {
    p->failed = 1;
    return -1;
  }
  if (p->mixer >= 0) {
    if (p->io.close(p->io.context, p->mixer) < 0)
      failed = 1;
    p->mixer = -1;
  }
  return failed ? -1 : 0;
}
int hb_pcm_start(struct hb_pcm_output *p, struct hb_pcm_ops io,
                 volatile int *stop) {
  if (!p || !io.open || !io.close || !io.control || !io.write || !stop ||
      *stop || p->route.dirty || p->dsp >= 0 || p->mixer >= 0)
    return -1;
  p->io = io;
  p->stop = stop;
  p->failed = 0;
  p->fault_stage = 0;
  p->fault_code = p->fault_value = 0;
  p->head = p->used = 0;
  p->stage = PCM_MIXER_OPEN;
  p->mixer = io.open(io.context, "/dev/sound/mixer", 2);
  if (p->mixer < 0) {
    fault(p, p->stage, p->mixer, 0);
    goto failed;
  }
  p->stage = PCM_CODEC_POWER;
  int32_t power = -1;
  if (mixer(p, FM_AUDIO_GET_CODEC_POWERDOWN, &power) < 0)
    goto failed;
  if (power != 0) {
    fault(p, p->stage, EAGAIN, power);
    goto failed;
  }
  memset(&p->route, 0, sizeof(p->route));
  p->route.io = (struct fm_audio_transport){p, mixer};
  p->stage = PCM_ROUTE_READ;
  const uint32_t gets[] = {FM_AUDIO_GET_MUTE, FM_AUDIO_GET_SOURCE,
                           FM_AUDIO_GET_OUTPUT, FM_AUDIO_GET_PCM,
                           FM_AUDIO_GET_ADC};
  for (unsigned i = 0; i < 5; i++)
    if (mixer(p, gets[i], &p->route.saved[i]) < 0)
      goto failed;
  if (p->route.saved[0] & 0x100) {
    fault(p, PCM_INTERNAL_MUTE, EBUSY, p->route.saved[0]);
    goto failed;
  }
  if (p->route.saved[1] < 0 || p->route.saved[1] > 6 || p->route.saved[2] < 0 ||
      p->route.saved[2] > 3) {
    fault(p, PCM_ROUTE_READ, EINVAL, p->route.saved[1]);
    goto failed;
  }
  if (stopped(p))
    goto failed;
  p->stage = PCM_DSP_OPEN;
  p->dsp = io.open(io.context, "/dev/sound/dsp", 1 | 0x800);
  if (p->dsp < 0) {
    fault(p, p->stage, p->dsp, 0);
    goto failed;
  }
  int values[] = {HB_PCM_S16_LE, 2, HB_PCM_HZ, (8 << 16) | 10};
  const uint32_t commands[] = {HB_PCM_FORMAT, HB_PCM_CHANNELS, HB_PCM_SPEED,
                               HB_PCM_FRAGMENT};
  const unsigned stages[] = {PCM_SET_FORMAT, PCM_SET_CHANNELS, PCM_SET_RATE,
                             PCM_SET_BUFFER};
  for (unsigned i = 0; i < 4; i++) {
    p->stage = stages[i];
    if (stopped(p))
      goto failed;
    int wanted = values[i],
        r = io.control(io.context, p->dsp, commands[i], &values[i]);
    if (r < 0) {
      fault(p, p->stage, r, values[i]);
      goto failed;
    }
    if (i < 3 && values[i] != wanted) {
      fault(p, p->stage, EPROTO, values[i]);
      goto failed;
    }
  }
  p->route.dirty = 1;
  const uint32_t set_cmd[] = {FM_AUDIO_SET_MUTE, FM_AUDIO_SET_PCM,
                              FM_AUDIO_SET_ADC, FM_AUDIO_SET_SOURCE,
                              FM_AUDIO_SET_OUTPUT};
  const uint32_t get_cmd[] = {FM_AUDIO_GET_MUTE, FM_AUDIO_GET_PCM,
                              FM_AUDIO_GET_ADC, FM_AUDIO_GET_SOURCE,
                              FM_AUDIO_GET_OUTPUT};
  const int set_values[] = {31, 0x6464, 0, 0, 0};
  const unsigned set_stages[] = {PCM_SET_MUTE, PCM_SET_MIX, PCM_SET_ADC,
                                 PCM_SET_SOURCE, PCM_SET_OUTPUT};
  for (unsigned i = 0; i < 5; i++) {
    p->stage = set_stages[i];
    if (stopped(p) || setting(p, set_cmd[i], get_cmd[i], set_values[i]))
      goto failed;
  }
  if (stopped(p))
    goto failed;
  p->enabled = 1;
  return 0;
failed:
  if (!p->fault_stage)
    fault(p, stopped(p) ? PCM_STOP : p->stage, stopped(p) ? ECANCELED : EIO, 0);
  hb_pcm_close(p);
  return -1;
}
static int unmute(struct hb_pcm_output *p) {
  if (p->route.playing)
    return 0;
  p->stage = PCM_UNMUTE;
  int32_t value = -1;
  if (stopped(p) || mixer(p, FM_AUDIO_GET_MUTE, &value) < 0 ||
      ((value ^ p->route.saved[0]) & 0x100) ||
      setting(p, FM_AUDIO_SET_MUTE, FM_AUDIO_GET_MUTE, 9))
    return -1;
  /* ADC and ADC mix stay muted; PCM, DAC and headphone output are enabled. */
  p->route.playing = 1;
  return 0;
}
int hb_pcm_flush(struct hb_pcm_output *p) {
  if (!p->enabled || p->failed)
    return -1;
  for (unsigned i = 0; p->used && i < 16 && !stopped(p); i++) {
    unsigned n = HB_PCM_QUEUE - p->head;
    if (n > p->used)
      n = p->used;
    p->stage = PCM_WRITE;
    long r = p->io.write(p->io.context, p->dsp, p->queue + p->head, n);
    if (r == -EINTR)
      continue;
    if (r == -EAGAIN || r == -EWOULDBLOCK)
      return 0;
    if (r <= 0 || (unsigned long)r > n) {
      fault(p, PCM_WRITE, r < 0 ? (int)r : EIO, 0);
      goto failed;
    }
    p->head = (p->head + (unsigned)r) % HB_PCM_QUEUE;
    p->used -= (unsigned)r;
    if (unmute(p))
      goto failed;
  }
  return 0;
failed:
  if (!p->fault_stage)
    fault(p, stopped(p) ? PCM_STOP : PCM_UNMUTE, stopped(p) ? ECANCELED : EIO,
          0);
  fm_audio_silence(&p->route);
  return -1;
}
int hb_pcm_submit_u8(void *context, const unsigned char *samples, unsigned n) {
  struct hb_pcm_output *p = context;
  if (!p || !samples || (n & 1) || n > HB_PCM_QUEUE / 2 || !p->enabled ||
      p->failed || stopped(p))
    return -1;
  if (hb_pcm_flush(p))
    return -1;
  if (n * 2 > HB_PCM_QUEUE - p->used) {
    p->dropped++;
    return 0;
  }
  for (unsigned i = 0; i < n; i++) {
    int value = ((int)samples[i] - 128) * 256 * (int)p->volume / 100;
    unsigned at = (p->head + p->used) % HB_PCM_QUEUE;
    p->queue[at] = (uint8_t)value;
    p->queue[(at + 1) % HB_PCM_QUEUE] = (uint8_t)((uint16_t)value >> 8);
    p->used += 2;
  }
  return hb_pcm_flush(p);
}
int hb_pcm_pause(struct hb_pcm_output *p) {
  if (!p->enabled)
    return 0;
  int failed = fm_audio_silence(&p->route) < 0;
  if (p->io.control(p->io.context, p->dsp, HB_PCM_RESET, 0) < 0)
    failed = 1;
  p->head = p->used = 0;
  if (failed)
    p->failed = 1;
  return failed ? -1 : 0;
}
