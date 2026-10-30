/* Real local pipe/socket/process semantics, original-action effects mocked. */
#define main full_control_checks
#include "test_xnow_full_control.c"
#undef main
#include "../runtime/platform/espnow/xnow_owner_gate.h"
#include <sys/stat.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <errno.h>
#include <sys/wait.h>
#include <fcntl.h>
#include <unistd.h>
#include "../runtime/store/target_abi.h"
extern int test_gate_fcntl(int,int,...) __asm__("fcntl");
static int denied_storage;
static int storage_permission(void *unused){(void)unused;return denied_storage;}
static void release_ready(struct xnow_full_control *c){xnow_full_control_stop(c);pump(c,XNOW_SESSION_DONE);assert(xnow_full_control_finished(c));}
static int replace_fd(int fd){assert(!close(fd));int other=open("/dev/null",O_RDONLY);assert(other>=0);if(other!=fd){assert(dup2(other,fd)==fd);close(other);}return fd;}
int main(void){
 assert(full_control_checks()==0);struct xnow_full_control controller;setup(&controller,1);pump(&controller,XNOW_SESSION_READY);
 struct xnow_owner_gate gate,second;int pipefd[2];volatile int stop_token=0;assert(!pipe(pipefd));
 assert(xnow_owner_gate_open(&second,pipefd[1],&stop_token,0,storage_permission)==XNOW_IDENTITY);
 assert(!xnow_owner_gate_open(&gate,pipefd[0],&stop_token,0,storage_permission));
 controller.options.context=&gate;controller.options.lease_valid=xnow_owner_gate_radio_valid;
 int old_owner=socket(AF_UNIX,SOCK_DGRAM,0);assert(old_owner>=0);struct sockaddr_un address;memset(&address,0,sizeof(address));address.sun_family=AF_UNIX;const char *legacy_name=XNOW_OWNER_GATE_NAMESPACE;memcpy(address.sun_path+1,legacy_name,strlen(legacy_name));
 assert(bind(old_owner,(struct sockaddr *)&address,(socklen_t)(sizeof(address.sun_family)+1+strlen(legacy_name)))<0&&errno==EADDRINUSE);close(old_owner);
 assert(test_gate_fcntl(gate.command_fd,F_GETFD)&FD_CLOEXEC);assert(test_gate_fcntl(gate.socket_fd,F_GETFD)&FD_CLOEXEC);
 assert(xnow_owner_gate_open(&second,pipefd[0],&stop_token,0,storage_permission)==XNOW_IDENTITY);
 assert(xnow_owner_gate_radio_valid(&gate)&&!xnow_owner_gate_storage_guard(&gate)&&!xnow_owner_gate_stop_requested(&gate));
 pid_t child=fork();assert(child>=0);if(!child){assert(!xnow_owner_gate_radio_valid(&gate));assert(xnow_owner_gate_release(&gate,&controller)==XNOW_UNCERTAIN);_exit(0);}int status;assert(waitpid(child,&status,0)==child&&WIFEXITED(status)&&!WEXITSTATUS(status));assert(xnow_owner_gate_radio_valid(&gate));
 assert(write(pipefd[1],"queued",6)==6&&!close(pipefd[1]));assert(xnow_owner_gate_stop_requested(&gate)&&xnow_owner_gate_storage_guard(&gate)<0&&xnow_owner_gate_radio_valid(&gate));
 stop_pending=1;assert(xnow_owner_gate_step(&gate,&controller)==XNOW_SESSION_READY&&controller.stop_requested&&controller.endpoint.stopping&&!xnow_full_control_endpoint(&controller));
 assert(xnow_owner_gate_release(&gate,&controller)==XNOW_UNCERTAIN&&xnow_owner_gate_radio_valid(&gate));stop_pending=0;
 release_ready(&controller);assert(!xnow_owner_gate_release(&gate,&controller));close(pipefd[0]);
 assert(!pipe(pipefd));assert(!xnow_owner_gate_open(&gate,pipefd[0],&stop_token,0,storage_permission));denied_storage=1;assert(xnow_owner_gate_storage_guard(&gate)<0&&xnow_owner_gate_radio_valid(&gate));denied_storage=0;assert(xnow_owner_gate_storage_guard(&gate)<0&&xnow_owner_gate_stop_requested(&gate));assert(!xnow_owner_gate_release(&gate,&controller));close(pipefd[0]);close(pipefd[1]);
 assert(!pipe(pipefd));assert(!xnow_owner_gate_open(&gate,pipefd[0],&stop_token,0,storage_permission));stop_token=1;assert(xnow_owner_gate_stop_requested(&gate)&&xnow_owner_gate_storage_guard(&gate)<0&&xnow_owner_gate_radio_valid(&gate));stop_token=0;assert(xnow_owner_gate_storage_guard(&gate)<0);assert(!xnow_owner_gate_release(&gate,&controller));close(pipefd[0]);close(pipefd[1]);
 assert(!pipe(pipefd));assert(!xnow_owner_gate_open(&gate,pipefd[0],&stop_token,0,storage_permission));int replacement=replace_fd(gate.command_fd);assert(xnow_owner_gate_stop_requested(&gate)&&xnow_owner_gate_radio_valid(&gate));assert(xnow_owner_gate_release(&gate,&controller)==XNOW_UNCERTAIN&&test_gate_fcntl(replacement,F_GETFD)>=0);close(replacement);close(pipefd[0]);close(pipefd[1]);
 assert(!pipe(pipefd));assert(!xnow_owner_gate_open(&gate,pipefd[0],&stop_token,0,storage_permission));replacement=replace_fd(gate.socket_fd);assert(!xnow_owner_gate_radio_valid(&gate));assert(xnow_owner_gate_storage_guard(&gate)<0);assert(xnow_owner_gate_release(&gate,&controller)==XNOW_UNCERTAIN&&test_gate_fcntl(replacement,F_GETFD)>=0);close(replacement);close(pipefd[0]);close(pipefd[1]);
 puts("Owner gate: actual abstract exclusion, pipe-HUP including queued bytes, stop/storage revocation retaining radio lease, fork refusal, fd reuse and release-after-restore checks passed; USB grant remains external.");return 0;
}
