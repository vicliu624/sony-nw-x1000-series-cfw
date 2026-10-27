#include "qqmusic_qimei.h"
#include "qqmusic_json.h"
#include "../../store/tls_platform.h"
#include <bearssl.h>
#include <stdlib.h>
#include <string.h>
extern int sony_snprintf(char *,size_t,const char *,...) __asm__("snprintf");
/* Published service SDK routing constants and RSA public key, not account
 * credentials. Protocol source: qqmusic-api-python 0.8.2 utils/qimei.py,
 * SHA256 bc7ce3ebc8e256b15f2b87fc80e48655d9cad06355e1ef2a3a38149648658e79.
 * This implementation does not port its fabricated Android device profiles. */
static const char modulus_hex[]="c4231830a2eb5fc2827170641e79d80fec51bda9a22e4b4ab37d1f205a4ae44d928cda25879f66a3429051663312a127faf8a246bdaaf63918417e90d7c95b5908aa6a2d0f852e4a6770294a548ac1c2fe8f1f252fb826f4ac86ab9a00e7ce47d002a56e7c4b51eb889acc60ca6adbc9f72e81f4d31b1dd7464805264530ab1d";
static const char extra[]="{\"appKey\":\"0AND0HD6FE4HY80F\"}";
static void hex(char *out,const unsigned char *in,size_t n){static const char h[]="0123456789abcdef";size_t i;for(i=0;i<n;i++){out[2*i]=h[in[i]>>4];out[2*i+1]=h[in[i]&15];}out[2*n]=0;}
static unsigned unhex(char c){return c<='9'?(unsigned)(c-'0'):(unsigned)(c-'a'+10);}
static int base64(char *out,size_t cap,const unsigned char *in,size_t n){
 static const char abc[]="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";size_t i,k=0;
 if((n+2)/3*4>=cap)return -1;
 for(i=0;i<n;i+=3){unsigned x=(unsigned)in[i]<<16;size_t left=n-i;if(left>1)x|=(unsigned)in[i+1]<<8;if(left>2)x|=in[i+2];out[k++]=abc[x>>18];out[k++]=abc[(x>>12)&63];out[k++]=left>1?abc[(x>>6)&63]:'=';out[k++]=left>2?abc[x&63]:'=';}
 out[k]=0;return 0;
}
static void digest(char out[33],const char *const *parts,size_t count){
 br_md5_context md;unsigned char bytes[16];size_t i;br_md5_init(&md);
 for(i=0;i<count;i++)br_md5_update(&md,parts[i],strlen(parts[i]));
 br_md5_out(&md,bytes);hex(out,bytes,16);qq_secret_clear(bytes,sizeof(bytes));qq_secret_clear(&md,sizeof(md));
}
struct workspace {struct qq_json json;br_hmac_drbg_context random;br_aes_ct_cbcenc_keys aes;
 unsigned char seed[48],random_bytes[16],modulus[128],rsa[128],iv[16],payload[3088];
 char key[17],nonce[17],rsa64[173],params[4120],millis[24],sign[33];};
