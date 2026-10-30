#include "xnow_peer.h"
#include <string.h>
static void erase(void *p,size_t n){volatile uint8_t *v=p;while(n--)*v++=0;}
static int index_of(const struct xnow_peer_table *t,const uint8_t a[6]){for(unsigned i=0;i<XNOW_PEER_LIMIT;i++)if(t->used[i]&&!memcmp(t->peers[i].address,a,6))return (int)i;return -1;}
static int valid(const struct xnow_peer *p){
 unsigned any=0,ff=1;for(unsigned i=0;i<6;i++){any|=p->address[i];ff&=p->address[i]==255;}
 return any&&(!(p->address[0]&1)||ff)&&p->encrypt<=1&&!(ff&&p->encrypt)&&p->channel<=14&&(p->version==1||p->version==2);
}
int xnow_peer_init(struct xnow_peer_table *t,unsigned limit){if(!t||limit>XNOW_ENCRYPTED_PEER_LIMIT)return XNOW_PEER_ARGUMENT;erase(t,sizeof(*t));t->encrypted_limit=(uint8_t)limit;return 0;}
void xnow_peer_clear(struct xnow_peer_table *t){if(t)erase(t,sizeof(*t));}
void xnow_peer_count(const struct xnow_peer_table *t,unsigned *total,unsigned *encrypted){unsigned n=0,e=0;if(t)for(unsigned i=0;i<XNOW_PEER_LIMIT;i++)if(t->used[i]){n++;e+=t->peers[i].encrypt!=0;}if(total)*total=n;if(encrypted)*encrypted=e;}
static int store(struct xnow_peer_table *t,const struct xnow_peer *p,int modify){
 if(!t||!p||!valid(p))return XNOW_PEER_ARGUMENT;
 int at=index_of(t,p->address);
 if(at>=0&&!modify)return XNOW_PEER_EXISTS;
 if(at<0&&modify)return XNOW_PEER_NOT_FOUND;
 unsigned encrypted;xnow_peer_count(t,0,&encrypted);
 if(at>=0)encrypted-=t->peers[at].encrypt!=0;
 if(p->encrypt&&encrypted>=t->encrypted_limit)return XNOW_PEER_FULL;
 if(at<0)for(unsigned i=0;i<XNOW_PEER_LIMIT;i++)if(!t->used[i]){at=(int)i;break;}
 if(at<0)return XNOW_PEER_FULL;
 /* Copy before erase permits an in-table source without destroying its key. */
 struct xnow_peer copy=*p;if(!copy.encrypt)erase(copy.lmk,sizeof(copy.lmk));
 erase(&t->peers[at],sizeof(t->peers[at]));t->peers[at]=copy;t->used[at]=1;erase(&copy,sizeof(copy));return 0;
}
int xnow_peer_add(struct xnow_peer_table *t,const struct xnow_peer *p){return store(t,p,0);}
int xnow_peer_modify(struct xnow_peer_table *t,const struct xnow_peer *p){return store(t,p,1);}
int xnow_peer_delete(struct xnow_peer_table *t,const uint8_t a[6]){if(!t||!a)return XNOW_PEER_ARGUMENT;int i=index_of(t,a);if(i<0)return XNOW_PEER_NOT_FOUND;erase(&t->peers[i],sizeof(t->peers[i]));t->used[i]=0;return 0;}
int xnow_peer_get(const struct xnow_peer_table *t,const uint8_t a[6],struct xnow_peer *out){if(!t||!a||!out)return XNOW_PEER_ARGUMENT;int i=index_of(t,a);if(i<0)return XNOW_PEER_NOT_FOUND;*out=t->peers[i];return 0;}
int xnow_peer_next(const struct xnow_peer_table *t,unsigned *cursor,struct xnow_peer *out){if(!t||!cursor||!out||*cursor>XNOW_PEER_LIMIT)return XNOW_PEER_ARGUMENT;for(unsigned i=*cursor;i<XNOW_PEER_LIMIT;i++)if(t->used[i]){*out=t->peers[i];*cursor=i+1;return 0;}*cursor=XNOW_PEER_LIMIT;return XNOW_PEER_END;}
int xnow_peer_validate_send(const struct xnow_peer_table *t,const uint8_t a[6],unsigned channel,size_t bytes,struct xnow_peer *out){
 if(!out||channel<1||channel>14)return XNOW_PEER_ARGUMENT;
 struct xnow_peer p;int r=xnow_peer_get(t,a,&p);if(r)return r;
 if(p.channel&&p.channel!=channel)r=XNOW_PEER_CHANNEL;
 else if(bytes>(p.version==1?250u:1470u))r=XNOW_PEER_LENGTH;
 else *out=p;
 erase(&p,sizeof(p));return r;
}
