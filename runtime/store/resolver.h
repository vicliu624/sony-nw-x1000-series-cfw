#ifndef HB_STORE_RESOLVER_H
#define HB_STORE_RESOLVER_H
#include <sys/select.h>
#include "ares.h"
#include "deadline.h"
#define HB_DNS_MAX_ADDRESSES 8
enum hb_dns_state {HB_DNS_EMPTY,HB_DNS_ACTIVE,HB_DNS_READY,HB_DNS_FAILED};
enum hb_dns_error {HB_DNS_INPUT=-70,HB_DNS_LOOKUP=-71,HB_DNS_FORMAT=-72,HB_DNS_LIMIT=-73,HB_DNS_CANCELLED=-74,HB_DNS_DEADLINE=-75,HB_DNS_CLOCK=-76,HB_DNS_IO=-77};
struct hb_dns_query {
 ares_channel channel;
 struct sockaddr_in addresses[HB_DNS_MAX_ADDRESSES];
 unsigned count,port;char name[254];
 enum hb_dns_state state;int error,ares_status;
 struct hb_transfer_deadline *deadline;volatile int *stop;
};
/* Stable single-thread owner. IPv4 only for now. OptionsNULL uses original
 * resolver configuration; tests always explicitly pin a loopback resolver. */
void hb_dns_init(struct hb_dns_query *);
int hb_dns_begin(struct hb_dns_query *,const char *name,unsigned port,
 struct hb_transfer_deadline *,volatile int *stop,const struct ares_options *,int option_mask);
/* 0=pending,1=owned address results,negative=terminal. No old timeval/select ABI. */
int hb_dns_step(struct hb_dns_query *,unsigned wait_cap_ms);
void hb_dns_release(struct hb_dns_query *);
#endif
