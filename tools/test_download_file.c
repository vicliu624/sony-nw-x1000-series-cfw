#define _XOPEN_SOURCE 700
#include "../runtime/store/download_file.h"
#include "../runtime/store/http_response.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
static const unsigned char digest[32]={0xba,0x78,0x16,0xbf,0x8f,0x01,0xcf,0xea,0x41,0x41,0x40,0xde,0x5d,0xae,0x22,0x23,0xb0,0x03,0x61,0xa3,0x96,0x17,0x7a,0x9c,0xb4,0x10,0xff,0x61,0xf2,0x00,0x15,0xad};
extern void hb_download_test_fault(int,int);
int main(int argc,char **argv){
 assert(argc==3);const char *mode=argv[2];struct hb_download_file file;volatile int stop=0;
 hb_download_file_init(&file);
 const char *key=!strcmp(mode,"bad-key")?"../escape":"demo";
 int result=hb_download_file_begin(&file,argv[1],key,3,digest,!strcmp(mode,"space")?(1ULL<<60):4096,&stop);
 if(!strcmp(mode,"exists")||!strcmp(mode,"link")){assert(result==HB_FETCH_EXISTS);assert(!hb_download_file_discard(&file));return 0;}
 if(!strcmp(mode,"space")){assert(result==HB_FETCH_SPACE);return 0;}
 if(!strcmp(mode,"bad-key")||!strcmp(mode,"root-alias")){assert(result==HB_FETCH_IO);return 0;}
 assert(!result);
 if(!strcmp(mode,"write-error"))hb_download_test_fault(1,1);
 if(!strcmp(mode,"write-after-error"))hb_download_test_fault(2,1);
 if(!strcmp(mode,"short-write"))hb_download_test_fault(3,1);
 if(!strcmp(mode,"sync-file")||!strcmp(mode,"recheck-file-sync")||!strcmp(mode,"recheck-corrupt"))hb_download_test_fault(4,1);
 if(!strcmp(mode,"sync-dir")||!strcmp(mode,"recheck-dir-sync"))hb_download_test_fault(4,2);
 if(!strcmp(mode,"close-error")||!strcmp(mode,"recheck-close"))hb_download_test_fault(5,1);
 if(!strcmp(mode,"cancel")){
  stop=1;assert(hb_download_stream_push(&file.body,(const unsigned char *)"abc",3)==HB_DOWNLOAD_CANCELLED);
  assert(hb_download_file_discard(&file)==HB_DOWNLOAD_CANCELLED&&file.fd==-1);
  stop=0;assert(!hb_download_file_discard(&file));return 0;
 }
 struct hb_http_response response;assert(!hb_http_response_init(&response,&file.body));
 const char *text=!strcmp(mode,"hash")?"HTTP/1.1 200 OK\r\nContent-Length: 3\r\n\r\nabd":"HTTP/1.1 200 OK\r\nContent-Length: 3\r\n\r\nabc";
 result=hb_http_response_push(&response,(const unsigned char *)text,(unsigned)strlen(text));
 if(!strcmp(mode,"write-error")||!strcmp(mode,"write-after-error")){
  assert(result==HB_DOWNLOAD_IO&&file.state!=HB_FETCH_READY);assert(!hb_download_file_discard(&file));return 0;
 }
 assert(!result);
 result=hb_http_response_finish(&response);
 if(!strcmp(mode,"hash")){assert(result==HB_DOWNLOAD_HASH&&hb_download_file_finish(&file)==HB_DOWNLOAD_HASH);assert(!hb_download_file_discard(&file));return 0;}
 assert(!result);
 if(!strcmp(mode,"sync-file")||!strcmp(mode,"sync-dir")||!strcmp(mode,"close-error")||!strncmp(mode,"recheck-",8)){
  assert(hb_download_file_finish(&file)==HB_FETCH_RETAINED&&file.state==HB_FETCH_REVIEW&&file.fd==-1);
  assert(hb_download_file_discard(&file)==HB_FETCH_RETAINED);
  if(!strncmp(mode,"recheck-",8)){
   hb_download_test_fault(0,0);
   if(!strcmp(mode,"recheck-corrupt")){int fd=open(file.path,O_WRONLY|O_TRUNC);assert(fd>=0&&write(fd,"abd",3)==3&&!close(fd));}
   result=hb_download_file_recheck(&file);
   if(!strcmp(mode,"recheck-corrupt"))assert(result==HB_FETCH_RETAINED&&file.state==HB_FETCH_REVIEW);
   else assert(!result&&file.state==HB_FETCH_READY);
  }
  return 0;
 }
 if(!strcmp(mode,"replace")){
  char saved[520];assert(snprintf(saved,sizeof saved,"%s-saved",file.path)<(int)sizeof saved);assert(!rename(file.path,saved));
  int fd=open(file.path,O_WRONLY|O_CREAT|O_EXCL,0600);assert(fd>=0&&write(fd,"KEEP",4)==4&&!close(fd));
  assert(hb_download_file_finish(&file)==HB_FETCH_RETAINED&&hb_download_file_discard(&file)==HB_FETCH_RETAINED);
  assert(hb_download_file_recheck(&file)==HB_FETCH_RETAINED);return 0;
 }
 assert(!hb_download_file_finish(&file)&&file.state==HB_FETCH_READY&&file.fd==-1);
 if(!strcmp(mode,"discard"))assert(!hb_download_file_discard(&file)&&file.state==HB_FETCH_EMPTY&&!file.identity_known);
 return 0;
}
