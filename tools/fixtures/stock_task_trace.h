/* PC guest-only, opt-in register/return-address observation. No register writes,
 * internal breakpoints or application data are emitted. Trace pauses scheduling
 * briefly and cannot qualify native timing or a complete boot.
 */
#include <errno.h>
extern long guest_ptrace(int,int,void *,void *) __asm__("ptrace");
static int task_trace_ready;
static void trace_stock_task(int pid){
 static int maps_printed;
 char path[80],line[512];snprintf(path,sizeof path,"/proc/%d/stat",pid);
 FILE *file=fopen(path,"r");if(!file)return;
 char *got=fgets(line,sizeof line,file);fclose(file);
 if(!got||!strstr(line,"(SpiderApp)"))return;
 if(!maps_printed){
  snprintf(path,sizeof path,"/proc/%d/maps",pid);file=fopen(path,"r");
  if(file){while(fgets(line,sizeof line,file))if(strstr(line,"r-xp"))printf("GUEST_ELF_MAP %s",line);fclose(file);maps_printed=1;}
 }
 if(guest_ptrace(16,pid,0,0)){
  unsigned inherited[18];int failure=errno;
  if(!guest_ptrace(12,pid,0,inherited)){
   printf("GUEST_TASK_TRACE_INHERITED_STOP pid=%d\n",pid);guest_ptrace(17,pid,0,0);
  }else printf("GUEST_TASK_TRACE_REFUSED pid=%d errno=%d\n",pid,failure);
  return;
 }
 int status=0;unsigned regs[18];
 if(waitpid(pid,&status,0)==pid&&WIFSTOPPED(status)&&!guest_ptrace(12,pid,0,regs)){
  printf("GUEST_TASK_REGS pid=%d pc=%08x lr=%08x sp=%08x cpsr=%08x\n",pid,regs[15],regs[14],regs[13],regs[16]);
  printf("GUEST_TASK_RETURN_CANDIDATES pid=%d",pid);
  for(unsigned i=0;i<96;i++){
   errno=0;unsigned value=(unsigned)guest_ptrace(2,pid,(void *)(unsigned long)(regs[13]+i*4),0);
   if(errno)break;
   if(!(value&3)&&((value>=0x8000&&value<0x4d6000)||(value>=0x40000000&&value<0x42000000)))printf(" %08x",value);
  }
  puts("");
  static const unsigned controls[]={0x613e60,0x613e64,0x613e68,0x613eac,0x66efe8,0x6833dc,0x820f6c};
  printf("GUEST_TASK_NATIVE_CONTROLS pid=%d",pid);
  for(unsigned i=0;i<sizeof controls/sizeof controls[0];i++){
   errno=0;unsigned v=(unsigned)guest_ptrace(2,pid,(void *)(unsigned long)controls[i],0);
   if(!errno)printf(" %08x=%08x",controls[i],v);
  }
  puts("");
 }
 if(guest_ptrace(17,pid,0,0))printf("GUEST_TASK_TRACE_DETACH_ERROR pid=%d errno=%d\n",pid,errno);
}
