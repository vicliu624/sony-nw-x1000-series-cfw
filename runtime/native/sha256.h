#ifndef HB_SHA256_H
#define HB_SHA256_H
struct hb_sha256 { unsigned h[8],used; unsigned long long total; unsigned char block[64]; };
void hb_sha256_init(struct hb_sha256 *s);
void hb_sha256_update(struct hb_sha256 *s,const unsigned char *p,unsigned n);
void hb_sha256_final(struct hb_sha256 *s,unsigned char out[32]);
#endif
