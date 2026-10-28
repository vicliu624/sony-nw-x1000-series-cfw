#define QQ_PREVIEW_RECEIPT_FIXTURE
#define main unused_volume_fixture_main
#include "qqmusic_volume.c"
#undef main
#include "../../runtime/apps/qqmusic/qqmusic_preview_receipt.h"
extern int __real_fsync(int);
static unsigned fault,exclusive_denied;
int __wrap_fsync(int fd){if(fault)return -1;return __real_fsync(fd);}
static int exclusive(void *p){(void)p;return exclusive_denied?-1:0;}
static void hash_bytes(const unsigned char *b,unsigned n,unsigned char *out){struct hb_sha256 h;hb_sha256_init(&h);hb_sha256_update(&h,b,n);hb_sha256_final(&h,out);}
int main(int argc,char **argv){
 struct qq_job_config config={0};struct qq_preview_receipt_store store={0};struct qq_preview_source_receipt r={0},out,bad;
 struct qq_worker_request request={0};struct qq_preview_source_job job={0};
 struct qq_stage_file source;struct qq_response_sink sink;struct qq_volume v;struct hb_sha256 h;uint64_t required;
 char contents[4096],work[4096],nested[4096],receipt_path[256];unsigned char bytes[384],corrupt[384],audio[16];unsigned i;int fd;
 assert(argc==2);base=argv[1];snprintf(contents,sizeof(contents),"%s/contents",base);assert(!mkdir(contents,0700));snprintf(work,sizeof(work),"%s/work",contents);assert(!mkdir(work,0700));path(nested,"nested");assert(!mkdir(nested,0700));
 config.volume.source="/dev/mock-user";config.volume.filesystem="vfat";config.workspace="/contents/work/nested";config.exclusive=exclusive;config.plan.source=4096;config.plan.files[0]=1;config.plan.metadata=131072;config.plan.files[5]=1;config.plan.reserve=4096;
 job.config=&config;job.request=&request;assert(!qq_preview_receipt_bind(&job,&store)&&job.retain==qq_preview_receipt_retain&&job.receipt_context==&store);assert(qq_preview_receipt_bind(&job,&store)<0);
 memset(r.identity,'a',64);memset(r.nonce,'b',16);strcpy(r.song_mid,"SONG01");strcpy(r.media_mid,"MEDIA01");strcpy(r.filename,"O6M0MEDIA01.mgg");r.bytes=16;memset(audio,0x67,sizeof(audio));hash_bytes(audio,sizeof(audio),r.sha256);
 assert(!qq_preview_receipt_encode(&r,bytes,384)&&!qq_preview_receipt_decode(bytes,384,&out)&&!memcmp(&r,&out,sizeof(r)));
 for(i=0;i<384;i++){memcpy(corrupt,bytes,384);corrupt[i]^=1;assert(qq_preview_receipt_decode(corrupt,384,&out)<0&&!out.bytes);}
 for(i=0;i<384;i++)assert(qq_preview_receipt_decode(bytes,i,&out)<0&&!out.bytes);
 bad=r;strcpy(bad.filename,"https://secret/");assert(qq_preview_receipt_encode(&bad,bytes,384)<0);bad=r;bad.song_mid[0]='/';assert(qq_preview_receipt_encode(&bad,bytes,384)<0);
 qq_volume_init(&v);active=1;assert(!qq_volume_open(&v,&config.volume,config.workspace,&config.plan,&required));active=0;
 qq_stage_init(&source);assert(!qq_stage_begin(&source,v.directory,v.device,r.identity,r.nonce,4096,0));sink=qq_stage_sink(&source);assert(!sink.write(sink.opaque,audio,sizeof(audio)));hb_sha256_init(&h);hb_sha256_update(&h,audio,sizeof(audio));hb_sha256_final(&h,r.sha256);assert(!sink.finish(sink.opaque,sizeof(audio),r.sha256));active=1;
 exclusive_denied=1;assert(qq_preview_receipt_retain(&store,&r,&source)<0);exclusive_denied=0;
 readonly_mount=1;assert(qq_preview_receipt_retain(&store,&r,&source)<0);readonly_mount=0;
 bad=r;bad.sha256[0]^=1;assert(qq_preview_receipt_retain(&store,&bad,&source)<0);
 assert(!job.retain(job.receipt_context,&r,&source));assert(qq_preview_receipt_retain(&store,&r,&source)<0);
 snprintf(receipt_path,sizeof(receipt_path),"/proc/self/fd/%d/.qq-preview-source-%s-%s.bin",v.directory,r.identity,r.nonce);
 fd=open(receipt_path,O_RDONLY|O_NOFOLLOW);assert(fd>=0&&read(fd,bytes,384)==384&&!close(fd));assert(!qq_preview_receipt_decode(bytes,384,&out)&&out.bytes==16&&!memcmp(out.sha256,r.sha256,32));
 fd=open(source.path,O_RDONLY|O_NOFOLLOW);assert(fd>=0&&read(fd,corrupt,16)==16&&!memcmp(audio,corrupt,16)&&!close(fd));
 /* An existing symlink cannot be replaced, and failed sync never removes
  * the original source or reports durable success. */
 active=0;assert(!unlink(receipt_path)&&!symlink("/etc/passwd",receipt_path));active=1;assert(qq_preview_receipt_retain(&store,&r,&source)<0);active=0;assert(!unlink(receipt_path));active=1;
 fault=1;assert(qq_preview_receipt_retain(&store,&r,&source)<0);fault=0;
 fd=open(source.path,O_RDONLY|O_NOFOLLOW);assert(fd>=0&&read(fd,corrupt,16)==16&&!memcmp(audio,corrupt,16)&&!close(fd));
 assert(!forbid_writes);active=0;assert(!qq_stage_discard(&source));assert(!qq_volume_close(&v));return 0;
}
