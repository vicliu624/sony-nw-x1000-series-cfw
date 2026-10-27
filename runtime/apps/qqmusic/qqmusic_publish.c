#define _XOPEN_SOURCE 700
#include "qqmusic_publish.h"
#include "qqmusic_source.h"
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <string.h>
#include "../../store/target_abi.h"
extern int sony_snprintf(char *,size_t,const char *,...) __asm__("snprintf");
extern int sony_rename(const char *,const char *) __asm__("rename");
static int file_same(const char *path,uint64_t device,uint64_t inode,uint64_t bytes){struct stat s;return !lstat(path,&s)&&S_ISREG(s.st_mode)&&s.st_nlink==1&&(uint64_t)s.st_dev==device&&(uint64_t)s.st_ino==inode&&(uint64_t)s.st_size==bytes;}
static int lock_same(const char *path,const struct stat *lock){struct stat s;return !lstat(path,&s)&&S_ISDIR(s.st_mode)&&s.st_dev==lock->st_dev&&s.st_ino==lock->st_ino;}
int qq_publish_mp3(struct qq_output_file *output,struct qq_export_directory *dest,const struct qq_storage_plan *plan,const struct qq_import_report *expected,struct qq_publish_report *report){
 struct qq_source_file reader;struct qq_codec_io io;struct qq_mp3_report mp3;struct stat lock,existing;
 struct qq_stage_file *file;char target[320],lock_path[96];const char *name;size_t n,i;uint64_t required;int rc=QQ_PUBLISH_ERROR,locked=0,moved=0;
 if(report)memset(report,0,sizeof(*report));
 if(!output||!dest||!plan||!expected||!report||!plan->directory_units||output->stage.state!=QQ_STAGE_READY||!output->volume||dest->volume.device!=output->stage.device||dest->volume.system_device==dest->volume.device)return rc;
 file=&output->stage;name=strrchr(file->path,'/');n=strnlen(dest->filename,sizeof(dest->filename));
 if(!name||strncmp(name+1,".qq-mp3-",8)||strlen(name+1)<72||n<71||n>=sizeof(dest->filename)||strcmp(dest->filename+n-4,".mp3")||memcmp(dest->filename+n-69,name+9,64)||dest->filename[n-70]!='['||dest->filename[n-5]!=']')return rc;
 for(i=0;i<n;i++)if((unsigned char)dest->filename[i]<32||strchr("/\\:*?\"<>|",dest->filename[i]))return rc;
 if(qq_volume_recheck(output->volume,plan,&required)||qq_volume_recheck(&dest->volume,plan,&required))return rc;
 if(sony_snprintf(target,sizeof(target),"/proc/self/fd/%d/%s",dest->volume.directory,dest->filename)<0||sony_snprintf(lock_path,sizeof(lock_path),"/proc/self/fd/%d/.qq-publish-lock",dest->volume.directory)<0)return rc;
 if(sony_snprintf(report->path,sizeof(report->path),"%s/%s",dest->volume.path,dest->filename)<0||strlen(dest->volume.path)+n+1>=sizeof(report->path)){report->path[0]=0;return rc;}
 qq_source_init(&reader);if(qq_source_open_output(&reader,output->volume,plan,file,file->stop))goto done;
 memset(&io,0,sizeof(io));io.source=&reader;io.source_bytes=reader.bytes;io.read_at=qq_source_read_at;io.stop=file->stop;
 if(qq_mp3_verify(&io,expected,&mp3))goto done;
 if(qq_source_close(&reader))goto done;
 if(mkdir(lock_path,0700)){rc=errno==EEXIST?QQ_PUBLISH_BUSY:QQ_PUBLISH_ERROR;goto done;}
 locked=1;if(lstat(lock_path,&lock)||!S_ISDIR(lock.st_mode)||(uint64_t)lock.st_dev!=file->device){rc=QQ_PUBLISH_REVIEW;goto done;}
 if(fsync(dest->volume.directory)||qq_volume_recheck(output->volume,plan,&required)||qq_volume_recheck(&dest->volume,plan,&required)||(file->stop&&*file->stop)||!file_same(file->path,file->device,file->inode,file->bytes))goto done;
 if(!lstat(target,&existing)){rc=QQ_PUBLISH_CONFLICT;goto done;}if(errno!=ENOENT)goto done;
 if(sony_rename(file->path,target)){if(!file_same(file->path,file->device,file->inode,file->bytes)){file->state=QQ_STAGE_REVIEW;rc=QQ_PUBLISH_REVIEW;}goto done;}
 moved=1;file->state=QQ_STAGE_REVIEW;report->bytes=file->bytes;memcpy(report->digest,file->digest,32);
 /* FAT inode behavior after rename is not assumed; validate final fd/path
  * identity and all bytes via the same read-only reader, using its new inode. */
 if(lstat(target,&existing)||!S_ISREG(existing.st_mode)||existing.st_nlink!=1||(uint64_t)existing.st_dev!=file->device||(uint64_t)existing.st_size!=file->bytes)goto uncertain;
 {
  struct hb_sha256 hash;unsigned char buffer[4096],digest[32];uint64_t offset=0;int bad=0;
  reader.parent=dup(dest->volume.directory);reader.fd=open(target,O_RDONLY|O_NOFOLLOW|O_NONBLOCK);reader.device=file->device;reader.parent_inode=dest->volume.inode;reader.inode=(uint64_t)existing.st_ino;reader.bytes=file->bytes;reader.stop=file->stop;strcpy(reader.path,target);
  hb_sha256_init(&hash);
  while(offset<file->bytes){unsigned count=(unsigned)((file->bytes-offset)>sizeof(buffer)?sizeof(buffer):file->bytes-offset);if(qq_source_read_at(&reader,offset,buffer,count)!=(int)count){bad=1;break;}hb_sha256_update(&hash,buffer,count);offset+=count;}
  hb_sha256_final(&hash,digest);if(memcmp(digest,file->digest,32))bad=1;
  qq_secret_clear(&hash,sizeof(hash));qq_secret_clear(buffer,sizeof(buffer));qq_secret_clear(digest,sizeof(digest));if(qq_source_close(&reader))bad=1;if(bad)goto uncertain;
 }
 if(fsync(file->parent)||fsync(dest->volume.directory)||qq_volume_recheck(output->volume,plan,&required)||qq_volume_recheck(&dest->volume,plan,&required))goto uncertain;
 rc=QQ_PUBLISH_OK;goto done;
uncertain:rc=QQ_PUBLISH_REVIEW;
done:
 if(qq_source_close(&reader)&&rc==QQ_PUBLISH_OK)rc=moved?QQ_PUBLISH_REVIEW:QQ_PUBLISH_ERROR;
 if(locked&&rc!=QQ_PUBLISH_REVIEW){if(!lock_same(lock_path,&lock)||rmdir(lock_path)||fsync(dest->volume.directory))rc=QQ_PUBLISH_REVIEW;}
 if(moved||file->state==QQ_STAGE_REVIEW){if(file->parent>=0){if(close(file->parent))rc=QQ_PUBLISH_REVIEW;file->parent=-1;}if(rc==QQ_PUBLISH_OK){file->state=QQ_STAGE_PUBLISHED;file->path[0]=0;}}
 if(rc!=QQ_PUBLISH_OK&&!moved&&rc!=QQ_PUBLISH_REVIEW)memset(report,0,sizeof(*report));
 return rc;
}
