#define _DEFAULT_SOURCE
#include "../../runtime/platform/espnow/xnow_pn_file.h"
#include <assert.h>
#include <dirent.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#include <errno.h>
static int guard(void *p){return p?0:-1;}
int main(int argc,char **argv){
 assert(argc==2);int fd=open(argv[1],O_RDONLY|O_DIRECTORY|O_NOFOLLOW);assert(fd>=0);
 struct stat st;assert(!fstat(fd,&st));struct xnow_pn_file file={fd,st.st_dev,&fd,guard};
 DIR *dir=opendir(argv[1]);assert(dir);struct dirent *entry;unsigned count=0;uint8_t scopes[2][32];
 while((entry=readdir(dir))){
  if(strlen(entry->d_name)!=71||strncmp(entry->d_name,"pn-",3)||strcmp(entry->d_name+67,".dat"))continue;
  assert(count<2);for(unsigned i=0;i<32;i++){unsigned value;assert(sscanf(entry->d_name+3+2*i,"%2x",&value)==1);scopes[count][i]=(uint8_t)value;}count++;
 }
 assert(count==2&&!closedir(dir));
 for(unsigned index=0;index<count;index++){
  const uint8_t *scope=scopes[index];
  uint64_t high=99,first=0,last=0;
  int loaded=xnow_pn_file_load_rx(&file,scope,&high);
  if(loaded||high)fprintf(stderr,"counter read rc=%d high=%llu errno=%d count=%u\n",loaded,(unsigned long long)high,errno,count);
  assert(!loaded&&high==0);
  assert(!xnow_pn_file_reserve(&file,scope,1024,&first,&last)&&first==1&&last==1024);
  assert(xnow_pn_file_provision(&file,scope)!=0);
  assert(!xnow_pn_file_load_rx(&file,scope,&high)&&high==1024);
 }
 assert(!close(fd));puts("REMOTE_PN_PROPOSAL_C_READER_AND_NO_RESET_PASS");return 0;
}