int qq_qimei_request(struct qq_request *out,const char *payload,size_t bytes,uint64_t timestamp,
 volatile int *stop,int (*seed)(unsigned char[48],volatile int *)){
 struct workspace *w=0;size_t i,padded,position;unsigned nonzero=0,nonff=0;int rc=-1,k;
 unsigned char exponent[]={1,0,1};br_rsa_public_key public_key;
 if(out)qq_secret_clear(out,sizeof(*out));
 if(!out||!payload||!bytes||bytes>3072||!stop||*stop||timestamp<1609459200||timestamp>4102444800ULL)return -1;
 w=calloc(1,sizeof(*w));if(!w)return -1;
 if(qq_json_parse(&w->json,payload,bytes)||w->json.nodes[0].type!=QQ_JSON_OBJECT)goto done;
 if((seed?seed:hb_tls_seed)(w->seed,stop)||*stop)goto done;
 for(i=0;i<48;i++){nonzero|=w->seed[i];nonff|=w->seed[i]^255u;}
 if(!nonzero||!nonff)goto done;
 br_hmac_drbg_init(&w->random,&br_sha256_vtable,w->seed,sizeof(w->seed));
 br_hmac_drbg_generate(&w->random,w->random_bytes,sizeof(w->random_bytes));
 hex(w->key,w->random_bytes,8);hex(w->nonce,w->random_bytes+8,8);
 for(i=0;i<128;i++)w->modulus[i]=(unsigned char)((unhex(modulus_hex[2*i])<<4)|unhex(modulus_hex[2*i+1]));
 w->rsa[0]=0;w->rsa[1]=2;position=2;
 for(i=0;i<1024&&position<111;i++){
  unsigned char random_byte;if(*stop)goto done;
  br_hmac_drbg_generate(&w->random,&random_byte,1);if(random_byte)w->rsa[position++]=random_byte;
 }
 if(position!=111)goto done;
 w->rsa[111]=0;memcpy(w->rsa+112,w->key,16);
 public_key.n=w->modulus;public_key.nlen=128;public_key.e=exponent;public_key.elen=sizeof(exponent);
 if(!br_rsa_i31_public(w->rsa,sizeof(w->rsa),&public_key)||base64(w->rsa64,sizeof(w->rsa64),w->rsa,sizeof(w->rsa)))goto done;
 padded=(bytes/16+1)*16;memcpy(w->payload,payload,bytes);memset(w->payload+bytes,(int)(padded-bytes),padded-bytes);
 memcpy(w->iv,w->key,16);br_aes_ct_cbcenc_init(&w->aes,w->key,16);br_aes_ct_cbcenc_run(&w->aes,w->iv,w->payload,padded);
 if(base64(w->params,sizeof(w->params),w->payload,padded))goto done;
 k=sony_snprintf(out->qimei_time,sizeof(out->qimei_time),"%llu",(unsigned long long)timestamp);
 if(k<0||(size_t)k>=sizeof(out->qimei_time))goto done;
 k=sony_snprintf(w->millis,sizeof(w->millis),"%llu",(unsigned long long)(timestamp*1000));if(k<0||(size_t)k>=sizeof(w->millis))goto done;
 {const char *parts[]={w->rsa64,w->params,w->millis,w->nonce,"ZdJqM15EeO2zWc08",extra};digest(w->sign,parts,6);}
 {const char *parts[]={"qimei_qq_androidpzAuCmaFAaFaHrdakPjLIEqKrGnSOOvH",out->qimei_time};digest(out->qimei_sign,parts,2);}
 k=sony_snprintf(out->body,sizeof(out->body),"{\"app\":0,\"os\":1,\"qimeiParams\":{\"key\":\"%s\",\"params\":\"%s\",\"time\":\"%s\",\"nonce\":\"%s\",\"sign\":\"%s\",\"extra\":\"{\\\"appKey\\\":\\\"0AND0HD6FE4HY80F\\\"}\"}}",w->rsa64,w->params,out->qimei_time,w->nonce,w->sign);
 if(k<0||(size_t)k>=sizeof(out->body)||*stop)goto done;
 strcpy(out->path,"/tme/trpc/proxy");out->host="api.tencentmusic.com";out->method="POST";out->json_body=out->qimei=1;rc=0;
done:
 qq_secret_clear(w,sizeof(*w));free(w);if(rc)qq_secret_clear(out,sizeof(*out));return rc;
}
struct reply_workspace {struct qq_json json;char inner[8193];};
static int status_ok(struct qq_json *json){int node=qq_json_get(json,0,"code");uint64_t code;return node<0||(!qq_json_uint(json,(unsigned)node,&code)&&!code);}
static int identifier(const char *text,size_t n){size_t i;if(strlen(text)!=n)return 0;for(i=0;i<n;i++)if(!((text[i]>='0'&&text[i]<='9')||(text[i]>='a'&&text[i]<='z')||(text[i]>='A'&&text[i]<='Z')))return 0;return 1;}
int qq_qimei_accept(const struct qq_response *response,struct qq_qimei *out){
 struct reply_workspace *w;int node,data,rc=-1;
 if(out)qq_secret_clear(out,sizeof(*out));
 if(!out||!response||response->phase!=QQ_RX_DONE||response->head.status!=200||response->anonymous!=1||!response->body)return -1;
 w=calloc(1,sizeof(*w));if(!w)return -1;
 if(qq_json_parse(&w->json,(const char *)response->body,response->body_bytes)||w->json.nodes[0].type!=QQ_JSON_OBJECT||!status_ok(&w->json))goto done;
 node=qq_json_get(&w->json,0,"data");if(node<0||qq_json_string(&w->json,(unsigned)node,w->inner,sizeof(w->inner)))goto done;
 if(qq_json_parse(&w->json,w->inner,strlen(w->inner))||w->json.nodes[0].type!=QQ_JSON_OBJECT||!status_ok(&w->json))goto done;
 data=qq_json_get(&w->json,0,"data");if(data<0||w->json.nodes[data].type!=QQ_JSON_OBJECT)goto done;
 node=qq_json_get(&w->json,(unsigned)data,"q16");if(node<0||qq_json_string(&w->json,(unsigned)node,out->q16,sizeof(out->q16))||(!identifier(out->q16,16)&&!identifier(out->q16,32)))goto done;
 /* Current service may explicitly return an empty q36 with a 32-byte q16.
  * Preserve that response, as the reference client does; never substitute q16
  * or manufacture a QIMEI36. Missing q36 and malformed nonempty values fail. */
 node=qq_json_get(&w->json,(unsigned)data,"q36");if(node<0||qq_json_string(&w->json,(unsigned)node,out->q36,sizeof(out->q36))||(out->q36[0]&&!identifier(out->q36,36)))goto done;
 rc=0;
done:
 qq_secret_clear(w,sizeof(*w));free(w);if(rc)qq_secret_clear(out,sizeof(*out));return rc;
}
