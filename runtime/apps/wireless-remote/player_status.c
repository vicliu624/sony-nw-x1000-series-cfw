#include "player_status.h"
#include <string.h>
/* SDK strings need termination, not zero-filled unused capacity. Canonicalize
 * padding for the radio format; do not reject valid native metadata tails. */
static void copy_text(char *out,const char *in,size_t bytes){
 for(size_t i=0;i<bytes;i++){out[i]=in[i];if(!in[i])return;}
}
int wr_player_status(struct wr_status *out,const struct xw_player_snapshot *p,
                     uint64_t session,uint32_t sequence,uint32_t commands){
 if(!out||!p)return -1;
 struct wr_status s;uint8_t checked[WR_STATUS_BYTES];memset(&s,0,sizeof s);
 s.session=session;s.sequence=sequence;s.commands=commands;s.valid=p->valid&39u;
 if(s.valid&1u)s.state=p->state;
 if(s.valid&2u)copy_text(s.id,p->track.id.value,sizeof s.id);
 if(s.valid&4u){s.metadata_flags=p->track.flags;
  if(p->track.flags&1u)copy_text(s.title,p->track.title,sizeof s.title);
  if(p->track.flags&2u)copy_text(s.artist,p->track.artist,sizeof s.artist);
  if(p->track.flags&4u)copy_text(s.album,p->track.album,sizeof s.album);
 }
 if(s.valid&32u){s.volume=p->volume;s.minimum=p->volume_min;s.maximum=p->volume_max;}
 if(wr_status_encode(checked,sizeof checked,&s))return -1;
 *out=s;return 0;
}
