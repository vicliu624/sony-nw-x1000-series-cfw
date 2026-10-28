#ifndef HB_FM_SESSION_H
#define HB_FM_SESSION_H
#include "../../../sdk/include/x1000/services/audio_route.h"
#include "../../../sdk/include/x1000/services/fm_tuner.h"
/* These callbacks acquire only resources released by Sony's lifecycle. The
 * native platform handoff implementation is not yet qualified or supplied.
 * An open callback failing must release any partially acquired handle itself.
 * A close callback consumes its handle even on error: do not retry close(fd). */
struct fm_session_ops {
 void *context;
 int (*open_audio)(void *,struct fm_audio_transport *);
 int (*close_audio)(void *);
 int (*open_tuner)(void *,struct fm_tuner_transport *);
 int (*close_tuner)(void *);
 int (*cancelled)(void *);
};
struct fm_session {
 struct fm_session_ops ops;struct fm_audio audio;struct fm_si470x tuner;struct fm_radio radio;
 int audio_open,tuner_open,active,close_failed;
};
/* Initialize the object to zero before first use. */
int fm_session_start(struct fm_session *,struct fm_session_ops,struct fm_band,int khz);
int fm_session_stop(struct fm_session *);
int fm_session_update_audio(struct fm_session *);
#endif
