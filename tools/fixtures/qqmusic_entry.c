#include "../../runtime/apps/qqmusic/qqmusic_font.h"
#include "../../runtime/apps/qqmusic/qqmusic_entry.h"
#include "../../runtime/apps/qqmusic/qqmusic_asset.h"
#include <assert.h>
#include <stdlib.h>
#include <string.h>
static int fault,volume_open,font_ready,runtime_open,display_open,steps,invalidated,cancelled;
static volatile int stopped;
static unsigned char *asset;
static struct qq_runtime *active_runtime;
void qq_secret_clear(void *p,size_t n){memset(p,0,n);}
void qq_volume_init(struct qq_volume *v){memset(v,0,sizeof(*v));v->directory=-1;}
int qq_volume_open(struct qq_volume *v,const struct qq_storage_policy *p,const char *path,const struct qq_storage_plan *plan,uint64_t *required){
 assert(!volume_open&&!strcmp(p->source,"fixture-user")&&!strcmp(path,"/contents/fixture"));
 assert(!plan->source&&!plan->mp3&&!plan->temporary);*required=0;if(fault==1)return -1;
 v->directory=42;volume_open=1;return 0;
}
int qq_volume_close(struct qq_volume *v){assert(!font_ready&&!runtime_open&&!display_open&&!asset);if(v->directory>=0){assert(volume_open);volume_open=0;v->directory=-1;}return fault==9?-1:0;}
int qq_asset_read(struct qq_volume *v,const struct qq_storage_plan *p,const char *name,size_t n,const unsigned char hash[32],unsigned char **out){
 (void)p;assert(volume_open&&v->directory==42&&!strcmp(name,QQ_FONT_NAME)&&n==QQ_FONT_BYTES&&hash[0]==0x63&&hash[31]==0x31);*out=0;
 if(fault==2)return -1;
 asset=malloc(n);assert(asset);memset(asset,0x65,n);*out=asset;return 0;
}
void qq_asset_free(unsigned char *p,size_t n){assert(p==asset&&n==QQ_FONT_BYTES&&!font_ready&&invalidated&&!runtime_open&&!display_open);memset(p,0,n);free(p);asset=0;}
int qq_ui_font(const unsigned char *p,size_t n){if(!p){assert(!n);font_ready=0;invalidated=1;return -1;}assert(p==asset&&n==QQ_FONT_BYTES);if(fault==3)return -1;font_ready=1;return 0;}
int qq_asset_map(struct qq_volume *v,const struct qq_storage_plan *plan,const char *name,size_t n,const unsigned char hash[32],struct qq_asset_mapping *out){int rc=qq_asset_read(v,plan,name,n,hash,&out->data);if(!rc){out->bytes=n;memcpy(out->digest,hash,32);}return rc;}
int qq_asset_unmap(struct qq_asset_mapping *m){qq_asset_free(m->data,m->bytes);memset(m,0,sizeof(*m));return 0;}
int qq_ui_font_mapped(const struct qq_asset_mapping *m){return qq_ui_font(m->data,m->bytes);}
int qq_runtime_init(struct qq_runtime *r,const struct qq_runtime_ops *ops){assert(font_ready&&ops);if(fault==4)return -1;active_runtime=r;runtime_open=1;if(fault==10)stopped=1;return 0;}
void qq_runtime_close(struct qq_runtime *r){assert(runtime_open&&r==active_runtime);runtime_open=0;cancelled++;}
int qq_devices_open(struct qq_devices *d,struct qq_loop_io *io,unsigned short *pixels,size_t n,volatile int *stop){
 (void)d;assert(runtime_open&&pixels&&n==QQ_UI_PIXELS&&stop==&stopped);if(fault==5)return -1;display_open=1;memset(io,0,sizeof(*io));return 0;
}
int qq_devices_close(struct qq_devices *d){(void)d;assert(display_open&&!runtime_open);display_open=0;return 0;}
int qq_loop_init(struct qq_loop *l,struct qq_runtime *r,const struct qq_loop_io *io,unsigned short *pixels,size_t n){
 (void)io;assert(display_open&&n==QQ_UI_PIXELS);if(fault==6)return -1;memset(l,0,sizeof(*l));l->runtime=r;l->pixels=pixels;return 0;
}
void qq_loop_close(struct qq_loop *l){if(l->closed)return;assert(runtime_open&&display_open);qq_runtime_close(l->runtime);display_open=0;l->closed=1;if(fault==8)l->failed=1;}
int qq_loop_step(struct qq_loop *l){assert(display_open&&runtime_open);if(++steps==1)return 0;qq_loop_close(l);return fault==7?-1:1;}
int main(void){
 struct qq_storage_policy policy={"fixture-user","vfat"};struct qq_runtime_ops ops;struct qq_entry_config config;int i;
 memset(&ops,0,sizeof(ops));config.volume=&policy;config.resource_directory="/contents/fixture";config.operations=&ops;config.stop=&stopped;
 assert(qq_entry_run(0)<0);stopped=1;assert(qq_entry_run(&config)<0);stopped=0;
 for(i=0;i<=10;i++){
  fault=i;steps=invalidated=cancelled=0;assert(!volume_open&&!font_ready&&!runtime_open&&!display_open&&!asset);
  assert(qq_entry_run(&config)==(i?-1:0));assert(!volume_open&&!font_ready&&!runtime_open&&!display_open&&!asset);
  assert(cancelled==(i==0||i>=5));stopped=0;
 }
 return 0;
}
