#ifndef HB_QQMUSIC_RESOURCE_H
#define HB_QQMUSIC_RESOURCE_H
#include "qqmusic_credential.h"
#include "qqmusic_protocol.h"
enum qq_resource_quality {QQ_MGG_96,QQ_MGG_192,QQ_MGG_320,QQ_MP3_128,QQ_MP3_320};
struct qq_resource_intent {
 char song_mid[65],media_mid[65],filename[81];
 enum qq_resource_quality quality;unsigned song_type;
};
/* Sensitive authorization, memory only; never log or persist ekey/signed URL. */
struct qq_resource {char url[2049],ekey[2049],filename[81];uint64_t expires_in;unsigned encrypted;};
int qq_resource_intent_init(struct qq_resource_intent *,const char *song_mid,
 const char *media_mid,unsigned song_type,enum qq_resource_quality);
int qq_resource_request(struct qq_request *,struct qq_json *,const char *comm,size_t,
 const struct qq_resource_intent *,uint64_t musicid,const char *guid);
int qq_resource_parse(struct qq_json *,const char *,size_t,const struct qq_resource_intent *,struct qq_resource *,uint64_t *code);
void qq_resource_clear(struct qq_resource *);
struct hb_https_url;
/* Revalidate parsed authorization URL before media TLS; no cookies attached. */
int qq_resource_url_parse(const char *,struct hb_https_url *);
#endif
