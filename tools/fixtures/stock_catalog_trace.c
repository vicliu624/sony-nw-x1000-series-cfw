/* Opt-in PC guest observation. Delegates original SQLite operations unchanged.
 * Logs filenames and numeric errors only, never SQL text or catalog contents. */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <stdio.h>
#include <unistd.h>
int sqlite3_open(const char *path,void **database){
 int (*next)(const char *,void **)=dlsym(RTLD_NEXT,"sqlite3_open");
 if(!next)return 14;
 int result=next(path,database),saved=errno;
 char line[256];int n=snprintf(line,sizeof line,"GUEST_CATALOG_OPEN path=%.160s result=%d\n",path?path:"(null)",result);
 if(n>0)(void)write(2,line,(unsigned)n<sizeof line?(unsigned)n:sizeof line-1);
 errno=saved;return result;
}
int sqlite3_prepare_v2(void *database,const char *sql,int bytes,void **statement,const char **tail){
 int (*next)(void *,const char *,int,void **,const char **)=dlsym(RTLD_NEXT,"sqlite3_prepare_v2");
 if(!next)return 21;
 int result=next(database,sql,bytes,statement,tail),saved=errno;
 if(result){char line[96];int n=snprintf(line,sizeof line,"GUEST_CATALOG_PREPARE result=%d\n",result);if(n>0)(void)write(2,line,(unsigned)n);}
 errno=saved;return result;
}
int sqlite3_step(void *statement){
 int (*next)(void *)=dlsym(RTLD_NEXT,"sqlite3_step");if(!next)return 21;
 int result=next(statement),saved=errno;
 if(result!=100&&result!=101&&result!=0){char line[96];int n=snprintf(line,sizeof line,"GUEST_CATALOG_STEP result=%d\n",result);if(n>0)(void)write(2,line,(unsigned)n);}
 errno=saved;return result;
}
int sqlite3_exec(void *database,const char *sql,void *callback,void *argument,char **error){
 int (*next)(void *,const char *,void *,void *,char **)=dlsym(RTLD_NEXT,"sqlite3_exec");if(!next)return 21;
 int result=next(database,sql,callback,argument,error),saved=errno;
 if(result){char line[96];int n=snprintf(line,sizeof line,"GUEST_CATALOG_EXEC result=%d\n",result);if(n>0)(void)write(2,line,(unsigned)n);}
 errno=saved;return result;
}
