#define _DEFAULT_SOURCE 1
#define main volume_checks_main
#include "qqmusic_volume.c"
#undef main
#include "../../runtime/apps/qqmusic/qqmusic_job.h"
#include "../../runtime/apps/qqmusic/qqmusic_journal.h"
#include "../../runtime/native/linux_process.h"
extern ssize_t sony_read(int,void *,size_t) __asm__("read");
#include <arpa/inet.h>
extern int __real_rename(const char *,const char *);extern int __real_fsync(int);
int __wrap_rename(const char *a,const char *b){return __real_rename(a,b);}int __wrap_fsync(int fd){return __real_fsync(fd);}
static struct qq_worker_import worker;static struct qq_worker_request request;
static unsigned char original[1048576],key[4096],der[8192],dn[2048];static size_t dn_bytes;
static br_x509_decoder_context decoder;static struct ares_options options;static struct in_addr nameserver;br_x509_trust_anchor anchor;
struct audit {uint32_t event;struct qq_job_record record;unsigned char digest[32];};
static struct context {struct qq_job_config config;int inherited[2],fail_event;unsigned detached,records;struct qq_volume journal_volume;struct qq_journal journal;} context;
static struct found {char name[128];struct qq_journal_snapshot snapshot;unsigned count;} found;
static int found_record(void *unused,const char *name,int status,const struct qq_journal_snapshot *snapshot){(void)unused;assert(status==QQ_JOURNAL_OK&&!found.count);strcpy(found.name,name);found.snapshot=*snapshot;found.count++;return 0;}
static void append_dn(void *unused,const void *p,size_t n){(void)unused;assert(n<=sizeof(dn)-dn_bytes);memcpy(dn+dn_bytes,p,n);dn_bytes+=n;}
static int exclusive(void *unused){(void)unused;return 0;}
static int denied(void *unused){(void)unused;return -1;}
static int detach(void *unused){(void)unused;assert(!context.detached);context.detached=1;return close(context.inherited[0])||close(context.inherited[1])?-1:0;}
static int record(void *unused,enum qq_job_event event,const struct qq_job_record *r){
 struct qq_volume volume;struct qq_storage_policy policy={"/dev/mock-user","vfat"};struct audit row;struct hb_sha256 hash;uint64_t required;char target[96];int fd,rc=0;size_t used=0;
 (void)unused;assert(context.detached&&(event==(enum qq_job_event)context.records||event==QQ_JOB_REVIEW));if((int)event==context.fail_event)return -1;
 if(context.journal_volume.directory<0&&qq_volume_open(&context.journal_volume,&policy,"/contents/work/nested",&context.config.plan,&required))return -1;
 if(qq_journal_append(&context.journal,&context.journal_volume,&context.config.plan,event,r))return -1;
 qq_volume_init(&volume);assert(qq_volume_open(&volume,&policy,"/contents/work/nested",&context.config.plan,&required)==0);
 assert(snprintf(target,sizeof(target),"/proc/self/fd/%d/.qq-job-audit.bin",volume.directory)>0);
 fd=__real_open(target,O_WRONLY|O_NOFOLLOW|(event==QQ_JOB_BEGIN?O_CREAT|O_EXCL:O_APPEND),0600);assert(fd>=0);
 memset(&row,0,sizeof(row));row.event=(uint32_t)event;row.record=*r;hb_sha256_init(&hash);hb_sha256_update(&hash,(unsigned char *)&row,(unsigned)((unsigned char *)row.digest-(unsigned char *)&row));hb_sha256_final(&hash,row.digest);
 while(used<sizeof(row)){ssize_t n=write(fd,(unsigned char *)&row+used,sizeof(row)-used);if(n<0&&errno==EINTR)continue;if(n<=0){rc=-1;break;}used+=(size_t)n;}
 if(fsync(fd))rc=-1;
 if(close(fd))rc=-1;
 if(fsync(volume.directory))rc=-1;
 if(qq_volume_close(&volume))rc=-1;
 if(event>=QQ_JOB_PUBLISHED){if(qq_journal_close(&context.journal))rc=-1;if(qq_volume_close(&context.journal_volume))rc=-1;}
 context.records++;return rc;
}
static int discard_emit(void *unused,const struct qq_runtime_import_progress *p){(void)unused;(void)p;assert(0);return -1;}
static int read_exact(int fd,void *data,size_t n){size_t used=0;while(used<n){ssize_t got=sony_read(fd,(unsigned char *)data+used,n-used);if(got<0&&errno==EINTR)continue;if(got<=0)return -1;used+=(size_t)got;}return 0;}
#ifdef QQ_JOB_BINDING
#include "qqmusic_binding.h"
#endif
int main(int argc,char **argv){
 char contents[4096],work[4096],nested[4096],music[4096],audit_path[4096],journal_path[4096];size_t bytes=0;ssize_t n;int fd,status,fault;unsigned i,pending=0,count,scanned,bitrate=192;unsigned long long clock;volatile int stop=0;struct audit rows[5];struct hb_sha256 hash;unsigned char digest[32],buffer[4096];uint64_t offset;const struct qq_runtime_import_ops *ops;
 assert((argc==8||argc==10)&&volume_checks_main(2,argv)==0);base=argv[1];assert(strcmp(argv[3],"-"));
 fd=open(argv[2],O_RDONLY);assert(fd>=0);while((n=sony_read(fd,original+bytes,sizeof(original)-bytes))>0){bytes+=(size_t)n;assert(bytes<sizeof(original));}assert(!n&&close(fd)==0);
 fd=open(argv[3],O_RDONLY);assert(fd>=0);n=sony_read(fd,key,sizeof(key));assert(n>0&&(size_t)n<sizeof(key)&&close(fd)==0);
 memset(&request,0,sizeof(request));strcpy(request.song.mid,"SONG01");strcpy(request.song.media_mid,"MEDIA01");strcpy(request.song.album_mid,"ALBUM01");request.song.album_id=42;strcpy(request.song.title,"接口标题");strcpy(request.song.artist,"接口艺人");strcpy(request.song.album,"接口专辑");
 assert(qq_resource_intent_init(&request.intent,"SONG01","MEDIA01",0,!strcmp(argv[4],"output-128")?QQ_MGG_96:!strcmp(argv[4],"output-320")?QQ_MGG_320:QQ_MGG_192)==0&&qq_export_plan(&request.song,&request.intent,0,&request.layout)==0);
 memcpy(request.resource.ekey,key,(size_t)n);memset(key,0,sizeof(key));request.resource.encrypted=1;strcpy(request.resource.filename,request.intent.filename);assert(snprintf(request.resource.url,sizeof(request.resource.url),"https://isure.stream.qqmusic.qq.com/%s?vkey=synthetic",request.intent.filename)>0);
 assert(hb_monotonic_millis(&clock)==0);request.now_ms=clock;request.expires_ms=clock+60000;
 assert(snprintf(contents,sizeof(contents),"%s/contents",base)>0&&mkdir(contents,0700)==0&&snprintf(work,sizeof(work),"%s/work",contents)>0&&mkdir(work,0700)==0&&snprintf(nested,sizeof(nested),"%s/nested",work)>0&&mkdir(nested,0700)==0&&snprintf(music,sizeof(music),"%s/music",work)>0&&mkdir(music,0700)==0&&snprintf(audit_path,sizeof(audit_path),"%s/.qq-job-audit.bin",nested)>0);
 fault=!strcmp(argv[4],"checkpoint-source")?1:(!strcmp(argv[4],"checkpoint-output")?2:(!strcmp(argv[4],"checkpoint-published")?4:0));
 memset(&context,0,sizeof(context));context.fail_event=fault?fault:-1;context.config.volume.source="/dev/mock-user";context.config.volume.filesystem="vfat";context.config.workspace="/contents/work/nested";context.config.music_root="/contents/work/music";
 qq_volume_init(&context.journal_volume);qq_journal_init(&context.journal);
 context.config.plan.source=bytes;context.config.plan.mp3=1048576;context.config.plan.metadata=131072;context.config.plan.files[0]=context.config.plan.files[2]=1;context.config.plan.files[5]=2;context.config.plan.directory_units=3;context.config.plan.reserve=4096;context.config.bitrate_kbps=192;context.config.exclusive=exclusive;context.config.checkpoint=record;
 fd=open(argv[7],O_RDONLY);assert(fd>=0);n=sony_read(fd,der,sizeof(der));assert(n>0&&(size_t)n<sizeof(der)&&close(fd)==0);br_x509_decoder_init(&decoder,append_dn,0);br_x509_decoder_push(&decoder,der,(size_t)n);assert(!br_x509_decoder_last_error(&decoder));memset(&anchor,0,sizeof(anchor));anchor.dn.data=dn;anchor.dn.len=dn_bytes;anchor.flags=BR_X509_TA_CA;anchor.pkey=*br_x509_decoder_get_pkey(&decoder);
 memset(&options,0,sizeof(options));nameserver.s_addr=htonl(INADDR_LOOPBACK);options.flags=ARES_FLAG_NOSEARCH|ARES_FLAG_NOALIASES;options.timeout=250;options.tries=1;options.servers=&nameserver;options.nservers=1;options.udp_port=htons((unsigned short)atoi(argv[5]));options.tcp_port=options.udp_port;options.lookups="b";
 context.config.network.anchors=&anchor;context.config.network.anchor_count=1;context.config.network.port=(unsigned)atoi(argv[6]);context.config.network.timeout_ms=5000;context.config.network.poll_ms=5;context.config.network.dns_options=&options;context.config.network.dns_mask=ARES_OPT_FLAGS|ARES_OPT_TIMEOUTMS|ARES_OPT_TRIES|ARES_OPT_SERVERS|ARES_OPT_UDP_PORT|ARES_OPT_TCP_PORT|ARES_OPT_LOOKUPS;
 {struct qq_job_config invalid=context.config;struct qq_worker_request bad=request;
  invalid.checkpoint=0;assert(qq_job_run(&invalid,&request,discard_emit,0,&stop)<0);
  invalid=context.config;invalid.exclusive=0;assert(qq_job_run(&invalid,&request,discard_emit,0,&stop)<0);
  invalid=context.config;invalid.exclusive=denied;assert(qq_job_run(&invalid,&request,discard_emit,0,&stop)<0);
  invalid=context.config;invalid.plan.metadata=0;assert(qq_job_run(&invalid,&request,discard_emit,0,&stop)<0);
  bad.expires_ms=bad.now_ms;assert(qq_job_run(&context.config,&bad,discard_emit,0,&stop)<0);bad=request;strcpy(bad.resource.filename,"wrong.mgg");assert(qq_job_run(&context.config,&bad,discard_emit,0,&stop)<0);qq_secret_clear(&bad,sizeof(bad));
 }
 active=allow_source=allow_output=allow_journal=1;
#ifdef QQ_JOB_BINDING
 if(argc==10){assert(!fault);run_binding(&context.config,&request,argv[8],argv[9],argv[4]);bitrate=binding_output_bitrate;count=5;}else
#endif
 {
 assert(pipe(context.inherited)==0&&qq_worker_import_init(&worker,qq_job_run,detach,&context.config)==0);ops=qq_worker_import_operations(&worker);
 assert(ops->begin(ops->context,&request.song,&request.intent,&request.resource,&request.layout,request.now_ms,request.expires_ms)==0);qq_resource_clear(&request.resource);
 status=0;for(i=0;!status&&i<3000;i++){struct qq_runtime_import_progress p;assert(hb_monotonic_millis(&clock)==0);status=ops->poll(ops->context,clock,&p);if(!status){assert(!p.published);pending++;hb_linux_wait_tick();}else if(fault)assert(status<0&&!p.published&&p.review);else assert(status==1&&p.published&&p.stage==3&&p.percent==100);}
 assert((fault?status<0:status==1)&&pending&&worker.reaped&&!context.detached&&!context.records);ops->cancel(ops->context);assert(close(context.inherited[0])==0&&close(context.inherited[1])==0);
 count=fault==1?2:fault==2?3:fault==4?4:5;fd=open(audit_path,O_RDONLY);assert(fd>=0&&read_exact(fd,rows,sizeof(rows[0])*count)==0&&sony_read(fd,buffer,1)==0&&close(fd)==0);
 for(i=0;i<count;i++){assert(rows[i].event==((fault==1||fault==2)&&i==count-1?QQ_JOB_REVIEW:i));hb_sha256_init(&hash);hb_sha256_update(&hash,(unsigned char *)&rows[i],(unsigned)((unsigned char *)rows[i].digest-(unsigned char *)&rows[i]));hb_sha256_final(&hash,digest);assert(!memcmp(digest,rows[i].digest,32));}
 }
 {struct qq_volume volume;struct qq_storage_policy policy={"/dev/mock-user","vfat"};uint64_t required;qq_volume_init(&volume);assert(qq_volume_open(&volume,&policy,"/contents/work/nested",&context.config.plan,&required)==0&&qq_journal_scan(&volume,&context.config.plan,128,found_record,0,&scanned)==QQ_JOURNAL_OK&&scanned==1&&found.count==1&&qq_volume_close(&volume)==0);}
 assert(found.snapshot.records==count&&snprintf(journal_path,sizeof(journal_path),"%s/%s",nested,found.name)>0);
 if(argc==10)assert(found.snapshot.event==QQ_JOB_PUBLISHED);else{
 assert(found.snapshot.event==(enum qq_job_event)rows[count-1].event);
 assert(!strcmp(found.snapshot.last.source,rows[count-1].record.source)&&!strcmp(found.snapshot.last.temporary,rows[count-1].record.temporary)&&!strcmp(found.snapshot.last.final,rows[count-1].record.final)&&!memcmp(found.snapshot.last.source_sha256,rows[count-1].record.source_sha256,32)&&!memcmp(found.snapshot.last.mp3_sha256,rows[count-1].record.mp3_sha256,32));
 }
 {struct qq_job_record *saved=&found.snapshot.last;const char *output=fault==2?saved->temporary:saved->final;
 assert(saved->version==1&&saved->source_quality==(unsigned)request.intent.quality&&saved->bitrate_kbps==bitrate&&strlen(saved->nonce)==16&&!strcmp(saved->filename,request.intent.filename)&&saved->source_bytes==bytes&&!strcmp(saved->song_mid,"SONG01"));
 fd=open(saved->source,O_RDONLY|O_NOFOLLOW);assert(fd>=0);offset=0;hb_sha256_init(&hash);while((n=sony_read(fd,buffer,sizeof(buffer)))>0){assert((size_t)n<=bytes-offset&&!memcmp(buffer,original+(size_t)offset,(size_t)n));hb_sha256_update(&hash,buffer,(unsigned)n);offset+=(size_t)n;}assert(!n&&offset==bytes&&close(fd)==0);hb_sha256_final(&hash,digest);assert(!memcmp(digest,saved->source_sha256,32));
 if(fault!=1){fd=open(output,O_RDONLY|O_NOFOLLOW);assert(fd>=0);offset=0;hb_sha256_init(&hash);while((n=sony_read(fd,buffer,sizeof(buffer)))>0){if(!fault)assert(write(1,buffer,(size_t)n)==n);hb_sha256_update(&hash,buffer,(unsigned)n);offset+=(size_t)n;}assert(!n&&offset==saved->mp3_bytes&&close(fd)==0);hb_sha256_final(&hash,digest);assert(!memcmp(digest,saved->mp3_sha256,32));}
 /* Test-only cleanup after proving data survives the worker's exit. */
 {char real_final[4096],real_source[4096],*slash;assert(snprintf(real_final,sizeof(real_final),"%s%s",base,output)>0&&snprintf(real_source,sizeof(real_source),"%s%s",base,saved->source)>0);if(fault!=1)assert(unlink(real_final)==0);assert(unlink(real_source)==0);if(!fault||fault==4){slash=strrchr(real_final,'/');*slash=0;assert(rmdir(real_final)==0);slash=strrchr(real_final,'/');*slash=0;assert(rmdir(real_final)==0);}}
 }
 active=allow_source=allow_output=allow_journal=0;if(argc==8)assert(unlink(audit_path)==0);
#ifdef QQ_JOB_BINDING
 if(argc==10)assert(rmdir(binding_music)==0);
#endif
 assert(unlink(journal_path)==0&&rmdir(music)==0&&rmdir(nested)==0&&rmdir(work)==0&&rmdir(contents)==0&&!forbid_writes);return 0;
}
