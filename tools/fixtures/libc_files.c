#include <assert.h>
#include <errno.h>
#include <string.h>
#include "../../runtime/native/linux_files.h"
extern long long stock_llseek(int,long long,int) __asm__("llseek");
int main(int argc,char **argv){
 assert(argc==4);volatile int stop=0;struct hb_directory d;int short_seen=0,exact_seen=0,total=0;char name[33];
 assert(!hb_directory_open(&d,argv[1],&stop));
 int result;while((result=hb_directory_next(&d,name))>0){total++;assert(strlen(name)<=32);if(!strcmp(name,"payload"))short_seen++;if(strlen(name)==32)exact_seen++;assert(total<10);}
 assert(result==0&&short_seen==1&&exact_seen==1);hb_directory_close(&d);hb_directory_close(&d);
 long fd=hb_file_open_read(argv[2]);assert(fd>=0);char data[5];assert(hb_file_read(fd,data,5)==5&&!memcmp(data,"HELLO",5));
 assert(stock_llseek(fd,0x200000011LL,0)==0x200000011LL); /* no file write/allocation */
 assert(hb_file_seek_end(fd)==5);assert(hb_file_close(fd)==0);
 assert(hb_file_seek_end(-1)==-EBADF);
 stop=1;assert(hb_directory_open(&d,argv[1],&stop)<0);hb_directory_close(&d);
 stop=0;assert(!hb_directory_open(&d,argv[1],&stop));stop=1;assert(hb_directory_next(&d,name)<0);hb_directory_close(&d);
 stop=0;assert(hb_directory_open(&d,argv[3],&stop)<0);hb_directory_close(&d);
 return 0;
}
