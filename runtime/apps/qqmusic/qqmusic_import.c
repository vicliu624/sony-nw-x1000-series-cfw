#include "qqmusic_import.h"
#include <stdlib.h>
#include <string.h>
struct conversion {const struct qq_import_conversion *config;struct qq_metadata metadata;uint64_t output;size_t tags;unsigned ready,used;unsigned char pending[16384];};
static int flush(struct conversion *c){const struct qq_import_conversion *p=c->config;unsigned at=0;
 while(at<c->used){unsigned n=c->used-at;if(n>4096)n=4096;if((p->io.stop&&*p->io.stop)||p->io.write(p->io.destination,c->pending+at,n))return -1;at+=n;}c->used=0;return 0;
}
static int output(void *context,const unsigned char *data,unsigned bytes){
 struct conversion *c=context;const struct qq_import_conversion *p=c->config;unsigned at=0;
 if(!data||!bytes||!c->ready||bytes>p->maximum_output-c->output)return -1;
 while(at<bytes){unsigned n=bytes-at;if(n>sizeof(c->pending)-c->used)n=sizeof(c->pending)-c->used;if(p->io.stop&&*p->io.stop)return -1;memcpy(c->pending+c->used,data+at,n);c->used+=n;c->output+=n;at+=n;if(c->used==sizeof(c->pending)&&flush(c))return -1;}return 0;
}
static int progress(void *context,uint64_t samples,uint64_t total){struct conversion *c=context;return c->config->progress?c->config->progress(c->config->progress_context,samples,total):0;}
static int comment(void *context,const char *key,size_t key_n,const char *value,size_t n){struct conversion *c=context;return c->ready?-1:qq_metadata_comment(&c->metadata,key,key_n,value,n);}
static int comments_done(void *context){
 struct conversion *c=context;const struct qq_import_conversion *p=c->config;struct qq_track_tags tags;unsigned char *data;int rc=-1;
 if(c->ready||qq_metadata_fill(&c->metadata,p->song,p->intent,p->album_artist))return -1;
 if(p->cover_bytes&&qq_metadata_album_cover(&c->metadata,p->cover_album_mid,p->cover,p->cover_bytes))return -1;
 if(!c->metadata.jpeg_bytes&&p->fetch_cover){
  unsigned char *image;size_t bytes=0;int fetched;
  if(!c->metadata.bound_album_mid[0]||!c->metadata.jpeg||(p->io.stop&&*p->io.stop))return -1;
  image=malloc(262144);if(!image)return -1;
  fetched=p->fetch_cover(p->cover_context,c->metadata.bound_album_mid,image,262144,&bytes);
  if(!fetched&&bytes&&bytes<=262144&&!(p->io.stop&&*p->io.stop))fetched=qq_metadata_album_cover(&c->metadata,c->metadata.bound_album_mid,image,bytes);
  else fetched=-1;
  qq_secret_clear(image,262144);free(image);if(fetched||!c->metadata.jpeg_bytes)return -1;
 }
 if(qq_metadata_tags(&c->metadata,&tags))return -1;
 data=malloc(1048576);if(!data)return -1;
 if(!qq_id3_build(&tags,data,1048576,&c->tags)&&c->tags){c->ready=1;rc=output(c,data,(unsigned)c->tags);}
 qq_secret_clear(data,1048576);free(data);return rc;
}
int qq_import_convert(const struct qq_import_conversion *p,struct qq_import_report *report){
 struct conversion *c;struct qq_codec_io io;struct qq_codec_report audio;int rc=-1;
 if(report)memset(report,0,sizeof(*report));
 if(!p||!report||!p->song||!p->intent||!p->io.read_at||!p->io.write||!p->io.source_bytes||p->io.metadata||p->io.comment||p->io.comments_done||!p->maximum_output||p->maximum_output>268435456||p->encrypted>1||(p->encrypted&&(!p->ekey||!p->ekey_bytes))||(!p->encrypted&&(p->ekey||p->ekey_bytes))||(p->cover_bytes&&(!p->cover||!p->cover_album_mid))||(p->io.stop&&*p->io.stop))return -1;
 c=calloc(1,sizeof(*c));if(!c)return -1;c->config=p;qq_metadata_init(&c->metadata);
 if(p->artwork_capacity&&qq_metadata_artwork_buffer(&c->metadata,p->artwork,p->artwork_capacity))goto done;
 io=p->io;io.destination=c;io.write=output;io.metadata=c;io.comment=comment;io.comments_done=comments_done;io.progress_context=c;io.progress=progress;
 if(p->encrypted)rc=qq_codec_qmc_vorbis_mp3(&io,p->ekey,p->ekey_bytes,p->bitrate_kbps,&audio);
 else rc=qq_codec_vorbis_mp3(&io,p->bitrate_kbps,&audio);
 if(!rc&&flush(c))rc=-1;
 if(!rc&&c->ready&&audio.samples&&audio.mp3_bytes&&c->output==audio.mp3_bytes+c->tags){report->audio=audio;report->output_bytes=c->output;report->tag_bytes=c->tags;report->cover_bytes=c->metadata.jpeg_bytes;report->source_fields=c->metadata.source_mask;report->filled_fields=c->metadata.filled_mask;report->source_cover=c->metadata.source_cover;}
 else rc=-1;
done:qq_secret_clear(c,sizeof(*c));free(c);return rc;
}
