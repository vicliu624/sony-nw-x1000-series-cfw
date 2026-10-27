#ifndef HB_STORE_DOWNLOAD_TASK_H
#define HB_STORE_DOWNLOAD_TASK_H
#include "resolver.h"
#include "connect_step.h"
#include "https_fetch.h"
#include "https_url.h"
enum hb_net_phase {HB_NET_EMPTY,HB_NET_DNS,HB_NET_CONNECT,HB_NET_TRANSFER,HB_NET_DONE,HB_NET_FAILED};
enum hb_net_error {HB_NET_INPUT=-90,HB_NET_ENTROPY=-91,HB_NET_TIME=-92,HB_NET_CANCELLED=-93,HB_NET_DEADLINE=-94,HB_NET_CLOCK=-95,HB_NET_IO=-96,HB_NET_TLS_INIT=-97};
struct hb_download_task {
 struct hb_https_url url;struct hb_dns_query dns;struct hb_connect connection;
 struct hb_transfer_deadline deadline;struct hb_download_file file;struct hb_https_fetch fetch;
 br_ssl_client_context client;br_x509_minimal_context verifier;
 unsigned char buffer[BR_SSL_BUFSIZE_BIDI];
 struct sockaddr_in addresses[HB_DNS_MAX_ADDRESSES];unsigned address_count,address_index;
 int fd,error,stage_error,cleanup_pending,tls_error,ares_status;volatile int *stop;enum hb_net_phase phase;
 const br_x509_trust_anchor *anchors;size_t anchor_count;
 const struct ares_options *options;int option_mask;unsigned redirects;
};
/* Large caller-owned workspace at stable address. Initialize once, discard
 * before reuse. Trust anchors/stop remain caller-owned for task lifetime. */
void hb_download_task_init(struct hb_download_task *);
int hb_download_task_begin(struct hb_download_task *,const char *url,
 const br_x509_trust_anchor *,size_t anchors,const char *cache,const char *key,
 unsigned bytes,const unsigned char *digest,unsigned long long reserve,unsigned timeout_ms,
 volatile int *stop,const struct ares_options *,int option_mask);
/* 0=more,1=closed transport and READY inactive cache,negative=terminal error.
 * HTTPS-only redirects (max5), no package publication. Same total deadline. */
int hb_download_task_step(struct hb_download_task *,unsigned wait_cap_ms);
struct hb_package_download_plan;
/* Takes a deep-copied per-file descriptor from an already validated plan. */
int hb_download_task_begin_file(struct hb_download_task *,const struct hb_package_download_plan *,unsigned file_index,
 const br_x509_trust_anchor *,size_t anchors,const char *cache,unsigned long long reserve,unsigned timeout_ms,
 volatile int *stop,const struct ares_options *,int option_mask);
/* Explicit cleanup, including a READY file after caller has consumed it.
 * REVIEW/active stop may retain cache, reported via cleanup_pending. */
int hb_download_task_discard(struct hb_download_task *);
/* User cancellation without modifying the platform stop token. */
int hb_download_task_cancel(struct hb_download_task *);
#endif
