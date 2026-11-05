#ifndef XNOW_CLIENT_H
#define XNOW_CLIENT_H
#include <stddef.h>
#include <stdint.h>
#define XNOW_CLIENT_PAYLOAD_MAX 1470u
#define XNOW_CLIENT_FRAME_MAX (32u+XNOW_CLIENT_PAYLOAD_MAX)
enum {XNOW_CLIENT_OK=0,XNOW_CLIENT_AGAIN=1,XNOW_CLIENT_PENDING=2,
 XNOW_CLIENT_IO=-1,XNOW_CLIENT_IDENTITY=-2,XNOW_CLIENT_ARGUMENT=-3,
 XNOW_CLIENT_UNCERTAIN=-4,XNOW_CLIENT_PROTOCOL=-20};
enum {XNOW_CLIENT_ACK=1,XNOW_CLIENT_TX=2,XNOW_CLIENT_RX=3};
enum {XNOW_CLIENT_BROADCAST=1u,XNOW_CLIENT_AUTHENTICATED=2u};
struct xnow_client_peer {uint8_t address[6],lmk[16],channel,version,encrypt;};
struct xnow_client_event {
 uint32_t kind,request,operation;int32_t result;
 uint8_t address[6],version,elements,random[4];
 uint32_t flags,stock_status,raw_fields;size_t bytes;
};
/* Fresh static/heap storage. One serialized worker/process, no fork reuse.
 * This client contains no device access, loader, driver or default endpoint. */
struct xnow_client {
 int input,output,pid;unsigned used,fault,event_ready,awaiting,stopping;
 uint64_t device[2],inode[2];uint32_t serial,pending,operation,tx_request;
 uint8_t tx_destination[6],pending_destination[6];
 size_t request_bytes,sent,received,needed;
 uint8_t request[XNOW_CLIENT_FRAME_MAX],response[XNOW_CLIENT_FRAME_MAX];
 struct xnow_client_event event;
};
#ifdef __cplusplus
extern "C" {
#endif
/* Already authorized, distinct nonblocking FIFO descriptions: owner->client
 * readonly input, client->owner writeonly output. Success transfers ownership
 * of both supplied FDs; failure leaves them untouched. New duplicates are
 * CLOEXEC. The manager must close all unintended copies. No radio starts here. */
int xnow_client_adopt(struct xnow_client *,int input,int output);
/* OK queues exactly one request and commits its generated ID. PENDING means
 * another command/one-peer send is pending: no new request or ID was committed.
 * No automatic replay, reconnect or token wrap. Temporary peer LMKs are wiped
 * after their complete write or on local failure; callers wipe their own copy. */
int xnow_client_peer(struct xnow_client *,const struct xnow_client_peer *,int modify,uint32_t *request);
int xnow_client_delete(struct xnow_client *,const uint8_t address[6],uint32_t *request);
int xnow_client_send(struct xnow_client *,const uint8_t destination[6],const void *,size_t,uint32_t *request);
int xnow_client_request_stop(struct xnow_client *,uint32_t *request);
/* One bounded nonblocking read OR write. OK means a staged event is available.
 * Peer/API results are event.result; TX completion is not an application ACK.
 * Too-small take capacity preserves event and outputs for an explicit retry. */
int xnow_client_step(struct xnow_client *);
int xnow_client_take(struct xnow_client *,struct xnow_client_event *,void *,size_t);
/* Local detach only. Pipe EOF makes the provider request cleanup, but is not a
 * hardware-off/restoration receipt. Wait for the separate system lifecycle
 * result before claiming the radio is available or powered off. */
int xnow_client_close(struct xnow_client *);
#ifdef __cplusplus
}
#endif
#endif
