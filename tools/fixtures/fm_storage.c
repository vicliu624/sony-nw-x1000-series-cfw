#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#include "../../runtime/apps/fm-radio/fm_storage.h"
#include "../../runtime/store/target_abi.h"
static int io_mode,writes,syncs,lease_valid=1;
extern ssize_t __real_write(int,const void *,size_t);
extern int __real_fsync(int);
ssize_t __wrap_write(int fd,const void *p,size_t n){
 writes++;
 if(io_mode==1&&writes==1){errno=EINTR;return -1;}
 if(io_mode==1&&writes==2&&n>13)n=13;
 if(io_mode==2){errno=EIO;return -1;}
 return __real_write(fd,p,n);
}
int __wrap_fsync(int fd){syncs++;if((io_mode==3&&syncs==1)||(io_mode==4&&syncs==2)){errno=EIO;return -1;}return __real_fsync(fd);}
static int guard(void *p){(void)p;return lease_valid?0:-1;}
static int tune(void *p,int khz){(void)p;(void)khz;return 0;}
static int sample(void *p,int *v){(void)p;*v=0;return 0;}
static void snapshot(struct fm_radio *r,struct fm_state *s,int khz){assert(!fm_tune(r,khz)&&!fm_favorite(r,"FAVORITE")&&!fm_state_capture(r,s));}
static void remove_file(const char *directory,const char *name){char p[512];snprintf(p,sizeof(p),"%s/%s",directory,name);if(unlink(p))assert(errno==ENOENT);}
int main(int argc,char **argv){
 assert(argc==2);const char *directory=argv[1];int fd=open(directory,O_RDONLY|O_DIRECTORY|O_NOFOLLOW);assert(fd>=0);
 struct fm_storage store;fm_storage_init(&store);
 int root=open("/",O_RDONLY|O_DIRECTORY);assert(root>=0);assert(fm_storage_bind(&store,root,guard,0)==FM_STORAGE_BOUNDARY);assert(!close(root));
 assert(!fm_storage_bind(&store,fd,guard,0));assert(!close(fd));
 struct fm_band band={76000,90000,100};struct fm_radio radio;struct fm_state state,loaded;
 assert(!fm_init(&radio,band,(struct fm_backend){0,tune,sample}));
 assert(fm_storage_load(&store,band,&loaded)==FM_STORAGE_EMPTY);
 snapshot(&radio,&state,82500);assert(!fm_storage_save(&store,&state)&&store.generation==1);
 snapshot(&radio,&state,88900);assert(!fm_storage_save(&store,&state)&&store.generation==2);
 assert(!fm_storage_load(&store,band,&loaded)&&loaded.frequency==88900&&loaded.favorite_count==2);
 /* Corrupt latest B, then recover A without changing either file on load. */
 char file[512];snprintf(file,sizeof(file),"%s/state-b.bin",directory);int broken=open(file,O_WRONLY|O_TRUNC);assert(broken>=0&&__real_write(broken,"BAD",3)==3&&!close(broken));
 assert(!fm_storage_load(&store,band,&loaded)&&loaded.frequency==82500&&loaded.favorite_count==1);
 snapshot(&radio,&state,80000);io_mode=1;writes=syncs=0;assert(!fm_storage_save(&store,&state)&&writes>=3);io_mode=0;
 assert(!fm_storage_load(&store,band,&loaded)&&loaded.frequency==80000);
 for(int mode=2;mode<=3;mode++){io_mode=mode;writes=syncs=0;snapshot(&radio,&state,81000);assert(fm_storage_save(&store,&state)<0);io_mode=0;assert(!fm_storage_load(&store,band,&loaded)&&loaded.frequency==80000);}
 io_mode=4;syncs=0;assert(fm_storage_save(&store,&state)==FM_STORAGE_UNCERTAIN);io_mode=0;
 assert(!fm_storage_load(&store,band,&loaded)&&loaded.frequency==81000);
 lease_valid=0;assert(fm_storage_save(&store,&state)==FM_STORAGE_BOUNDARY);lease_valid=1;
 /* A link at the reserved temporary name is never followed or removed. */
 char link[512],foreign[512];snprintf(link,sizeof(link),"%s/state.tmp",directory);snprintf(foreign,sizeof(foreign),"%s/foreign",directory);
 int other=open(foreign,O_WRONLY|O_CREAT|O_EXCL,0600);assert(other>=0&&__real_write(other,"KEEP",4)==4&&!close(other));
 assert(!symlink(foreign,link));assert(fm_storage_save(&store,&state)==FM_STORAGE_BOUNDARY);struct stat st;assert(!lstat(link,&st)&&S_ISLNK(st.st_mode));assert(!unlink(link));
 other=open(foreign,O_RDONLY);char keep[4];assert(other>=0&&read(other,keep,4)==4&&!memcmp(keep,"KEEP",4)&&!close(other));assert(!unlink(foreign));
 /* A bounded orphan temporary file is recovered on the next commit. */
 other=open(link,O_WRONLY|O_CREAT|O_EXCL,0600);assert(other>=0&&__real_write(other,"partial",7)==7&&!close(other));assert(!fm_storage_save(&store,&state));
 /* Upgrade previous90MHz snapshots, then persist a108MHz selection. */
 assert(!fm_storage_load(&store,(struct fm_band){76000,108000,100},&loaded)&&loaded.band.high==108000);
 state=loaded;state.frequency=108000;assert(!fm_storage_save(&store,&state));
 assert(!fm_storage_load(&store,(struct fm_band){76000,108000,100},&loaded)&&loaded.frequency==108000);
 assert(!fm_storage_close(&store)&&!fm_storage_close(&store));
 remove_file(directory,"state-a.bin");remove_file(directory,"state-b.bin");remove_file(directory,"state.tmp");
 const char *good="/dev/root / ext2 rw 0 0\n/dev/mtdblock/2 /contents vfat rw,utf8 0 0\n";
 assert(fm_storage_mounts_ok(good,(unsigned)strlen(good)));
 const char *bad="/dev/root / ext2 rw 0 0\n/dev/mtdblock/1 /contents vfat rw 0 0\n";assert(!fm_storage_mounts_ok(bad,(unsigned)strlen(bad)));
 const char *ro="/dev/root / ext2 rw 0 0\n/dev/mtdblock/2 /contents vfat ro 0 0\n";assert(!fm_storage_mounts_ok(ro,(unsigned)strlen(ro)));
 assert(!fm_storage_mounts_ok(good,(unsigned)strlen(good)-1));
 return 0;
}
