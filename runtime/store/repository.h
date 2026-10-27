#ifndef HB_STORE_REPOSITORY_H
#define HB_STORE_REPOSITORY_H
#include "bearssl.h"
#define HB_REPOSITORY_CONFIG_BYTES 4096u
struct hb_repository_spec {char catalog_url[2400];unsigned catalog_bytes;unsigned char catalog_sha256[32],ca_sha256[32];int valid;};
struct hb_repository {
 struct hb_repository_spec spec;
 br_x509_decoder_context decoder;br_x509_trust_anchor anchor;
 unsigned char dn[1024],raw[8192];unsigned dn_bytes,raw_bytes;int dn_overflow,valid;
 struct {br_x509_decoder_context decoder;unsigned char dn[1024];unsigned bytes;int overflow;} extra_ca[7];
 br_x509_trust_anchor anchors[8];unsigned anchor_count;
};
enum hb_repository_error {HB_REPO_INPUT=-110,HB_REPO_IO=-111,HB_REPO_HASH=-112,HB_REPO_CERT=-113,HB_REPO_CANCELLED=-114,HB_REPO_MISSING=-115};
/* HBREPO1 LF text, exactly catalog_url/catalog_bytes/catalog_sha256/ca_sha256.
 * Configuration is user-selected trust policy, not authenticated by its hash. */
int hb_repository_parse(const unsigned char *,unsigned,struct hb_repository_spec *);
/* Read-only canonical directory with repository.conf and a single DER ca.der.
 * No links/hardlinks, no default/sample anchors. Object remains stable/alive
 * while anchor is borrowed (key points into decoder). Quiescent directory. */
int hb_repository_load(const char *directory,volatile int *stop,struct hb_repository *);
#endif
