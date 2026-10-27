#include "../../runtime/apps/qqmusic/qqmusic_id3.h"
#include <assert.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
static unsigned char tag[65536],cover[16384];
static void erased(void) {size_t i;for(i=0;i<sizeof(tag);i++) assert(tag[i]==0);}
int main(int argc,char **argv) {
 struct qq_track_tags tags={"\xe6\xb5\x8b\xe8\xaf\x95\xe6\xad\x8c\xe6\x9b\xb2 \xf0\x9f\x8e\xb5","\xe6\xb5\x8b\xe8\xaf\x95\xe6\xad\x8c\xe6\x89\x8b","\xe6\xb5\x8b\xe8\xaf\x95\xe4\xb8\x93\xe8\xbe\x91","Album Artist","3/12","1/2","2026",0,0,0,0,0,0,0};
 size_t bytes;ssize_t n;int fd;
 assert(argc==2);fd=open(argv[1],O_RDONLY);assert(fd>=0);n=read(fd,cover,sizeof(cover));assert(n>0&&n<(ssize_t)sizeof(cover)&&close(fd)==0);
 tags.jpeg=cover;tags.jpeg_bytes=(size_t)n;
 assert(qq_id3_build(&tags,tag,sizeof(tag),&bytes)==0&&bytes>10&&!memcmp(tag,"ID3\3\0\0",6));
 assert(qq_id3_build(&tags,tag,11,&bytes)<0&&bytes==0);
 tags.title="\xc0\x80";assert(qq_id3_build(&tags,tag,sizeof(tag),&bytes)<0);erased();
 tags.title="valid";tags.year="26";assert(qq_id3_build(&tags,tag,sizeof(tag),&bytes)<0);erased();
 tags.year="2026";tags.track="../3";assert(qq_id3_build(&tags,tag,sizeof(tag),&bytes)<0);erased();
 tags.track="3/12";tags.title="\xe6\xb5\x8b\xe8\xaf\x95\xe6\xad\x8c\xe6\x9b\xb2 \xf0\x9f\x8e\xb5";
 assert(qq_id3_build(&tags,tag,sizeof(tag),&bytes)==0);
 assert(write(1,tag,bytes)==(ssize_t)bytes);return 0;
}
