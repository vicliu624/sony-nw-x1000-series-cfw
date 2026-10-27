#include "qqmusic_download.h"
#include <string.h>
void qq_download_init(struct qq_download_file *f){memset(f,0,sizeof(*f));qq_stage_init(&f->stage);}
static int check(struct qq_download_file *f){struct qq_storage_plan remaining;uint64_t required;
 if(!f||!f->volume||f->stage.state!=QQ_STAGE_OPEN||f->stage.bytes>f->plan.source||(f->stage.stop&&*f->stage.stop))return -1;
 remaining=f->plan;remaining.source-=f->stage.bytes;return qq_volume_recheck(f->volume,&remaining,&required);
}
int qq_download_begin(struct qq_download_file *f,struct qq_volume *volume,const struct qq_storage_plan *plan,const char *identity,const char *nonce,uint64_t maximum,volatile int *stop){
 uint64_t required;if(!f||f->stage.state!=QQ_STAGE_EMPTY||!volume||!plan||!maximum||plan->source<maximum||!plan->files[0]||(stop&&*stop)||qq_volume_recheck(volume,plan,&required))return -1;
 f->volume=volume;f->plan=*plan;return qq_stage_begin(&f->stage,volume->directory,volume->device,identity,nonce,maximum,stop);
}
int qq_download_abort(struct qq_download_file *f){if(!f)return -1;return f->stage.state==QQ_STAGE_READY?0:qq_stage_discard(&f->stage);}
static int write_bytes(void *context,const unsigned char *data,size_t n){struct qq_download_file *f=context;struct qq_response_sink sink;if(check(f))return -1;sink=qq_stage_sink(&f->stage);return sink.write(sink.opaque,data,n);}
static int finish(void *context,uint64_t bytes,const unsigned char digest[32]){struct qq_download_file *f=context;struct qq_response_sink sink;if(check(f))return -1;sink=qq_stage_sink(&f->stage);return sink.finish(sink.opaque,bytes,digest);}
static void abort_file(void *context){(void)qq_download_abort(context);}
struct qq_response_sink qq_download_sink(struct qq_download_file *f){struct qq_response_sink sink={f,write_bytes,finish,abort_file};return sink;}
int qq_download_take(struct qq_download_file *f,struct qq_stage_file *out){
 if(!f||!out||out->state!=QQ_STAGE_EMPTY||out->fd>=0||out->parent>=0||f->stage.state!=QQ_STAGE_READY||f->stage.fd>=0||f->stage.parent<0)return -1;
 *out=f->stage;qq_download_init(f);return 0;
}
