#include "catalog_ro.h"
#include "sqlite_abi.h"
#include "local_identity.h"
#include "../../store/stock_fs_bridge.h"
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <limits.h>
#define READONLY 1
#define ROW 100
#define DONE 101
struct budget {struct xw_catalog_ro *reader;unsigned remaining;};
static int permitted(struct xw_catalog_ro *r){return (!r->policy.stop||!*r->policy.stop)&&r->policy.may_read&&r->policy.may_read(r->policy.context)==1;}
static int progress(void *context){struct budget *b=context;if(!b->remaining||!permitted(b->reader))return 1;--b->remaining;return 0;}
static int authorize(void *context,int action,const char *a,const char *b,const char *database,const char *trigger){(void)context;(void)b;(void)database;(void)trigger;if(action==20||action==21)return 0;if(action==31&&b&&!strcmp(b,"coalesce"))return 0;if(action==22&&a&&(!strcmp(a,"BEGIN")||!strcmp(a,"COMMIT")||!strcmp(a,"ROLLBACK")))return 0;return 1;}
static int sql_error(int rc){return rc==5||rc==6||rc==9?XW_PLAYER_BUSY:rc==7?XW_PLAYER_UNAVAILABLE:XW_PLAYER_PROTOCOL;}
static uint32_t be32(const unsigned char *p){return (uint32_t)p[0]<<24|(uint32_t)p[1]<<16|(uint32_t)p[2]<<8|p[3];}
static int identity(struct xw_catalog_ro *r,int fd){
 struct hb_target_stat a,b;if(hb_target_fstat(fd,&a)||hb_target_lstat(r->path,&b))return XW_PLAYER_IO;
 if((a.st_mode&0170000)!=0100000||(b.st_mode&0170000)!=0100000||a.st_nlink!=1||b.st_nlink!=1||a.st_dev!=b.st_dev||a.st_ino!=b.st_ino||a.st_size!=b.st_size||a.st_size<100||a.st_size>268435456)return XW_PLAYER_PROTOCOL;
 if(r->bound&&(r->device!=a.st_dev||r->inode!=a.st_ino))return XW_PLAYER_STALE;
 if(!r->bound){r->device=a.st_dev;r->inode=a.st_ino;r->bound=1;}
 return 0;
}
static int revision(struct xw_catalog_ro *r,int fd,uint64_t *out){
 unsigned char header[100];unsigned used=0;int rc=identity(r,fd);if(rc)return rc;if(lseek(fd,0,SEEK_SET)!=0)return XW_PLAYER_IO;
 while(used<sizeof header){ssize_t n=read(fd,header+used,sizeof header-used);if(n<0&&errno==EINTR)continue;if(n<=0)return XW_PLAYER_IO;used+=(unsigned)n;}
 if(memcmp(header,"SQLite format 3\0",16))return XW_PLAYER_PROTOCOL;
 *out=((uint64_t)be32(header+24)<<32)|be32(header+40);return *out?0:XW_PLAYER_PROTOCOL;
}
static int text(sqlite3_stmt *statement,int column,char *out,uint32_t *present,uint32_t *truncated,unsigned mask){
 if(sqlite3_column_type(statement,column)==5){out[0]=0;return 0;}
 if(sqlite3_column_type(statement,column)!=3)return XW_PLAYER_PROTOCOL;
 const unsigned char *p=sqlite3_column_text(statement,column);int bytes=sqlite3_column_bytes(statement,column);if(!p||bytes<0||bytes>65536)return XW_PLAYER_PROTOCOL;
 unsigned at=0,written=0;int full=0;
 while(at<(unsigned)bytes){unsigned start=at,c=p[at++],extra=0,value=0,minimum=0;if(!c)return XW_PLAYER_PROTOCOL;
  if(c>=0xc2&&c<=0xdf){extra=1;value=c&31;minimum=0x80;}else if(c>=0xe0&&c<=0xef){extra=2;value=c&15;minimum=0x800;}else if(c>=0xf0&&c<=0xf4){extra=3;value=c&7;minimum=0x10000;}else if(c>=0x80)return XW_PLAYER_PROTOCOL;
  while(extra--){if(at>=(unsigned)bytes||(p[at]&192)!=128)return XW_PLAYER_PROTOCOL;value=(value<<6)|(p[at++]&63);}
  if(minimum&&(value<minimum||value>0x10ffff||(value>=0xd800&&value<=0xdfff)))return XW_PLAYER_PROTOCOL;
  if(!full&&written+at-start<XW_MEDIA_TEXT_BYTES){memcpy(out+written,p+start,at-start);written+=at-start;}else full=1;
 }
 out[written]=0;*present|=mask;if(full)*truncated|=mask;return 0;
}
static int schema(sqlite3 *db){
 sqlite3_stmt *statement=0;int rc=sqlite3_prepare_v2(db,"SELECT prop_name,meta_id,prop_type,data_type FROM schema WHERE prop_name IN ('ARTIST','ALBUM') ORDER BY prop_name",-1,&statement,0);if(rc)return sql_error(rc);
 unsigned seen=0;while((rc=sqlite3_step(statement))==ROW){const unsigned char *name=sqlite3_column_text(statement,0);int id=sqlite3_column_int(statement,1);if(sqlite3_column_int(statement,2)!=1||sqlite3_column_int(statement,3)!=0x73){rc=-1;break;}if(name&&!strcmp((const char *)name,"ALBUM")&&id==3&&!(seen&1))seen|=1;else if(name&&!strcmp((const char *)name,"ARTIST")&&id==2&&!(seen&2))seen|=2;else {rc=-1;break;}}
 int result=rc==DONE&&seen==3?0:XW_PLAYER_UNSUPPORTED;if(sqlite3_finalize(statement))result=XW_PLAYER_IO;return result;
}
int xw_catalog_ro_init(struct xw_catalog_ro *r,const char *path,const struct xw_catalog_policy *policy){
 if(!r||!path||!policy||!policy->may_read||path[0]!='/')return XW_PLAYER_INVALID;
 size_t n=strlen(path);if(!n||n>=sizeof r->path||strstr(path,"/../")||strstr(path,"/./")||strstr(path,"//"))return XW_PLAYER_INVALID;
 if(r->busy||r->pending_db)return XW_PLAYER_BUSY;
 memset(r,0,sizeof *r);memcpy(r->path,path,n+1);r->policy=*policy;r->pending_fd=-1;return 0;
}
int xw_catalog_ro_close(struct xw_catalog_ro *r){
 if(!r||!r->path[0])return XW_PLAYER_CLOSED;if(r->busy)return XW_PLAYER_BUSY;
 if(r->pending_db){int rc=sqlite3_close(r->pending_db);if(rc)return XW_PLAYER_BUSY;r->pending_db=0;}
 if(r->pending_fd>=0){int fd=r->pending_fd;r->pending_fd=-1;if(close(fd))return XW_PLAYER_IO;}
 memset(r,0,sizeof *r);r->pending_fd=-1;return 0;
}
static int read_objects(struct xw_catalog_ro *r,const struct xw_catalog_query *q,struct xw_catalog_entry *entries,unsigned capacity,struct xw_catalog_page *page,unsigned by_id){
 static const char select_sql[]="SELECT o.object_id,o.reference_id,o.parent_id,o.tree_id,o.object_type,o.child_index,o.media_type,o.format,COALESCE(t.title,o.title),a.value,b.value FROM object_body o LEFT JOIN object_body t ON t.object_id=o.reference_id LEFT JOIN object_meta_text a ON a.id=COALESCE(t.m2_id,o.m2_id) AND a.meta_id=2 LEFT JOIN object_meta_text b ON b.id=COALESCE(t.m3_id,o.m3_id) AND b.meta_id=3 WHERE (?1=2 AND o.object_id=?3) OR (?1=1 AND o.parent_id=0 AND o.object_type=1) OR (?1=0 AND o.tree_id=?2 AND o.parent_id=?3) ORDER BY o.child_index,o.object_id LIMIT ?4 OFFSET ?5";
 struct xw_catalog_entry staged[XW_MEDIA_PAGE_MAX];struct xw_catalog_page output;sqlite3 *db=0;sqlite3_stmt *statement=0;int fd=-1,rc,result=XW_PLAYER_IO,transaction=0;uint64_t before=0,after=0;struct budget budget={r,64};
 if(!r||!q||!entries||!page||!r->path[0]||!q->limit||q->limit>XW_MEDIA_PAGE_MAX||q->limit>capacity||q->offset>INT_MAX-q->limit-1||q->parent_id>INT64_MAX||q->roots>1)return XW_PLAYER_INVALID;
 if(r->busy||r->pending_db)return XW_PLAYER_BUSY;r->busy=1;if(!permitted(r)){r->busy=0;return XW_PLAYER_UNAVAILABLE;}memset(staged,0,sizeof staged);memset(&output,0,sizeof output);
 fd=open(r->path,O_RDONLY|O_NONBLOCK|O_NOFOLLOW);if(fd<0){result=XW_PLAYER_UNAVAILABLE;goto done;}if((result=revision(r,fd,&before)))goto done;
 if(q->expected_revision&&q->expected_revision!=before){result=XW_PLAYER_STALE;goto done;}
 rc=sqlite3_open_v2(r->path,&db,READONLY,0);if(rc){result=sql_error(rc);goto done;}
 sqlite3_limit(db,0,65536);sqlite3_limit(db,1,4096);sqlite3_limit(db,2,64);
 if(sqlite3_exec(db,"PRAGMA temp_store=MEMORY; PRAGMA cache_size=64",0,0,0)||sqlite3_set_authorizer(db,authorize,0)){result=XW_PLAYER_IO;goto done;}
 sqlite3_progress_handler(db,1000,progress,&budget);
 rc=sqlite3_exec(db,"BEGIN",0,0,0);if(rc){result=sql_error(rc);goto done;}transaction=1;
 if((result=schema(db)))goto done;
 rc=sqlite3_prepare_v2(db,select_sql,-1,&statement,0);if(rc){result=sql_error(rc);goto done;}
 if(sqlite3_bind_int(statement,1,by_id?2:(int)q->roots)||sqlite3_bind_int64(statement,2,q->tree_id)||sqlite3_bind_int64(statement,3,(long long)q->parent_id)||sqlite3_bind_int(statement,4,(int)q->limit+1)||sqlite3_bind_int(statement,5,(int)q->offset)){result=XW_PLAYER_IO;goto done;}
 while((rc=sqlite3_step(statement))==ROW){
  if(output.count==q->limit){output.more=1;break;}
  struct xw_catalog_entry *e=staged+output.count;long long id=sqlite3_column_int64(statement,0),reference=sqlite3_column_int64(statement,1),parent=sqlite3_column_int64(statement,2),tree=sqlite3_column_int64(statement,3);
  int kind=sqlite3_column_int(statement,4);if(id<=0||reference<0||parent<0||tree<0||tree>UINT32_MAX||kind<1||kind>3){result=XW_PLAYER_PROTOCOL;goto done;}
  e->object_id=(uint64_t)id;e->reference_id=(uint64_t)reference;e->parent_id=(uint64_t)parent;e->tree_id=(uint32_t)tree;e->object_type=(uint32_t)kind;e->child_index=sqlite3_column_int(statement,5);e->media_type=(uint32_t)sqlite3_column_int(statement,6);e->format=(uint32_t)sqlite3_column_int(statement,7);
  if((result=text(statement,8,e->title,&e->text_present,&e->text_truncated,1))||(result=text(statement,9,e->artist,&e->text_present,&e->text_truncated,2))||(result=text(statement,10,e->album,&e->text_present,&e->text_truncated,4)))goto done;
  output.count++;
 }
 if(rc!=DONE&&rc!=ROW){result=sql_error(rc);goto done;}
 if((result=revision(r,fd,&after)))goto done;if(after!=before){result=XW_PLAYER_STALE;goto done;}
 if(!permitted(r)){result=XW_PLAYER_UNAVAILABLE;goto done;}
 output.revision=before;output.next_offset=q->offset+output.count;result=0;
done:
 if(statement&&sqlite3_finalize(statement)&&!result)result=XW_PLAYER_IO;
 if(db){sqlite3_progress_handler(db,0,0,0);if(transaction&&sqlite3_exec(db,"ROLLBACK",0,0,0)&&!result)result=XW_PLAYER_IO;rc=sqlite3_close(db);if(rc){r->pending_db=db;r->pending_fd=fd;fd=-1;result=XW_PLAYER_BUSY;}}
 if(fd>=0&&close(fd)&&!result)result=XW_PLAYER_IO;
 r->busy=0;if(!result){memcpy(entries,staged,output.count*sizeof *entries);*page=output;}return result;
}
int xw_catalog_ro_page(struct xw_catalog_ro *r,const struct xw_catalog_query *q,struct xw_catalog_entry *entries,unsigned capacity,struct xw_catalog_page *page){
 return read_objects(r,q,entries,capacity,page,0);
}
int xw_catalog_ro_object(struct xw_catalog_ro *r,uint64_t object_id,uint64_t expected_revision,struct xw_catalog_entry *entry,uint64_t *revision_out){
 struct xw_catalog_query query={0};struct xw_catalog_entry staged;struct xw_catalog_page page;
 if(!entry||!revision_out||object_id>INT64_MAX)return XW_PLAYER_INVALID;
 query.parent_id=object_id;query.limit=1;query.expected_revision=expected_revision;
 int rc=read_objects(r,&query,&staged,1,&page,1);if(rc)return rc;
 if(!page.count)return XW_PLAYER_UNAVAILABLE;
 if(page.count!=1||page.more)return XW_PLAYER_PROTOCOL;
 *entry=staged;*revision_out=page.revision;return 0;
}
int xw_catalog_ro_media(struct xw_catalog_ro *r,const struct xw_media_id *identity,uint64_t expected_revision,struct xw_media_item *item,uint64_t *revision_out){
 uint32_t domain,object;uint64_t observed=0;struct xw_catalog_entry entry;struct xw_media_item staged={0};
 if(!item||!revision_out)return XW_PLAYER_INVALID;
 int rc=xw_local_media_id_parse(identity,&domain,&object);if(rc)return rc;
 /* Native local-content ID0 is the synthetic root, not a playable record. */
 if(!object)return XW_PLAYER_UNAVAILABLE;
 rc=xw_catalog_ro_object(r,object,expected_revision,&entry,&observed);if(rc)return rc;
 if(entry.object_type==3){
  if(!entry.reference_id)return XW_PLAYER_UNAVAILABLE;
  rc=xw_catalog_ro_object(r,entry.reference_id,observed,&entry,&observed);if(rc)return rc;
 }
 if(entry.object_type!=2)return XW_PLAYER_UNSUPPORTED;
 rc=xw_local_media_id_format(domain,object,&staged.id);if(rc)return rc;
 memcpy(staged.title,entry.title,sizeof staged.title);memcpy(staged.artist,entry.artist,sizeof staged.artist);memcpy(staged.album,entry.album,sizeof staged.album);
 staged.flags=(entry.text_present&7u)|((entry.text_truncated&7u)<<8);
 *item=staged;*revision_out=observed;return 0;
}
