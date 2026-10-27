/* Library ABI probe on an ordinary file and anonymous pipe, never a player. */
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
/* Only the non-time framebuffer query is probed. Stock ioctl is a direct
 * three-register OABI wrapper (verified separately); no time64 aliasing. */
extern int hb_stock_ioctl(int,unsigned long,void *) __asm__("ioctl");
#include <sys/mman.h>
#include <unistd.h>
int main(int argc,char **argv) {
 assert(argc==2);int fd=open(argv[1],O_RDONLY);assert(fd>=0);
 unsigned values[40]={0};errno=0;
 assert(hb_stock_ioctl(fd,0x4600,values)==-1&&errno==ENOTTY);
 void *mapped=mmap(0,4096,PROT_READ,MAP_PRIVATE,fd,0);assert(mapped!=MAP_FAILED);
 assert(((unsigned char*)mapped)[0]==0x7f&&((unsigned char*)mapped)[1]=='E');
 assert(munmap(mapped,4096)==0&&close(fd)==0);
 int pipefd[2];assert(pipe(pipefd)==0);
 struct pollfd p={pipefd[0],POLLIN,0};assert(poll(&p,1,0)==0);
 assert(write(pipefd[1],"X",1)==1);assert(poll(&p,1,0)==1&&(p.revents&POLLIN));
 char value;assert(read(pipefd[0],&value,1)==1&&value=='X');
 assert(close(pipefd[0])==0&&close(pipefd[1])==0);
 return 0;
}

