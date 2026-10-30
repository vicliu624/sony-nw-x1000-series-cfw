#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#include "../runtime/platform/espnow/xnow_pn_file.h"
#include "../runtime/platform/espnow/xnow_security.h"
#include <assert.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
static unsigned sync_calls,fail_sync;static int denied;
int __real_fsync(int);
int __wrap_fsync(int fd){if(++sync_calls==fail_sync){errno=EIO;return -1;}return __real_fsync(fd);}
static int guard(void *unused){(void)unused;return denied;}
static void name(char path[512],const char *dir,const uint8_t scope[32],const char *suffix){char hex[65];for(unsigned i=0;i<32;i++)sprintf(hex+i*2,"%02x",scope[i]);snprintf(path,512,"%s/pn-%s.%s",dir,hex,suffix);}
int main(int argc,char **argv){
 assert(argc==2);char temp[512];assert(snprintf(temp,sizeof(temp),"%s/pn-XXXXXX",argv[1])>0);char *dir=mkdtemp(temp);assert(dir);
 int fd=open(dir,O_RDONLY|O_DIRECTORY|O_NOFOLLOW);assert(fd>=0);struct stat st;assert(!fstat(fd,&st));struct xnow_pn_file file={fd,st.st_dev,0,guard};
 uint8_t scope[32]={1};uint64_t first=999,last=999;assert(xnow_pn_file_reserve(&file,scope,16,&first,&last)==XNOW_PN_STORAGE&&first==999);
 assert(!xnow_pn_file_provision(&file,scope));assert(xnow_pn_file_provision(&file,scope)==XNOW_PN_STORAGE);
 assert(!xnow_pn_file_reserve(&file,scope,16,&first,&last)&&first==1&&last==16);
 assert(!xnow_pn_file_reserve(&file,scope,16,&first,&last)&&first==17&&last==32);
 int pipefd[2];assert(!pipe(pipefd));pid_t child=fork();assert(child>=0);
 if(!child){close(pipefd[0]);struct xnow_pn_file other=file;other.directory=open(dir,O_RDONLY|O_DIRECTORY);uint64_t range[2];int result=-1;for(unsigned i=0;i<1000&&result;i++){result=xnow_pn_file_reserve(&other,scope,16,&range[0],&range[1]);if(result)usleep(1000);}assert(!result);assert(write(pipefd[1],range,sizeof(range))==sizeof(range));close(other.directory);_exit(0);}
 close(pipefd[1]);uint64_t theirs[2];int result=-1;for(unsigned i=0;i<1000&&result;i++){result=xnow_pn_file_reserve(&file,scope,16,&first,&last);if(result)usleep(1000);}assert(!result);assert(read(pipefd[0],theirs,sizeof(theirs))==sizeof(theirs));int status;assert(waitpid(child,&status,0)==child&&WIFEXITED(status)&&!WEXITSTATUS(status));close(pipefd[0]);assert(last<theirs[0]||theirs[1]<first);
 denied=1;first=999;assert(xnow_pn_file_reserve(&file,scope,16,&first,&last)==XNOW_PN_STORAGE&&first==999);denied=0;
 char path[512];name(path,dir,scope,"dat");int data=open(path,O_WRONLY|O_NOFOLLOW);assert(data>=0&&write(data,"BAD",3)==3&&!close(data));assert(xnow_pn_file_reserve(&file,scope,16,&first,&last)==XNOW_PN_STORAGE);
 scope[0]=2;assert(!xnow_pn_file_provision(&file,scope));sync_calls=0;fail_sync=1;assert(xnow_pn_file_reserve(&file,scope,16,&first,&last)==XNOW_PN_STORAGE);fail_sync=0;
 assert(xnow_pn_file_reserve(&file,scope,16,&first,&last)==XNOW_PN_STORAGE); /* preserves stale temp rather than resetting */
 scope[0]=3;assert(!xnow_pn_file_provision(&file,scope));sync_calls=0;fail_sync=2;assert(xnow_pn_file_reserve(&file,scope,16,&first,&last)==XNOW_PN_UNCERTAIN);fail_sync=0;
 assert(!xnow_pn_file_reserve(&file,scope,16,&first,&last)&&first==17);
 scope[0]=4;name(path,dir,scope,"dat");assert(!symlink("/dev/null",path));assert(xnow_pn_file_reserve(&file,scope,16,&first,&last)==XNOW_PN_STORAGE);
 file.device++;assert(xnow_pn_file_provision(&file,scope)==XNOW_PN_STORAGE);file.device--;
 scope[0]=5;assert(!xnow_pn_file_provision(&file,scope));uint64_t highest=999;
 assert(!xnow_pn_file_load_rx(&file,scope,&highest)&&highest==0);
 assert(!xnow_pn_file_commit_rx(&file,scope,100));assert(!xnow_pn_file_load_rx(&file,scope,&highest)&&highest==100);
 assert(xnow_pn_file_commit_rx(&file,scope,100)==XNOW_PN_REPLAY&&xnow_pn_file_commit_rx(&file,scope,99)==XNOW_PN_REPLAY);
 assert(xnow_pn_file_commit_rx(&file,scope,0)==XNOW_PN_ARGUMENT);
 scope[0]=6;assert(!xnow_pn_file_provision(&file,scope));sync_calls=0;fail_sync=2;
 assert(xnow_pn_file_commit_rx(&file,scope,150)==XNOW_PN_UNCERTAIN);fail_sync=0;
 assert(!xnow_pn_file_load_rx(&file,scope,&highest)&&highest==150);
 assert(xnow_pn_file_commit_rx(&file,scope,150)==XNOW_PN_REPLAY);assert(!xnow_pn_file_commit_rx(&file,scope,151));
 /* Real host journal callbacks connected to security contexts, not RAM state. */
 struct xnow_security_io sio={&file,xnow_pn_file_reserve,xnow_pn_file_load_rx,xnow_pn_file_commit_rx};
 uint8_t ma[6]={2,1,2,3,4,5},mb[6]={2,6,7,8,9,10},key[16]={0},rx_scope[32];struct xnow_pn tx_scope;
 assert(!xnow_pn_init(&tx_scope,ma,key,1024,&file,xnow_pn_file_reserve));assert(!xnow_pn_file_provision(&file,tx_scope.scope));
 assert(!xnow_pn_init(&tx_scope,mb,key,1024,&file,xnow_pn_file_reserve));assert(!xnow_pn_file_provision(&file,tx_scope.scope));
 assert(!xnow_security_rx_scope(rx_scope,ma,mb,key));assert(!xnow_pn_file_provision(&file,rx_scope));
 assert(!xnow_security_rx_scope(rx_scope,mb,ma,key));assert(!xnow_pn_file_provision(&file,rx_scope));
 struct xnow_security a,b,restarted;assert(!xnow_security_init(&a,&sio,ma,mb,key,0,1024)&&!xnow_security_init(&b,&sio,mb,ma,key,0,1024));
 uint8_t frame[1560],payload[10]={1,2,3},decoded[10],random[4]={1,2,3,4};size_t bytes;struct xnow_wire_info info;
 assert(!xnow_security_seal(&a,1,random,payload,10,frame,sizeof(frame),&bytes));assert(!xnow_security_open(&b,frame,bytes,decoded,sizeof(decoded),&info)&&!memcmp(payload,decoded,10));
 assert(!xnow_security_init(&restarted,&sio,mb,ma,key,0,1024));assert(xnow_security_open(&restarted,frame,bytes,decoded,sizeof(decoded),&info)==XNOW_SECURITY_REPLAY);
 assert(!xnow_security_seal(&a,1,random,payload,10,frame,sizeof(frame),&bytes));sync_calls=0;fail_sync=2;memset(decoded,0xa5,sizeof(decoded));
 assert(xnow_security_open(&b,frame,bytes,decoded,sizeof(decoded),&info)==XNOW_SECURITY_STORAGE&&decoded[0]==0xa5&&b.fault);fail_sync=0;
 assert(!xnow_security_init(&restarted,&sio,mb,ma,key,0,1024));assert(xnow_security_open(&restarted,frame,bytes,decoded,sizeof(decoded),&info)==XNOW_SECURITY_REPLAY);
 xnow_security_clear(&a);xnow_security_clear(&b);xnow_security_clear(&restarted);xnow_pn_clear(&tx_scope);
 close(fd);puts("PN file: durable reservation, independent owners, missing/corrupt/symlink refusal, ownership denial and injected fsync failures passed; no power-loss/device claim.");return 0;
}
