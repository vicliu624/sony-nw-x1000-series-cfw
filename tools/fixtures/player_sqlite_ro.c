/* ABI probe only: original Sony SQLite, synthetic database, no player access. */
#include <assert.h>
#include <stdio.h>
#include <string.h>
typedef struct sqlite3 sqlite3;typedef struct sqlite3_stmt sqlite3_stmt;
extern void _exit(int);
extern int sqlite3_open_v2(const char *,sqlite3 **,int,const char *);
extern int sqlite3_close(sqlite3 *);
extern int sqlite3_exec(sqlite3 *,const char *,void *,void *,char **);
extern int sqlite3_set_authorizer(sqlite3 *,int (*)(void *,int,const char *,const char *,const char *,const char *),void *);
extern int sqlite3_prepare_v2(sqlite3 *,const char *,int,sqlite3_stmt **,const char **);
extern int sqlite3_step(sqlite3_stmt *);
extern int sqlite3_finalize(sqlite3_stmt *);
extern int sqlite3_column_int(sqlite3_stmt *,int);
extern const unsigned char *sqlite3_column_text(sqlite3_stmt *,int);
extern const char *sqlite3_libversion(void);
static int allow_read(void *unused,int operation,const char *a,const char *b,const char *c,const char *d){(void)unused;(void)a;(void)b;(void)c;(void)d;return operation==20||operation==21?0:1;}
int main(int argc,char **argv){
 sqlite3 *database=0;sqlite3_stmt *statement=0;int rc;
 if(argc!=3)return 64;
 printf("SQLite version: %s\n",sqlite3_libversion());fflush(stdout);
 assert(!strncmp(sqlite3_libversion(),"3.6.6",5));
 assert(sqlite3_open_v2(argv[2],&database,1,0)==14);if(database)assert(!sqlite3_close(database));database=0;
 assert(!sqlite3_open_v2(argv[1],&database,1,0));
 rc=sqlite3_exec(database,"UPDATE object_body SET title='MUST NOT WRITE'",0,0,0);assert(rc==8);
 assert(!sqlite3_set_authorizer(database,allow_read,0));
 assert(sqlite3_exec(database,"UPDATE object_body SET title='MUST NOT WRITE'",0,0,0)==23);
 assert(!sqlite3_prepare_v2(database,"SELECT object_id,title,reference_id,child_index FROM object_body WHERE parent_id=9 ORDER BY child_index,object_id LIMIT 2",-1,&statement,0));
 assert(sqlite3_step(statement)==100);assert(sqlite3_column_int(statement,0)==12);assert(!strcmp((const char *)sqlite3_column_text(statement,1),"First song"));assert(sqlite3_column_int(statement,2)==100);assert(sqlite3_column_int(statement,3)==0);
 assert(sqlite3_step(statement)==100);assert(sqlite3_column_int(statement,0)==11);assert(!strcmp((const char *)sqlite3_column_text(statement,1),"Second song"));assert(sqlite3_column_int(statement,3)==1);
 assert(sqlite3_step(statement)==101);assert(!sqlite3_finalize(statement));assert(!sqlite3_close(database));
 puts("Original SQLite: read-only open, no creation, rejected update and ordered reference rows passed");fflush(stdout);_exit(0);
}
