/* Read-only schema diagnostic. No controls, radio, firmware or personal song-field query. */
#include <stdio.h>
#include <string.h>
#include <stdint.h>
typedef struct sqlite3 sqlite3;typedef struct sqlite3_stmt sqlite3_stmt;
extern int sqlite3_open_v2(const char *,sqlite3 **,int,const char *);
extern int sqlite3_close(sqlite3 *);
extern int sqlite3_exec(sqlite3 *,const char *,void *,void *,char **);
extern int sqlite3_prepare_v2(sqlite3 *,const char *,int,sqlite3_stmt **,const char **);
extern int sqlite3_step(sqlite3_stmt *);
extern int sqlite3_finalize(sqlite3_stmt *);
extern int sqlite3_column_int(sqlite3_stmt *,int);
extern int sqlite3_column_type(sqlite3_stmt *,int);
extern const unsigned char *sqlite3_column_text(sqlite3_stmt *,int);
extern const char *sqlite3_libversion(void);
extern int sqlite3_set_authorizer(sqlite3 *,int (*)(void *,int,const char *,const char *,const char *,const char *),void *);
extern void sqlite3_progress_handler(sqlite3 *,int,int (*)(void *),void *);
#ifdef XW_INSPECT_FIXTURE
extern void _exit(int);
#endif
static int authorize(void *context,int action,const char *a,const char *b,const char *database,const char *source){
 (void)a;(void)database;(void)source;
 if(context&&action==31&&b&&!strcmp(b,"count"))return 0;
 return action==20||action==21?0:1;
}
static int progress(void *context){unsigned *budget=context;if(!*budget)return 1;--*budget;return 0;}
static int rows(sqlite3 *db,const char *sql,unsigned columns,unsigned text_column){
 sqlite3_stmt *statement=0;int rc=sqlite3_prepare_v2(db,sql,-1,&statement,0),result=1;unsigned count=0;
 if(rc){printf("prepare_error=%d\n",rc);return 1;}
 while((rc=sqlite3_step(statement))==100){
  if(++count>128){puts("row_limit_exceeded=128");goto done;}
  for(unsigned i=0;i<columns;i++){
   if(i==text_column){const unsigned char *text=sqlite3_column_text(statement,(int)i);printf("%s%.96s",i?"\t":"",text?(const char *)text:"");}
   else if(sqlite3_column_type(statement,(int)i)==5)printf("%sNULL",i?"\t":"");
   else printf("%s%d",i?"\t":"",sqlite3_column_int(statement,(int)i));
  }
  putchar('\n');
 }
 if(rc==101)result=0;else printf("query_error=%d\n",rc);
done:
 if(sqlite3_finalize(statement))result=1;return result;
}
static int inspect(const char *path,int types){
 sqlite3 *db=0;unsigned budget=types?512:64;int result=1,rc;
 printf("player-schema-inspect=0.2.0\nsqlite=%s\npath=%s\nmode=READONLY\n",sqlite3_libversion(),path);
 rc=sqlite3_open_v2(path,&db,1,0);
 if(rc){printf("open_error=%d\n",rc);if(db)sqlite3_close(db);return 2;}
 /* Connection-local memory setting, not a persistent database pragma. */
 if(sqlite3_exec(db,"PRAGMA temp_store=MEMORY",0,0,0))goto done;
 if(sqlite3_set_authorizer(db,authorize,(void *)(uintptr_t)(types!=0)))goto done;
 sqlite3_progress_handler(db,1000,progress,&budget);
 if(types){
  puts("OBJECT_TYPES: object_type / media_type / format / count");
  result=rows(db,"SELECT object_type,media_type,format,count(*) FROM object_body GROUP BY object_type,media_type,format ORDER BY object_type,media_type,format LIMIT 129",4,UINT32_MAX);
  goto done;
 }
 puts("OBJECT_BODY_COLUMNS: ordinal / declared-name");
 /* The bound SELECT has no rows or personal metadata; successful preparation
  * verifies that the original object-identity and ordering columns exist. */
 sqlite3_stmt *shape=0;
 rc=sqlite3_prepare_v2(db,"SELECT object_id,parent_id,reference_id,object_type,tree_id,child_index,title,m1_id,m2_id,m3_id FROM object_body LIMIT 0",-1,&shape,0);
 if(rc){printf("object_shape_error=%d\n",rc);goto done;}
 if(sqlite3_finalize(shape))goto done;
 puts("object_shape=present");puts("SCHEMA: prop_type / meta_id / data_type / prop_name");
 result=rows(db,"SELECT prop_type,meta_id,data_type,prop_name FROM schema ORDER BY prop_type,meta_id LIMIT 128",4,3);
done:
 sqlite3_progress_handler(db,0,0,0);
 if(sqlite3_close(db))result=1;printf("result=%s\n",result?"ERROR":"OK");return result;
}
int main(int argc,char **argv){
 int result;
 if(argc==2&&!strcmp(argv[1],"--version")){puts("player-schema-inspect 0.2.0");return 0;}
 if(argc==2&&!strcmp(argv[1],"--help")){puts("Read-only stock catalog schema diagnostic. --inspect /db/MTPDB.dat or --inspect /contents/MTPDB.dat. Use --inspect-types for aggregate object_type/media_type/format counts only. No song titles, paths or IDs. No firmware, controls, scans or writes.");return 0;}
 if(argc!=3)return 64;
#ifdef XW_INSPECT_FIXTURE
 if(strcmp(argv[1],"--fixture")&&strcmp(argv[1],"--fixture-types"))return 64;
#else
 if((strcmp(argv[1],"--inspect")&&strcmp(argv[1],"--inspect-types"))||(strcmp(argv[2],"/db/MTPDB.dat")&&strcmp(argv[2],"/contents/MTPDB.dat")))return 64;
#endif
 result=inspect(argv[2],!strcmp(argv[1],"--inspect-types")||!strcmp(argv[1],"--fixture-types"));fflush(stdout);
#ifdef XW_INSPECT_FIXTURE
 /* QEMU user mode cannot run the original LinuxThreads manager teardown. */
 _exit(result);
#endif
 return result;
}
