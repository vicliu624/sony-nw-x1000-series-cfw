#include "qqmusic_codec.h"
#include "qqmusic_qmc.h"
#include "qqmusic_protocol.h"
#include <string.h>
struct qmc_source {struct qq_codec_io *base;struct qq_qmc_key key;uint64_t payload;};
static int decrypted_read(void *opaque,uint64_t offset,unsigned char *out,unsigned n) {
 struct qmc_source *s=opaque;int read;
 if((s->base->stop&&*s->base->stop)||n>65536||offset>s->payload||n>s->payload-offset) return -1;
 read=s->base->read_at(s->base->source,offset,out,n);
 if(read<=0||(unsigned)read>n) return read==0?0:-1;
 if(qq_qmc_apply(&s->key,out,(unsigned)read,offset)) {qq_secret_clear(out,n);return -1;}
 return read;
}
int qq_codec_qmc_vorbis_mp3(struct qq_codec_io *io,const char *encoded,size_t encoded_bytes,unsigned bitrate,struct qq_codec_report *report) {
 struct qmc_source source;struct qq_codec_io decoded;unsigned char tail[16],magic[4];
 size_t used=0;int footer,rc=-1;
 memset(&source,0,sizeof(source));memset(tail,0,sizeof(tail));memset(magic,0,sizeof(magic));
 if(!report) return -1;
 memset(report,0,sizeof(*report));
 if(!io||!io->read_at||!io->write||io->source_bytes<16||io->source_bytes>268435456||(io->stop&&*io->stop)) goto done;
 while(used<sizeof(tail)) {
  int n=io->read_at(io->source,io->source_bytes-16+used,tail+used,(unsigned)(16-used));
  if(n<=0||(unsigned)n>16-used) goto done;
  used+=(unsigned)n;
 }
 if(qq_qmc_payload_length(io->source_bytes,tail,&source.payload,&footer)||source.payload<4||qq_qmc_derive(&source.key,encoded,encoded_bytes)) goto done;
 source.base=io;
 used=0;
 while(used<sizeof(magic)) {
  int n=decrypted_read(&source,used,magic+used,(unsigned)(sizeof(magic)-used));
  if(n<=0) goto done;
  used+=(unsigned)n;
 }
 if(memcmp(magic,"OggS",4)) goto done;
 decoded=*io;decoded.source=&source;decoded.source_bytes=source.payload;decoded.read_at=decrypted_read;
 rc=qq_codec_vorbis_mp3(&decoded,bitrate,report);
done:
 qq_qmc_clear(&source.key);qq_secret_clear(&source,sizeof(source));qq_secret_clear(tail,sizeof(tail));qq_secret_clear(magic,sizeof(magic));return rc;
}
