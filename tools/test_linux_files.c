#include "../runtime/native/linux_files.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static unsigned char data[2048];
static unsigned size,reads,closes;
static int oversize;
static volatile int stop;
static void reset(void){size=reads=closes=0;oversize=0;stop=0;}
static void entry(const char *name){
 unsigned length=(unsigned)strlen(name),record=(10+length+1+3)&~3u;
 memset(data+size,0,record);data[size+8]=(unsigned char)record;data[size+9]=(unsigned char)(record>>8);
 memcpy(data+size+10,name,length);size+=record;
}
long x1000_oabi_call(long n,long a,long b,long c,long d,long e,long f){
 (void)d;(void)e;(void)f;
 if(n==5){assert(!strcmp((const char*)a,"apps"));return 42;}
 if(n==6){assert(a==42);closes++;return 0;}
 assert(n==141&&a==42&&c==2048);reads++;
 if(oversize)return 2049;
 if(reads>1)return 0;
 memcpy((void*)b,data,size);return size;
}
int main(void){
 struct hb_directory directory;char name[33];
 reset();entry(".");entry("abcdefghijklmnopqrstuvwxyz1234567");entry("store");
 assert(!hb_directory_open(&directory,"apps",&stop));
 assert(hb_directory_next(&directory,name)==1&&!strcmp(name,"."));
 assert(hb_directory_next(&directory,name)==1&&!strcmp(name,"store"));
 assert(!hb_directory_next(&directory,name));hb_directory_close(&directory);assert(closes==1);
 reset();entry("abcdefghijklmnopqrstuvwxyz123456");assert(!hb_directory_open(&directory,"apps",&stop));
 assert(hb_directory_next(&directory,name)==1&&strlen(name)==32);hb_directory_close(&directory);
 reset();size=4;assert(!hb_directory_open(&directory,"apps",&stop));assert(hb_directory_next(&directory,name)==-1);hb_directory_close(&directory);
 reset();entry("store");data[8]=11;assert(!hb_directory_open(&directory,"apps",&stop));assert(hb_directory_next(&directory,name)==-1);hb_directory_close(&directory);
 reset();assert(!hb_directory_open(&directory,"apps",&stop));stop=1;assert(hb_directory_next(&directory,name)==-1&&!reads);hb_directory_close(&directory);
 reset();oversize=1;assert(!hb_directory_open(&directory,"apps",&stop));assert(hb_directory_next(&directory,name)==-1);hb_directory_close(&directory);
 puts("Linux directory iterator bounds, long names and cancellation passed");return 0;
}
