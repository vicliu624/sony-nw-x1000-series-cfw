#include "qqmusic_preview_transport.h"
#include "qqmusic_preview_pcm.h"
int qq_preview_decode_worker(struct qq_preview_transport *transport,struct qq_codec_io *source,unsigned encrypted,
 const char *ekey,size_t key_bytes,unsigned maximum_ms){
 struct qq_preview_pcm normalizer;struct qq_preview_sink output,input;
 struct qq_preview_report report;struct qq_codec_io io;int rc;
 if(!transport||!transport->stop||!transport->sequence||!source||!maximum_ms||maximum_ms>30000)return -1;
 io=*source;io.stop=transport->stop;output=qq_preview_transport_sink(transport);
 if(qq_preview_pcm_init(&normalizer,&output,transport->stop))return -1;
 input=qq_preview_pcm_sink(&normalizer);
 rc=qq_preview_decode(&io,encrypted,ekey,key_bytes,maximum_ms,&input,&report);
 if(!rc&&qq_preview_pcm_finish(&normalizer))rc=*transport->stop?-2:-1;
 if(!rc&&qq_preview_transport_end(transport,0))rc=*transport->stop?-2:-1;
 else if(rc==-1&&!transport->failed&&!*transport->stop)(void)qq_preview_transport_end(transport,1);
 qq_preview_pcm_clear(&normalizer);return rc;
}
