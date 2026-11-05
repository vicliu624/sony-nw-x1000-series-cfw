/* Generic ARM guest only. /proc/mounts and user volume are explicit RAM fixtures. */
#include <assert.h>
#include <stdio.h>
#include <unistd.h>
#include <sys/wait.h>
extern char **environ;
int main(void){
 int pid=fork();assert(pid>=0);
 if(!pid){char *argv[]={"/contents/HOMEBREW/launcher/app","--native",0};execve("/entry-probe",argv,environ);_exit(127);}
 int status;assert(waitpid(pid,&status,0)==pid&&WIFEXITED(status)&&WEXITSTATUS(status)==0);
 unsigned char data[128],seed[128];
 FILE *file=fopen("/contents/HOMEBREW/data/diagnostics/entry-boundary.bin","rb");assert(file&&fread(data,1,128,file)==128&&fgetc(file)==EOF);fclose(file);
 file=fopen("/seed","rb");assert(file&&fread(seed,1,128,file)==128);fclose(file);
 for(unsigned i=0;i<32;i++)assert(data[i]==seed[i]);
 for(unsigned i=96;i<128;i++)assert(data[i]==seed[i]);
 for(unsigned i=0;i<8;i++){assert(data[32+i]==(unsigned char)"ENTERED1"[i]);assert(data[88+i]==(unsigned char)"COMMIT01"[i]);}
 unsigned recorded=(unsigned)data[40]|(unsigned)data[41]<<8|(unsigned)data[42]<<16|(unsigned)data[43]<<24;
 assert(recorded==(unsigned)pid&&data[44]==1);
 puts("ENTRY_PROBE_SYSTEM_PASS");fflush(stdout);return 0;
}
