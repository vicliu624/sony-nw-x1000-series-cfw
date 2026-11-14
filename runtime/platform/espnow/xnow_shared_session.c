#include "xnow_shared_session.h"

int xnow_shared_session_start(struct xnow_shared_session *session,struct xnow_sd8686_full *radio,
                              const struct xnow_word_io *io,unsigned limit,void *context,
                              int (*random)(void *,uint8_t[4])) {
    if (!session || session->radio || session->fault || !radio || !io || !random ||
        limit > XNOW_ENCRYPTED_PEER_LIMIT || io->context != &radio->boundary ||
        !radio->boundary.profile) return XNOW_ARGUMENT;
    unsigned channel;
    int result = xnow_sd8686_full_channel_get(radio,&channel);
    if (result) return result;
    result = xnow_full_open(&session->transport,io,&radio->boundary.profile->layout);
    if (result && !session->transport.fault) return result;
    session->radio = radio;
    if (!result) result = xnow_sd8686_full_enable_spans(radio,&session->transport);
    if (!result) result = xnow_endpoint_init(&session->endpoint,&session->transport,channel,limit,context,random);
    if (result) {
        session->fault = 1;
        return XNOW_UNCERTAIN;
    }
    return 0;
}

int xnow_shared_session_check_channel(struct xnow_shared_session *session) {
    if (!session || !session->radio) return XNOW_ARGUMENT;
    if (session->fault) return XNOW_UNCERTAIN;
    if (session->stopping) return XNOW_PENDING;
    unsigned channel;
    int result = xnow_sd8686_full_channel_get(session->radio,&channel);
    if (result || channel != session->endpoint.channel) {
        session->stopping = session->endpoint.stopping = 1;
        return result ? result : XNOW_ENDPOINT_CHANNEL;
    }
    return 0;
}

int xnow_shared_session_stop_step(struct xnow_shared_session *session) {
    if (!session || !session->radio) return XNOW_ARGUMENT;
    if (session->fault) return XNOW_UNCERTAIN;
    session->stopping = 1;
    int result = xnow_endpoint_stop_step(&session->endpoint);
    if (result && result != XNOW_PENDING) session->fault = 1;
    if (!result) *session = (struct xnow_shared_session){0};
    return result;
}
