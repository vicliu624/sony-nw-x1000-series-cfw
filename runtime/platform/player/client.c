#include "provider.h"
#include <string.h>
#define ALL_FIELDS 63u
static int string_ok(const char *p,unsigned size,int ascii,int empty){
 unsigned n=0;
 while(n<size&&p[n]){
  unsigned c=(unsigned char)p[n++];
  if(ascii){if(c<33||c>126)return 0;continue;}
  if(c<0x80)continue;
  unsigned count,minimum,value;
  if(c>=0xc2&&c<=0xdf){count=1;minimum=0x80;value=c&31;}
  else if(c>=0xe0&&c<=0xef){count=2;minimum=0x800;value=c&15;}
  else if(c>=0xf0&&c<=0xf4){count=3;minimum=0x10000;value=c&7;}
  else return 0;
  while(count--){if(n>=size)return 0;c=(unsigned char)p[n++];if((c&192)!=128)return 0;value=(value<<6)|(c&63);}
  if(value<minimum||value>0x10ffff||(value>=0xd800&&value<=0xdfff))return 0;
 }
 return n<size&&(empty||n);
}
static int id_ok(const struct xw_media_id *id,int empty){return string_ok(id->value,sizeof id->value,1,empty);}
static int item_ok(const struct xw_media_item *item,int empty){return id_ok(&item->id,empty)&&string_ok(item->title,sizeof item->title,0,1)&&string_ok(item->artist,sizeof item->artist,0,1)&&string_ok(item->album,sizeof item->album,0,1);}
static int enter(struct xw_player *p){if(!p||!p->initialized)return XW_PLAYER_CLOSED;if(p->busy)return XW_PLAYER_BUSY;p->busy=1;return 0;}
int xw_player_bind(struct xw_player *p,const struct xw_player_provider *provider){
 if(!p||!provider||provider->api!=XW_PLAYER_API||!provider->snapshot||!provider->close||provider->commands>>XW_OP_COUNT)return XW_PLAYER_INVALID;
 if(provider->commands&&!provider->command)return XW_PLAYER_INVALID;
 if(p->initialized)return XW_PLAYER_BUSY;
 memset(p,0,sizeof *p);p->provider=*provider;p->initialized=1;return 0;
}
int xw_player_command(struct xw_player *p,const struct xw_player_command *command){
 int rc;if(!command||command->operation<0||command->operation>=XW_OP_COUNT||!id_ok(&command->item,1)||!id_ok(&command->container,1))return XW_PLAYER_INVALID;
 if(command->operation==XW_OP_PLAY_ITEM&&!command->item.value[0])return XW_PLAYER_INVALID;
 if(command->operation==XW_OP_STEP_VOLUME&&!command->value)return XW_PLAYER_INVALID;
 if((rc=enter(p)))return rc;
 if(!(p->provider.commands&(1u<<command->operation))){p->busy=0;return XW_PLAYER_UNSUPPORTED;}
 rc=p->provider.command(p->provider.context,command);p->busy=0;
 return rc>1?XW_PLAYER_PROTOCOL:rc;
}
static int read_snapshot(struct xw_player *p,struct xw_player_snapshot *out){
 struct xw_player_snapshot next;int rc;memset(&next,0,sizeof next);
 rc=p->provider.snapshot(p->provider.context,&next);if(rc)return rc>0?XW_PLAYER_PROTOCOL:rc;
 if(next.valid&~ALL_FIELDS)return XW_PLAYER_PROTOCOL;
 if((next.valid&XW_PF_STATE)&&(next.state<XW_PLAY_STOPPED||next.state>XW_PLAY_BUFFERING))return XW_PLAYER_PROTOCOL;
 if((next.valid&XW_PF_TRACK)&&!id_ok(&next.track.id,0))return XW_PLAYER_PROTOCOL;
 if((next.valid&XW_PF_METADATA)&&!item_ok(&next.track,!(next.valid&XW_PF_TRACK)))return XW_PLAYER_PROTOCOL;
 if((next.valid&XW_PF_VOLUME)&&(next.volume_min>next.volume_max||next.volume<next.volume_min||next.volume>next.volume_max))return XW_PLAYER_PROTOCOL;
 if(!(next.valid&XW_PF_STATE))next.state=XW_PLAY_UNKNOWN;
 if(!(next.valid&XW_PF_TRACK))memset(&next.track.id,0,sizeof next.track.id);
 if(!(next.valid&XW_PF_METADATA)){memset(next.track.title,0,sizeof next.track.title);memset(next.track.artist,0,sizeof next.track.artist);memset(next.track.album,0,sizeof next.track.album);next.track.flags=0;next.track.duration_ms=0;}
 if(!(next.valid&XW_PF_POSITION))next.position_ms=0;
 if(!(next.valid&XW_PF_DURATION))next.duration_ms=0;
 if(!(next.valid&XW_PF_VOLUME))next.volume=next.volume_min=next.volume_max=0;
 *out=next;return 0;
}
int xw_player_snapshot(struct xw_player *p,struct xw_player_snapshot *out){int rc;if(!out)return XW_PLAYER_INVALID;if((rc=enter(p)))return rc;rc=read_snapshot(p,out);p->busy=0;return rc;}
int xw_player_poll(struct xw_player *p,struct xw_player_snapshot *out,uint32_t *changes){
 struct xw_player_snapshot next;uint32_t changed;int rc;
 if(!out||!changes)return XW_PLAYER_INVALID;if((rc=enter(p)))return rc;
 rc=read_snapshot(p,&next);if(rc){p->have_previous=0;p->busy=0;return rc;}
 changed=p->have_previous?(p->previous.valid^next.valid):next.valid|XW_PC_AVAILABLE;
 if(!p->have_previous||next.state!=p->previous.state)changed|=next.valid&XW_PF_STATE;
 if(!p->have_previous||strcmp(next.track.id.value,p->previous.track.id.value))changed|=next.valid&XW_PF_TRACK;
 if(!p->have_previous||strcmp(next.track.title,p->previous.track.title)||strcmp(next.track.artist,p->previous.track.artist)||strcmp(next.track.album,p->previous.track.album)||next.track.flags!=p->previous.track.flags||next.track.duration_ms!=p->previous.track.duration_ms)changed|=next.valid&XW_PF_METADATA;
 if(!p->have_previous||next.position_ms!=p->previous.position_ms)changed|=next.valid&XW_PF_POSITION;
 if(!p->have_previous||next.duration_ms!=p->previous.duration_ms)changed|=next.valid&XW_PF_DURATION;
 if(!p->have_previous||next.volume!=p->previous.volume||next.volume_min!=p->previous.volume_min||next.volume_max!=p->previous.volume_max)changed|=next.valid&XW_PF_VOLUME;
 if(!p->have_previous||next.library_revision!=p->previous.library_revision)changed|=XW_PC_LIBRARY;
 if(!p->have_previous||next.queue_revision!=p->previous.queue_revision)changed|=XW_PC_QUEUE;
 p->previous=next;p->have_previous=1;*out=next;*changes=changed;p->busy=0;return 0;
}
int xw_media_browse(struct xw_player *p,const struct xw_media_query *query,struct xw_media_item *items,uint32_t capacity,struct xw_media_page *page){
 struct xw_media_item *staged;struct xw_media_page result;int rc;
 if(!query||!items||!page||query->view<0||query->view>XW_MEDIA_QUEUE||!query->limit||query->limit>XW_MEDIA_PAGE_MAX||query->limit>capacity||!id_ok(&query->container,1)||query->offset>UINT32_MAX-query->limit)return XW_PLAYER_INVALID;
 if(query->view==XW_MEDIA_PLAYLIST_TRACKS&&!query->container.value[0])return XW_PLAYER_INVALID;
 if((rc=enter(p)))return rc;if(!p->provider.browse){p->busy=0;return XW_PLAYER_UNSUPPORTED;}
 staged=p->browse_scratch;memset(staged,0,sizeof p->browse_scratch);memset(&result,0,sizeof result);
 rc=p->provider.browse(p->provider.context,query,staged,&result);p->busy=0;if(rc)return rc>0?XW_PLAYER_PROTOCOL:rc;
 if(result.offset!=query->offset||result.count>query->limit||result.next_offset!=query->offset+result.count)return XW_PLAYER_PROTOCOL;
 if(query->expected_revision&&query->expected_revision!=result.revision)return XW_PLAYER_STALE;
 if(result.total!=XW_MEDIA_TOTAL_UNKNOWN&&(result.next_offset>result.total||(!result.count&&result.offset<result.total)))return XW_PLAYER_PROTOCOL;
 for(uint32_t i=0;i<result.count;i++)if(!item_ok(&staged[i],0))return XW_PLAYER_PROTOCOL;
 memcpy(items,staged,result.count*sizeof *items);*page=result;return 0;
}
int xw_player_close(struct xw_player *p){int rc;if((rc=enter(p)))return rc;rc=p->provider.close(p->provider.context);p->busy=0;if(rc)return rc>0?XW_PLAYER_PROTOCOL:rc;memset(p,0,sizeof *p);return 0;}
