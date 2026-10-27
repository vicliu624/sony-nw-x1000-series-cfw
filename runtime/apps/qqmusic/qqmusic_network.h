#ifndef HB_QQMUSIC_NETWORK_H
#define HB_QQMUSIC_NETWORK_H
#include "qqmusic_runtime.h"
#include "qqmusic_tls.h"
#include "../../store/resolver.h"
#include "../../store/connect_step.h"
#include "../../store/tls_platform.h"
enum qq_network_phase {QQ_NET_EMPTY,QQ_NET_DNS,QQ_NET_CONNECT,QQ_NET_TLS,QQ_NET_DONE,QQ_NET_FAILED};
struct qq_network_config {
 const br_x509_trust_anchor *anchors;size_t anchor_count;
 const struct ares_options *dns_options;int dns_mask;
 unsigned port,timeout_ms,poll_ms;
 /* NULL uses the stock-compatible /dev/urandom and time adapters. No fallback. */
 int (*seed)(unsigned char out[48],volatile int *);
 int (*time)(struct hb_tls_time *);
};
struct qq_network {
 struct qq_network_config config;struct qq_runtime_ops operations;
 void *application;int (*material)(void *,struct qq_runtime_material *);int (*stock)(void *);
 struct hb_dns_query dns;struct hb_connect connection;struct hb_transfer_deadline deadline;
 struct qq_tls_transaction transaction;struct qq_request request;struct qq_cookie_jar *cookies;
 br_ssl_client_context client;br_x509_minimal_context verifier;
 unsigned char tls_buffer[BR_SSL_BUFSIZE_BIDI],body[262144];
 char host[128],method[8];struct hb_tls_time clock;
 uint64_t ticket;unsigned address;volatile int stopped;int fd,error,tls_error;
 enum qq_network_phase phase;
 struct qq_connection_diagnostic diagnostic;
 unsigned media,media_sink_active;size_t media_maximum;struct qq_response_sink media_sink;
 char media_url[2049];
};
/* Fresh stable single-thread object only. Anchors/options remain caller-owned.
 * Creates actual DNS/connect/TLS operations, no default trust, no persistence.
 * port0 means443; non443 is used only by explicit local test configurations. */
int qq_network_init(struct qq_network *,const struct qq_network_config *,void *application,
 int (*material)(void *,struct qq_runtime_material *),int (*stock)(void *));
const struct qq_runtime_ops *qq_network_operations(struct qq_network *);
void qq_network_cancel(struct qq_network *);
/* QQ-only date plausibility check; records an explicit clock diagnostic.
 * Never repairs RTC, invents current time or weakens certificate validation. */
int qq_network_current_time(struct qq_network *,struct hb_tls_time *);
/* Accepted media transfer owns sink through finish/abort, including DNS or
 * connect failure. Invalid arguments/URL before acceptance retain caller
 * ownership. No ekey or account cookies copied. Completed sink survives cancel.
 * Total media deadline1..900s, same hostname/time/TLS validation as control. */
int qq_network_media_begin(struct qq_network *,const struct qq_resource *,size_t maximum,unsigned timeout_ms,struct qq_response_sink);
int qq_network_media_step(struct qq_network *);
#endif
