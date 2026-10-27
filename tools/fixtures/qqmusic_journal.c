#define main volume_checks_main
#include "qqmusic_volume.c"
#undef main
#include "../../runtime/apps/qqmusic/qqmusic_journal.h"
extern int sony_ftruncate(int,long) __asm__("ftruncate");
extern long sony_lseek(int,long,int) __asm__("lseek");
static void initial(struct qq_job_record *r){
 memset(r,0,sizeof(*r));r->version=1;r->source_quality=1;r->bitrate_kbps=192;
 strcpy(r->identity,"9f8f6f83481e2e2f55a0dc13bcb34ecd6357e174c7380f03036775803d1f6552");strcpy(r->nonce,"0123456789abcdef");strcpy(r->song_mid,"SONG01");strcpy(r->media_mid,"MEDIA01");strcpy(r->filename,"O6M0MEDIA01.mgg");
 assert(snprintf(r->source,sizeof(r->source),"/contents/work/nested/.qq-source-%s-%s.part",r->identity,r->nonce)>0);
 assert(snprintf(r->temporary,sizeof(r->temporary),"/contents/work/nested/.qq-mp3-%s-%s.part",r->identity,r->nonce)>0);
 assert(snprintf(r->final,sizeof(r->final),"/contents/work/music/q-Artist/q-Album/q-Title [%s].mp3",r->identity)>0);
}
static void source(struct qq_job_record *r){struct hb_sha256 hash;r->source_bytes=100;hb_sha256_init(&hash);hb_sha256_update(&hash,(const unsigned char *)"source",6);hb_sha256_final(&hash,r->source_sha256);}
static int visited_good,visited_bad;
static int visit(void *context,const char *name,int status,const struct qq_journal_snapshot *snapshot){(void)context;assert(!strncmp(name,".qq-journal-",12));if(status==QQ_JOURNAL_OK){assert(snapshot->records==5&&snapshot->event==QQ_JOB_PUBLISHED);visited_good++;}else{assert(status==QQ_JOURNAL_INVALID&&!snapshot->records);visited_bad++;}return 0;}
int main(int argc,char **argv){
 struct qq_journal journal,collision;struct qq_journal_snapshot snapshot;struct qq_job_record r,bad;struct qq_volume volume;struct qq_storage_plan plan;struct qq_storage_policy policy={"/dev/mock-user","vfat"};
 char contents[4096],workspace[4096],nested[4096],file_path[160],name[128],extra[160];uint64_t required,size;struct hb_sha256 hash;int fd;unsigned count;unsigned char byte;
 assert(argc==2&&volume_checks_main(argc,argv)==0);base=argv[1];
 assert(snprintf(contents,sizeof(contents),"%s/contents",base)>0&&mkdir(contents,0700)==0);
 assert(snprintf(workspace,sizeof(workspace),"%s/work",contents)>0&&mkdir(workspace,0700)==0);path(nested,"nested");assert(mkdir(nested,0700)==0);
 memset(&plan,0,sizeof(plan));plan.metadata=QQ_JOURNAL_MAX_BYTES;plan.files[5]=1;plan.reserve=4096;qq_volume_init(&volume);active=allow_journal=1;
 assert(qq_volume_open(&volume,&policy,"/contents/work/nested",&plan,&required)==0);initial(&r);qq_journal_init(&journal);
 bad=r;strcpy(bad.source,"/tmp/forbidden");assert(qq_journal_append(&journal,&volume,&plan,QQ_JOB_BEGIN,&bad)<0&&journal.fd<0&&!journal.failed);
 assert(qq_journal_append(&journal,&volume,&plan,QQ_JOB_BEGIN,&r)==0&&journal.sequence==1);
 strcpy(name,journal.name);assert(snprintf(file_path,sizeof(file_path),"/proc/self/fd/%d/%s",volume.directory,name)>0);
 qq_journal_init(&collision);assert(qq_journal_append(&collision,&volume,&plan,QQ_JOB_BEGIN,&r)<0&&collision.failed&&qq_journal_close(&collision)==0);
 assert(qq_journal_read(&volume,&plan,name,&snapshot)==QQ_JOURNAL_OK&&snapshot.records==1&&snapshot.event==QQ_JOB_BEGIN&&!snapshot.last.source_bytes);
 bad=r;strcpy(bad.final,"/contents/work/music/q-Artist/q-Album/q-Other [9f8f6f83481e2e2f55a0dc13bcb34ecd6357e174c7380f03036775803d1f6552].mp3");source(&bad);assert(qq_journal_append(&journal,&volume,&plan,QQ_JOB_SOURCE_READY,&bad)<0&&!journal.failed);
 source(&r);assert(qq_journal_append(&journal,&volume,&plan,QQ_JOB_SOURCE_READY,&r)==0);
 assert(qq_journal_append(&journal,&volume,&plan,QQ_JOB_PUBLISHED,&r)<0);
 r.mp3_bytes=200;hb_sha256_init(&hash);hb_sha256_update(&hash,(const unsigned char *)"mp3",3);hb_sha256_final(&hash,r.mp3_sha256);
 assert(qq_journal_append(&journal,&volume,&plan,QQ_JOB_OUTPUT_READY,&r)==0);
 bad=r;bad.source_sha256[0]^=1;assert(qq_journal_append(&journal,&volume,&plan,QQ_JOB_PUBLISHING,&bad)<0);
 assert(qq_journal_append(&journal,&volume,&plan,QQ_JOB_PUBLISHING,&r)==0&&qq_journal_append(&journal,&volume,&plan,QQ_JOB_PUBLISHED,&r)==0);
 assert(qq_journal_append(&journal,&volume,&plan,QQ_JOB_REVIEW,&r)<0);size=journal.bytes;
 assert(qq_journal_close(&journal)==0&&qq_journal_close(&journal)==0);
 assert(qq_journal_read(&volume,&plan,name,&snapshot)==QQ_JOURNAL_OK&&snapshot.records==5&&snapshot.event==QQ_JOB_PUBLISHED&&!memcmp(snapshot.last.mp3_sha256,r.mp3_sha256,32));
 assert(qq_journal_scan(&volume,&plan,128,visit,0,&count)==QQ_JOURNAL_OK&&count==1&&visited_good==1&&!visited_bad);
 assert(snprintf(extra,sizeof(extra),"/proc/self/fd/%d/.qq-journal-broken.bin",volume.directory)>0);fd=__real_open(extra,O_WRONLY|O_CREAT|O_EXCL,0600);assert(fd>=0&&close(fd)==0);
 assert(qq_journal_scan(&volume,&plan,128,visit,0,&count)==QQ_JOURNAL_OK&&count==2&&visited_good==2&&visited_bad==1);
 assert(qq_journal_scan(&volume,&plan,1,visit,0,&count)==QQ_JOURNAL_REVIEW&&count==1&&unlink(extra)==0);
 fd=__real_open(file_path,O_WRONLY|O_APPEND|O_NOFOLLOW);assert(fd>=0&&write(fd,"x",1)==1&&close(fd)==0);
 assert(qq_journal_read(&volume,&plan,name,&snapshot)==QQ_JOURNAL_REVIEW&&snapshot.records==5&&snapshot.event==QQ_JOB_PUBLISHED);
 fd=__real_open(file_path,O_RDWR|O_NOFOLLOW);assert(fd>=0&&sony_ftruncate(fd,(long)size)==0&&sony_lseek(fd,88,SEEK_SET)==88);byte=0;assert(write(fd,&byte,1)==1&&close(fd)==0);
 assert(qq_journal_read(&volume,&plan,name,&snapshot)==QQ_JOURNAL_REVIEW&&!snapshot.records);
 fd=__real_open(file_path,O_RDWR|O_NOFOLLOW);assert(fd>=0&&sony_lseek(fd,88,SEEK_SET)==88);byte=1;assert(write(fd,&byte,1)==1&&sony_ftruncate(fd,(long)size-1)==0&&close(fd)==0);
 assert(qq_journal_read(&volume,&plan,name,&snapshot)==QQ_JOURNAL_REVIEW&&snapshot.records==4&&snapshot.event==QQ_JOB_PUBLISHING);
 assert(unlink(file_path)==0);initial(&r);qq_journal_init(&journal);assert(qq_journal_append(&journal,&volume,&plan,QQ_JOB_BEGIN,&r)==0);source(&r);readonly_mount=1;
 assert(qq_journal_append(&journal,&volume,&plan,QQ_JOB_SOURCE_READY,&r)<0&&journal.failed);readonly_mount=0;assert(qq_journal_append(&journal,&volume,&plan,QQ_JOB_SOURCE_READY,&r)<0&&qq_journal_close(&journal)==0);
 assert(qq_journal_read(&volume,&plan,name,&snapshot)==QQ_JOURNAL_OK&&snapshot.records==1&&snapshot.event==QQ_JOB_BEGIN);
 assert(unlink(file_path)==0&&symlink("/",file_path)==0&&qq_journal_read(&volume,&plan,name,&snapshot)==QQ_JOURNAL_INVALID&&!snapshot.records&&unlink(file_path)==0);
 assert(qq_journal_read(&volume,&plan,"../escape",&snapshot)==QQ_JOURNAL_INVALID);
 assert(qq_volume_close(&volume)==0);active=allow_journal=0;assert(rmdir(nested)==0&&rmdir(workspace)==0&&rmdir(contents)==0&&!forbid_writes);return 0;
}
