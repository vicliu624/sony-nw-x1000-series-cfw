/* PC guest init only: no on-player payload. */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/mount.h>
#include <sys/wait.h>
#include <signal.h>
#include <string.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/sysmacros.h>
#ifdef HB_QEMU_INPUT
#include <dirent.h>
#ifdef HB_QEMU_TASK_TRACE
#include "stock_task_trace.h"
#endif
static int numeric_name(const char *s){if(!*s)return 0;for(;*s;s++)if(*s<'0'||*s>'9')return 0;return 1;}
static void report_tasks(void){
 DIR *procs=opendir("/proc");if(!procs)return;struct dirent *p;
 while((p=readdir(procs)))if(numeric_name(p->d_name)){
  char directory[100];snprintf(directory,sizeof directory,"/proc/%.10s/task",p->d_name);
  DIR *tasks=opendir(directory);if(!tasks)continue;struct dirent *t;
  while((t=readdir(tasks)))if(numeric_name(t->d_name)){
   char path[150],name[64]="?",wait[100]="?";FILE *file;
   snprintf(path,sizeof path,"%s/%.10s/comm",directory,t->d_name);file=fopen(path,"r");if(file){if(!fgets(name,sizeof name,file))strcpy(name,"?");fclose(file);}
   snprintf(path,sizeof path,"%s/%.10s/wchan",directory,t->d_name);file=fopen(path,"r");if(file){if(!fgets(wait,sizeof wait,file))strcpy(wait,"?");fclose(file);}
   name[strcspn(name,"\r\n")]=0;wait[strcspn(wait,"\r\n")]=0;
   printf("GUEST_TASK pid=%s tid=%s name=%s wait=%s\n",p->d_name,t->d_name,name,wait);
  }
  closedir(tasks);
#ifdef HB_QEMU_TASK_TRACE
  if(task_trace_ready)trace_stock_task(atoi(p->d_name));
#endif
 }
 closedir(procs);
}
#endif
#ifndef HB_PROBE_SECONDS
#define HB_PROBE_SECONDS 5
#endif
#ifdef HB_RAM_STATE
extern int init_module(void *,unsigned long,const char *);
extern int __xmknod(int,const char *,unsigned,const unsigned long long *);
extern unsigned long guest_strtoul(const char *,char **,int) __asm__("strtoul");
static int load_module(const char *path,const char *arguments){
 FILE *file=fopen(path,"rb");if(!file)return -1;
 unsigned char *data=malloc(1024*1024);if(!data){fclose(file);return -1;}
 size_t n=fread(data,1,1024*1024,file);fclose(file);int result=init_module(data,n,arguments);free(data);
 printf("GUEST_MODULE %s %d\n",path,result);return result;
}
static int prepare_state(void){
 if(mount("sysfs","/sys","sysfs",0,NULL))return -1;
 if(load_module("/brd.ko",
#ifdef HB_RAM_USER_VOLUME
 "rd_nr=4 rd_size=65536"
#else
 "rd_nr=3 rd_size=8192"
#endif
 )||load_module("/mbcache.ko","")||load_module("/ext2.ko",""))return -1;
#ifdef HB_RAM_USER_VOLUME
#ifdef HB_USER_NLS_BASE
 if(load_module("/nls_base.ko",""))return -1;
#endif
 if(load_module("/nls_cp437.ko","")||load_module("/nls_iso8859-1.ko","")||load_module("/nls_utf8.ko","")||load_module("/fat.ko","")||load_module("/vfat.ko",""))return -1;
#endif
 for(unsigned partition=
#ifdef HB_RAM_USER_VOLUME
 2
#else
 3
#endif
 ;partition<=5;partition++){
 unsigned ram=partition==2?3:partition-3;
 char sysfs[80],path[80];snprintf(sysfs,sizeof sysfs,"/sys/block/ram%u/dev",ram);snprintf(path,sizeof path,"/dev/mtdblock/%u",partition);
 FILE *device=fopen(sysfs,"r");unsigned major=0,minor=0;
 if(!device)return -1;char line[64],*end;
 if(!fgets(line,sizeof line,device)){fclose(device);return -1;}fclose(device);
 major=guest_strtoul(line,&end,10);if(*end++!=':')return -1;minor=guest_strtoul(end,&end,10);if(*end!='\n'&&*end)return -1;
 unsigned long long number=makedev(major,minor);
 if(__xmknod(1,path,S_IFBLK|0600,&number))return -1;
 int input=open(partition==2?"/fixture-user.fat":"/fixture-var.ext2",O_RDONLY),output=open(path,O_WRONLY);if(input<0||output<0)return -1;
 char block[4096];ssize_t got;
 while((got=read(input,block,sizeof block))>0){ssize_t used=0;while(used<got){ssize_t done=write(output,block+used,got-used);if(done<=0)return -1;used+=done;}}
 close(input);close(output);if(got<0)return -1;
 /* Release the initramfs seed after copying; the guest RAM block owns state. */
 if(partition==2&&unlink("/fixture-user.fat"))return -1;
 }
#ifdef HB_RAM_USER_VOLUME
 /* Original sysmgrd owns its normal unmount/mount sequence, not this fixture. */
 puts("GUEST_USER_VOLUME_BLOCK_PREPARED source=/dev/mtdblock/2 fs=vfat volatile=1");
#endif
 puts("GUEST_RAM_STATE_PREPARED");return 0;
}
#endif
int main(void){
 setbuf(stdout,NULL);setbuf(stderr,NULL);
 if(mount("proc","/proc","proc",0,NULL))puts("GUEST_PROC_MOUNT_FAILED");
#ifdef HB_RAM_STATE
 if(prepare_state()){puts("GUEST_RAM_STATE_FAILED");puts("GUEST_MANAGER_PROBE_COMPLETE");for(;;)pause();}
#ifdef HB_QEMU_INPUT
 if(load_module("/evdev.ko","")){puts("GUEST_INPUT_MODULE_FAILED");puts("GUEST_MANAGER_PROBE_COMPLETE");for(;;)pause();}
#endif
#endif
 pid_t child=fork();
 if(child==0){
#ifdef HB_LIVE_MANAGER
 setenv("LD_PRELOAD","/lib/manager-devices.so:/lib/system-devices.so",1);
#else
 setenv("LD_PRELOAD","/lib/manager-devices.so",1);
#endif
#ifdef HB_PLAYER_BOOTSTRAP_FIXTURE
 setenv("X1000_PLAYER_SERVICE","1",1);
#endif
 setenv("PATH","/usr/local/bin:/usr/bin:/bin",1);execl("/usr/local/bin/sysmgrd","sysmgrd","-r","/usr/local/bin/moc_repairer.sh","/etc/AppList.conf",NULL);_exit(127);}
 int status=0;pid_t done=0;
 for(unsigned i=0;
#ifdef HB_GUI_INTERACTIVE
 done==0;
#else
 i<100u*HB_PROBE_SECONDS&&done==0;
#endif
 i++){
#ifdef HB_QEMU_INPUT
#ifdef HB_QEMU_TASK_TRACE
  if(i==1000)task_trace_ready=1;
#endif
  if(i==100||i==1000)report_tasks();
#endif
  if(access("/tmp/manager-home-complete",F_OK)==0)break;done=waitpid(child,&status,WNOHANG);if(done==0)usleep(10000);
 }
 if(done==0){puts(access("/tmp/manager-home-complete",F_OK)==0?"GUEST_MANAGER_STOP_AFTER_COMPLETION":"GUEST_MANAGER_STOP_AFTER_LIMIT");kill(child,SIGTERM);waitpid(child,&status,0);}
 printf("GUEST_MANAGER_WAIT_STATUS %d\n",status);
 FILE *mounts=fopen("/proc/mounts","r");
 if(mounts){char line[512];while(fgets(line,sizeof line,mounts))if(strstr(line,"/dev/mtdblock/"))printf("GUEST_MOUNT %s",line);fclose(mounts);}
 puts("GUEST_MANAGER_PROBE_COMPLETE");for(;;)pause();
}
