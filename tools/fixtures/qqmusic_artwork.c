#include "../../runtime/apps/qqmusic/qqmusic_image.h"
#include "../../runtime/apps/qqmusic/qqmusic_metadata.h"
#include <assert.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdlib.h>
extern ssize_t sony_read(int,void *,size_t) __asm__("read");
static unsigned char *input,*jpeg,*picture,*attached,*tag;
static char *encoded;
static struct qq_metadata metadata;
static struct qq_song song;
static struct qq_resource_intent intent;
static void cleanup(void) {free(input);free(jpeg);free(picture);free(attached);free(tag);free(encoded);}
static size_t load(const char *path,void *out,size_t cap) {
 int fd=open(path,O_RDONLY);size_t used=0;ssize_t n;assert(fd>=0);
 while((n=sony_read(fd,(unsigned char *)out+used,cap-used))>0) {used+=(size_t)n;assert(used<cap);}
 assert(n==0&&close(fd)==0);return used;
}
int main(int argc,char **argv) {
 size_t n,b64,bytes,picture_bytes,tag_bytes;unsigned w,h,pw,ph;struct qq_track_tags tags;
 assert(argc==3||argc==4);input=malloc(524288);jpeg=malloc(524288);picture=malloc(524288);attached=malloc(524288);tag=malloc(1048576);encoded=malloc(1048576);assert(input&&jpeg&&picture&&attached&&tag&&encoded);
 n=load(argv[1],input,524288);b64=load(argv[2],encoded,1048576);
 if(argc==4&&!strcmp(argv[3],"reject-image")) {assert(qq_image_jpeg(input,n,jpeg,524288,&bytes,&w,&h)<0);cleanup();return 0;}
 if(argc==4&&!strcmp(argv[3],"reject-picture")) {assert(qq_picture_jpeg(encoded,b64,picture,524288,&bytes,&w,&h)<0);cleanup();return 0;}
 if(argc==4&&!strcmp(argv[3],"nonfront")) {assert(qq_picture_jpeg(encoded,b64,picture,524288,&bytes,&w,&h)==1&&!bytes);cleanup();return 0;}
 assert(qq_image_jpeg(input,n,jpeg,524288,&bytes,&w,&h)==0&&bytes&&w==32&&h==24);
 assert(qq_picture_jpeg(encoded,b64,picture,524288,&picture_bytes,&pw,&ph)==0&&picture_bytes==bytes&&w==pw&&h==ph&&!memcmp(jpeg,picture,bytes));
 qq_metadata_init(&metadata);assert(qq_metadata_artwork_buffer(&metadata,attached,524288)==0);
 assert(qq_metadata_comment(&metadata,"METADATA_BLOCK_PICTURE",22,encoded,b64)==0&&metadata.source_cover);
 memcpy(song.mid,"SONG01",7);memcpy(song.media_mid,"MEDIA01",8);memcpy(song.album_mid,"ALBUM01",8);
 memcpy(intent.song_mid,"SONG01",7);memcpy(intent.media_mid,"MEDIA01",8);
 assert(qq_metadata_fill(&metadata,&song,&intent,0)==0);
 assert(qq_metadata_album_cover(&metadata,"ALBUM01",(const unsigned char *)"bad",3)==0);
 assert(qq_metadata_tags(&metadata,&tags)==0&&tags.jpeg_bytes==bytes&&!memcmp(tags.jpeg,jpeg,bytes));
 assert(qq_id3_build(&tags,tag,1048576,&tag_bytes)==0);
 assert(qq_metadata_album_cover(&metadata,"OTHER",input,n)<0&&qq_metadata_tags(&metadata,&tags)<0);
 qq_metadata_init(&metadata);assert(qq_metadata_artwork_buffer(&metadata,attached,524288)==0);
 assert(qq_metadata_fill(&metadata,&song,&intent,0)==0&&qq_metadata_album_cover(&metadata,"ALBUM01",input,n)==0&&!metadata.source_cover);
 assert(qq_metadata_tags(&metadata,&tags)==0&&tags.jpeg_bytes==bytes&&!memcmp(tags.jpeg,jpeg,bytes));
 assert(qq_image_jpeg(input,n,jpeg,8,&bytes,&w,&h)<0&&!bytes);
 assert(qq_image_jpeg(input,n-1,jpeg,524288,&bytes,&w,&h)<0&&!bytes);
 assert(write(1,tag,tag_bytes)==(ssize_t)tag_bytes);cleanup();return 0;
}
