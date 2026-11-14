#ifndef XNOW_OWNER_RUNTIME_H
#define XNOW_OWNER_RUNTIME_H
#include "xnow_owner_gate.h"
#include "xnow_owner_stream.h"
#include "xnow_owner_transport.h"
/* Experimental SDK owner loop, not a qualified device app. Every dependency is
 * explicitly constructed before radio startup. Gate is cooperative exclusion,
 * not proof of original Sony/APF/USB ownership; qualified platform guards still
 * belong in full_control_options. Caller ignores SIGPIPE and owns signal setup.
 * While step is pending/uncertain caller must keep the owner/foreground alive. */
struct xnow_owner_receive_stats {
 uint32_t decoded,forwarded,sideband,gated;
 uint32_t auth,replay,format,refused,other_error;
};
struct xnow_owner_runtime {
 struct xnow_full_control *control;struct xnow_owner_gate *gate;
 struct xnow_owner_stream *stream;struct xnow_owner_commands *commands;
 void *context;
 int (*prepare)(void *,struct xnow_endpoint *,const uint8_t[6]);
 int (*close_data)(void *);
 int writer,pid,prepared,cleaned,released,done,fault,application_failure;
 uint64_t writer_device,writer_inode;uint8_t cookie[16];
 unsigned dropped,application_origin;uint8_t receive[XNOW_ESPNOW_V2_MAX];
 /* One authenticated/validated application record may share receive[] while
  * an admitted command or its reply progresses. No second data buffer. */
 struct xnow_full_received received;
 unsigned receive_pending;
 struct xnow_owner_transport transport;
 struct xnow_owner_receive_stats receive_stats;
 unsigned started,transport_bound,transport_stopped,stepping;
};
#ifdef __cplusplus
extern "C" {
#endif
/* Gate/stream open, fresh initialized controller, no RF started yet. Commands
 * must back stream and are rebound to the actual controller. Controller lease
 * must use this exact gate via xnow_owner_gate_radio_valid. Writer/cookie are
 * the inherited capability from xnow_managed_process_inherited(), transferred
 * exclusively to this owner (all UI/loader copies must be closed).
 * close_data must close all user-storage FDs and move cwd off the user mount.
 * prepare attaches security/journals before any app command if encryption is
 * enabled; may be NULL only for a controller with encrypted_limit=0. A callback
 * may request cooperative stop and return0: no later data producer runs, and
 * canceled preparation does not need to finish crypto configuration. Nonzero
 * callback errors are retained even when stop is also requested. close_data
 * must handle partially prepared state after controller retirement. */
int xnow_owner_runtime_init(struct xnow_owner_runtime *,struct xnow_full_control *,struct xnow_owner_gate *,struct xnow_owner_stream *,struct xnow_owner_commands *,int writer,const uint8_t cookie[16],void *,int (*prepare)(void *,struct xnow_endpoint *,const uint8_t[6]),int (*close_data)(void *));
/* Optional negotiation seam, configured once before the first step. It grants
 * no radio authority. Caller owns context through independent radio retirement.
 * Holding input never invents a PENDING command ACK; pipe HUP and stop-token
 * observation remain live. One queued RX event is processed before admitting
 * an app request; transport readiness is checked again after that event.
 * An application RX is retained for one command opportunity, then delivered
 * before another RX is read. Stop discards the retained record.
 * Existing runtimes without a transport are unchanged. */
int xnow_owner_runtime_transport(struct xnow_owner_runtime *,const struct xnow_owner_transport *);
/* OK only after controller finished, data closed, stream/gate closed and a
 * complete restoration notification+writer close. Pending is not exit permission.
 * UNCERTAIN is retained: no timed kill, fabricated DONE or implicit retry. */
int xnow_owner_runtime_step(struct xnow_owner_runtime *);
/* Same stream/gate/receipt lifecycle, with an explicit controller-step policy.
 * No implicit radio-off behavior is added to ordinary runtime_step(). */
int xnow_owner_runtime_step_with_controller(struct xnow_owner_runtime *,void *,
                                           int (*step)(void *,struct xnow_full_control *));
#ifdef __cplusplus
}
#endif
#endif
