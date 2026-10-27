/* Idle initialization/options only. No query/search/gethost call. */
#include <sys/select.h>
#include <arpa/inet.h>
#include <stddef.h>
#include <assert.h>
#include <string.h>
#include <stdio.h>
#include <unistd.h>
#include "ares.h"
extern const char *ares_version(int *);
#ifdef __arm__
typedef char hb_ares_options_64[(sizeof(struct ares_options)==64)?1:-1];
typedef char hb_ares_servers_28[(offsetof(struct ares_options,servers)==28)?1:-1];
#endif
int main(void){
 struct ares_options input;struct {struct ares_options value;unsigned char guard[32];} saved_options;
 struct ares_options *output=&saved_options.value;
 memset(&input,0,sizeof input);memset(&saved_options,0xa5,sizeof saved_options);memset(output,0,sizeof *output);
 struct in_addr server;server.s_addr=htonl(INADDR_LOOPBACK);
 input.flags=ARES_FLAG_NOSEARCH|ARES_FLAG_NOALIASES;input.timeout=250;input.tries=1;
 input.udp_port=htons(54545);input.tcp_port=htons(54545);input.servers=&server;input.nservers=1;input.lookups="b";
 int mask=ARES_OPT_FLAGS|ARES_OPT_TIMEOUTMS|ARES_OPT_TRIES|ARES_OPT_SERVERS|ARES_OPT_UDP_PORT|ARES_OPT_TCP_PORT|ARES_OPT_LOOKUPS;
 ares_channel channel=0;assert(ares_init_options(&channel,&input,mask)==ARES_SUCCESS&&channel);
 int saved=0;assert(ares_save_options(channel,output,&saved)==ARES_SUCCESS);
 for(unsigned i=0;i<32;i++)assert(saved_options.guard[i]==0xa5);
 assert(output->flags==input.flags&&output->tries==1&&output->nservers==1&&output->servers&&output->servers[0].s_addr==server.s_addr);
 assert(output->udp_port==input.udp_port&&output->tcp_port==input.tcp_port&&output->lookups&&!strcmp(output->lookups,"b"));
 int sockets[ARES_GETSOCK_MAXNUM];assert(ares_getsock(channel,sockets,ARES_GETSOCK_MAXNUM)==0);
 ares_process_fd(channel,ARES_SOCKET_BAD,ARES_SOCKET_BAD);ares_cancel(channel);
 int version=0;const char *label=ares_version(&version);assert(label&&!strcmp(label,"1.5.2"));
 char message[256];int n=snprintf(message,sizeof message,"stock c-ares %s options roundtrip passed; saved timeout=%d mask=%u; no query\n",label,output->timeout,(unsigned)saved);
 assert(n>0&&n<(int)sizeof message&&write(1,message,(unsigned)n)==n);
 ares_destroy_options(output);ares_destroy(channel);
 for(unsigned i=0;i<32;i++)assert(saved_options.guard[i]==0xa5);
 return 0;
}
