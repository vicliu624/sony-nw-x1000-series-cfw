/* Real read-only SQLite consumer. Synthetic records and ownership only. */
#include "../../runtime/platform/player/catalog_ro.h"
#include "../../runtime/platform/player/local_identity.h"
#include "../../runtime/store/stock_fs_bridge.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#ifndef HB_STORE_SONY_LIBC
#include <sys/stat.h>
int hb_target_fstat(int fd,struct hb_target_stat *out){struct stat s;if(fstat(fd,&s))return -1;*out=(struct hb_target_stat){s.st_dev,s.st_size,s.st_ino,s.st_mode,s.st_nlink};return 0;}
int hb_target_lstat(const char *path,struct hb_target_stat *out){struct stat s;if(lstat(path,&s))return -1;*out=(struct hb_target_stat){s.st_dev,s.st_size,s.st_ino,s.st_mode,s.st_nlink};return 0;}
#endif
struct owner {unsigned checks,deny_after;int allow;};
static int allowed(void *context){struct owner *o=context;o->checks++;return o->allow&&(!o->deny_after||o->checks<o->deny_after);}
int main(int argc,char **argv){
 struct xw_catalog_ro reader={0};struct owner owner={0};volatile int stop=0;struct xw_catalog_policy policy={&owner,allowed,&stop};struct xw_catalog_entry entries[2],prior[2];struct xw_catalog_page page={0},old_page;struct xw_catalog_query q={0};
 if(argc<3)return 64;
 assert(xw_catalog_ro_close(&reader)==XW_PLAYER_CLOSED);
 assert(!xw_catalog_ro_init(&reader,argv[1],&policy));q.roots=1;q.limit=2;memset(entries,0x5a,sizeof entries);memcpy(prior,entries,sizeof prior);old_page=page;
 assert(xw_catalog_ro_page(&reader,&q,entries,2,&page)==XW_PLAYER_UNAVAILABLE);assert(!memcmp(prior,entries,sizeof prior)&&!memcmp(&page,&old_page,sizeof page));
 owner.allow=1;assert(!xw_catalog_ro_page(&reader,&q,entries,2,&page));assert(page.count==1&&!page.more&&entries[0].object_id==10&&entries[0].object_type==1&&!strcmp(entries[0].title,"Synthetic playlist"));assert(reader.pending_db==0&&reader.pending_fd==-1);
 uint64_t revision=page.revision;q.roots=0;q.tree_id=1;q.parent_id=10;q.limit=1;q.expected_revision=revision;
 assert(!xw_catalog_ro_page(&reader,&q,entries,2,&page));assert(page.count==1&&page.more&&entries[0].object_id==202&&entries[0].reference_id==101&&!strcmp(entries[0].title,"Second song")&&!strcmp(entries[0].artist,"Shared artist")&&!strcmp(entries[0].album,"Shared album"));assert(entries[0].text_present==7&&!entries[0].text_truncated);
 q.offset=page.next_offset;assert(!xw_catalog_ro_page(&reader,&q,entries,2,&page));assert(entries[0].object_id==201&&entries[0].reference_id==100&&entries[0].text_truncated==1&&strlen(entries[0].title)==253&&entries[0].title[0]=='X');
 struct xw_catalog_entry record,saved_record;uint64_t object_revision=0;
 assert(!xw_catalog_ro_object(&reader,202,revision,&record,&object_revision));
 assert(object_revision==revision&&record.object_id==202&&record.reference_id==101&&!strcmp(record.title,"Second song")&&!strcmp(record.artist,"Shared artist")&&!strcmp(record.album,"Shared album"));
 assert(!reader.pending_db&&reader.pending_fd==-1);
 assert(!xw_catalog_ro_object(&reader,100,revision,&record,&object_revision)&&record.text_truncated==1&&strlen(record.title)==253);
 saved_record=record;object_revision=0x12345678;
 assert(xw_catalog_ro_object(&reader,999,revision,&record,&object_revision)==XW_PLAYER_UNAVAILABLE);
 assert(!memcmp(&record,&saved_record,sizeof record)&&object_revision==0x12345678);
 assert(xw_catalog_ro_object(&reader,0,revision,&record,&object_revision)==XW_PLAYER_UNAVAILABLE);
 assert(xw_catalog_ro_object(&reader,102,revision,&record,&object_revision)==XW_PLAYER_PROTOCOL);
 assert(xw_catalog_ro_object(&reader,202,revision+1,&record,&object_revision)==XW_PLAYER_STALE);
 assert(xw_catalog_ro_object(&reader,UINT64_MAX,revision,&record,&object_revision)==XW_PLAYER_INVALID);
 assert(!memcmp(&record,&saved_record,sizeof record)&&object_revision==0x12345678);
 owner.allow=0;assert(xw_catalog_ro_object(&reader,202,revision,&record,&object_revision)==XW_PLAYER_UNAVAILABLE);owner.allow=1;
 owner.checks=0;owner.deny_after=2;assert(xw_catalog_ro_object(&reader,202,revision,&record,&object_revision)==XW_PLAYER_UNAVAILABLE);owner.deny_after=0;
 stop=1;assert(xw_catalog_ro_object(&reader,202,revision,&record,&object_revision)==XW_PLAYER_UNAVAILABLE);stop=0;
 assert(!memcmp(&record,&saved_record,sizeof record)&&object_revision==0x12345678&&!reader.pending_db&&reader.pending_fd==-1);
 struct xw_media_id media_id;struct xw_media_item media_item,saved_item;
 assert(!xw_local_media_id_format(1,202,&media_id));
 assert(!xw_catalog_ro_media(&reader,&media_id,revision,&media_item,&object_revision));
 assert(!strcmp(media_item.id.value,media_id.value)&&!strcmp(media_item.title,"Second song")&&!strcmp(media_item.artist,"Shared artist")&&!strcmp(media_item.album,"Shared album")&&media_item.flags==7&&object_revision==revision);
 assert(!xw_local_media_id_format(0,100,&media_id));assert(!xw_catalog_ro_media(&reader,&media_id,revision,&media_item,&object_revision));
 assert(strlen(media_item.title)==253&&media_item.flags==(7|XW_MEDIA_TITLE_TRUNCATED));
 assert(!xw_local_media_id_format(1,103,&media_id));assert(!xw_catalog_ro_media(&reader,&media_id,revision,&media_item,&object_revision));
 assert(!strcmp(media_item.title,"Title only")&&!media_item.artist[0]&&!media_item.album[0]&&media_item.flags==XW_MEDIA_TITLE_PRESENT);
 saved_item=media_item;object_revision=0x12345678;
 assert(!xw_local_media_id_format(1,10,&media_id));assert(xw_catalog_ro_media(&reader,&media_id,revision,&media_item,&object_revision)==XW_PLAYER_UNSUPPORTED);
 assert(!xw_local_media_id_format(1,999,&media_id));assert(xw_catalog_ro_media(&reader,&media_id,revision,&media_item,&object_revision)==XW_PLAYER_UNAVAILABLE);
 assert(!xw_local_media_id_format(1,204,&media_id));assert(xw_catalog_ro_media(&reader,&media_id,revision,&media_item,&object_revision)==XW_PLAYER_UNAVAILABLE);
 assert(!xw_local_media_id_format(1,102,&media_id));assert(xw_catalog_ro_media(&reader,&media_id,revision,&media_item,&object_revision)==XW_PLAYER_PROTOCOL);
 assert(!xw_local_media_id_format(1,202,&media_id));assert(xw_catalog_ro_media(&reader,&media_id,revision+1,&media_item,&object_revision)==XW_PLAYER_STALE);
 strcpy(media_id.value,"moma-object:MOMA_LC;domain=FOLDERTREE;type=MEDIA;id=0ca");assert(xw_catalog_ro_media(&reader,&media_id,revision,&media_item,&object_revision)==XW_PLAYER_INVALID);
 assert(!memcmp(&media_item,&saved_item,sizeof media_item)&&object_revision==0x12345678&&!reader.pending_db&&reader.pending_fd==-1);
 memcpy(prior,entries,sizeof prior);old_page=page;q.expected_revision=revision+1;assert(xw_catalog_ro_page(&reader,&q,entries,2,&page)==XW_PLAYER_STALE);assert(!memcmp(prior,entries,sizeof prior)&&!memcmp(&page,&old_page,sizeof page));
 q.expected_revision=revision;q.offset=1;q.limit=2;assert(xw_catalog_ro_page(&reader,&q,entries,2,&page)==XW_PLAYER_PROTOCOL);assert(!memcmp(prior,entries,sizeof prior)&&!memcmp(&page,&old_page,sizeof page));
 q.offset=0;q.limit=1;owner.checks=0;owner.deny_after=2;assert(xw_catalog_ro_page(&reader,&q,entries,2,&page)==XW_PLAYER_UNAVAILABLE);assert(!memcmp(prior,entries,sizeof prior));assert(!reader.pending_db&&reader.pending_fd==-1);
 owner.deny_after=0;stop=1;assert(xw_catalog_ro_page(&reader,&q,entries,2,&page)==XW_PLAYER_UNAVAILABLE);stop=0;assert(!xw_catalog_ro_close(&reader));
 for(int i=2;i<argc;i++){memset(&reader,0,sizeof reader);assert(!xw_catalog_ro_init(&reader,argv[i],&policy));q.expected_revision=0;assert(xw_catalog_ro_page(&reader,&q,entries,2,&page)==XW_PLAYER_UNSUPPORTED);assert(xw_catalog_ro_object(&reader,202,0,&record,&object_revision)==XW_PLAYER_UNSUPPORTED);assert(!xw_local_media_id_format(1,202,&media_id));assert(xw_catalog_ro_media(&reader,&media_id,0,&media_item,&object_revision)==XW_PLAYER_UNSUPPORTED);assert(!xw_catalog_ro_close(&reader));}
 puts("Original catalog reader: pages and object lookup, reference metadata, bounded UTF-8, stale/atomic refusal and ownership cleanup passed");fflush(stdout);
#ifdef HB_STORE_SONY_LIBC
 _exit(0);
#endif
 return 0;
}
