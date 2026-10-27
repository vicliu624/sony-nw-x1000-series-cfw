#include "qqmusic_output.h"
#include <string.h>
void qq_output_init(struct qq_output_file *f){memset(f,0,sizeof(*f));qq_stage_init(&f->stage);}
int qq_output_abort(struct qq_output_file *f){return f?qq_stage_discard(&f->stage):-1;}
static int check(struct qq_output_file *f){struct qq_storage_plan remaining;uint64_t required;
 if(!f||!f->volume||f->stage.state!=QQ_STAGE_OPEN||f->stage.bytes>f->plan.mp3)return -1;
 remaining=f->plan;remaining.mp3-=f->stage.bytes;
 return qq_volume_recheck(f->volume,&remaining,&required);
}
int qq_output_begin(struct qq_output_file *f,struct qq_volume *volume,const struct qq_storage_plan *plan,const char *identity,const char *nonce,uint64_t maximum,volatile int *stop){
 uint64_t required;if(!f||f->stage.state!=QQ_STAGE_EMPTY||!volume||!plan||!maximum||plan->mp3<maximum||!plan->files[2]||(stop&&*stop)||qq_volume_recheck(volume,plan,&required))return -1;
 f->volume=volume;f->plan=*plan;
 return qq_stage_begin_mp3(&f->stage,volume->directory,volume->device,identity,nonce,maximum,stop);
}
int qq_output_write(void *context,const unsigned char *data,unsigned count){
 struct qq_output_file *f=context;struct qq_response_sink sink;
 if(!f)return -1;
 if(check(f)){qq_output_abort(f);return -1;}sink=qq_stage_sink(&f->stage);
 if(sink.write(sink.opaque,data,count)){qq_output_abort(f);return -1;}return 0;
}
int qq_output_finish(struct qq_output_file *f,uint64_t expected){
 struct hb_sha256 hash;unsigned char digest[32];struct qq_response_sink sink;int rc;
 if(!f)return -1;
 if(!expected||expected!=f->stage.bytes||check(f)){qq_output_abort(f);return -1;}
 hash=f->stage.hash;hb_sha256_final(&hash,digest);qq_secret_clear(&hash,sizeof(hash));sink=qq_stage_sink(&f->stage);
 rc=sink.finish(sink.opaque,expected,digest);qq_secret_clear(digest,sizeof(digest));if(rc)qq_output_abort(f);return rc;
}
