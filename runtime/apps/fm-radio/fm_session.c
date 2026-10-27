#include "fm_session.h"
static int cancelled(struct fm_session *s){return s->ops.cancelled&&s->ops.cancelled(s->ops.context);}
int fm_session_stop(struct fm_session *s){
 if(!s)return -1;
 int failed=0;
 /* Teardown discards an incomplete scan and closes the tuner; do not issue
  * another RF tune just to restore the scan origin while USB/stop is pending. */
 s->radio.scanning=0;s->radio.pending_count=0;
 if(fm_audio_silence(&s->audio)<0)failed=1;
 if(s->tuner_open){
  if(s->tuner.identity_verified&&(fm_si470x_quiesce(&s->tuner)<0||fm_si470x_restore_band(&s->tuner)<0)){s->active=0;return -1;}
  s->tuner_open=0;if(s->ops.close_tuner(s->ops.context)<0)s->close_failed=1;
 }
 s->tuner.verified=0;s->tuner.last_tuned=0;s->active=0;
 if(fm_audio_restore(&s->audio)<0)failed=1;
 /* Keep the audio handle while restoration needs a retry. Never claim release
  * or allow another start with unresolved saved state. */
 if(s->audio_open&&!s->audio.dirty){s->audio_open=0;if(s->ops.close_audio(s->ops.context)<0)s->close_failed=1;}
 return failed||s->close_failed?-1:0;
}
int fm_session_start(struct fm_session *s,struct fm_session_ops ops,struct fm_band band,int khz){
 if(!s||s->active||s->audio_open||s->tuner_open||s->audio.dirty||s->close_failed||
    !ops.open_audio||!ops.close_audio||!ops.open_tuner||!ops.close_tuner)return -1;
 s->ops=ops;if(cancelled(s))return -1;struct fm_audio_transport audio;struct fm_tuner_transport tuner;
 if(ops.open_audio(ops.context,&audio)<0)return -1;
 s->audio_open=1;
 /* Capture original mixer settings before opening the tuner: its open path
  * itself changes ADC mute state and initializes hardware. */
 if(cancelled(s)||fm_audio_prepare(&s->audio,audio)<0)goto fail;
 if(cancelled(s)||ops.open_tuner(ops.context,&tuner)<0)goto fail;
 s->tuner_open=1;
 if(cancelled(s)||fm_si470x_probe(&s->tuner,tuner,band)<0||
    fm_init(&s->radio,band,fm_si470x_backend(&s->tuner))<0||
    fm_tune(&s->radio,khz)<0||cancelled(s)||fm_audio_play(&s->audio)<0||cancelled(s))goto fail;
 s->active=1;return 0;
fail:
 fm_session_stop(s);return -1;
}

/* Call after a UI action or scan step. Scanning and failed tuning never enable
 * output. Tuner-side unmute may clear ADC mix mute, so silence keeps DAC and
 * external output muted as well until scanning has ended successfully. */
int fm_session_update_audio(struct fm_session *s){
 if(!s||!s->active)return -1;
 if(s->radio.scanning||s->radio.error||cancelled(s)){
  return s->audio.playing?fm_audio_silence(&s->audio):0;
 }
 return s->audio.playing?0:fm_audio_play(&s->audio);
}
