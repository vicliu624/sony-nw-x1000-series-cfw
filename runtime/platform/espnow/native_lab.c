/* Terminal-operated native application. stdout only; installation is separate. */
#include "xnow_sd8686.h"
#include "xnow_frame.h"
#include <stdio.h>
#include <string.h>
#include <poll.h>
#include <fcntl.h>
#include <unistd.h>
int main(int argc,char **argv,char **env) {
    struct xnow_sd8686 radio={-1,0};struct xnow_mailbox link;
    struct xnow_received received;struct xnow_view view;
    uint8_t packet[32];uint32_t token=0;size_t n;int result,ping,i;
    (void)env;
    if(argc==2 && !strcmp(argv[1],"--version")){puts("XNOW Lab 0.1.0-dev.4");return 0;}
    if(argc!=2 || (!strcmp(argv[1],"--help"))) {
        puts("XNOW Lab: --probe | --pool-info | --stock-verify | --channel | --listen | --ping | --version\n"
             "No installation or filesystem writes. --ping requires verified radio bridge and active polling peer.");
        return argc==1 || (argc==2&&!strcmp(argv[1],"--help"))?0:64;
    }
    if(!strcmp(argv[1],"--stock-verify")) {
        result=xnow_sd8686_stock_verify();
        printf("stock_fingerprint_result=%d; stable276-byte code/layout check, no SET\n",result);
        return result?69:0;
    }
    if(!strcmp(argv[1],"--channel")) {
        unsigned channel;
        if(xnow_sd8686_channel_get(&channel)){puts("Channel GET unavailable; no SET issued");return 69;}
        printf("radio_channel=%u (read-only GET)\n",channel);return 0;
    }
    if(!strcmp(argv[1],"--pool-info")) {
        uint32_t stride,count,free_blocks;
        if(xnow_sd8686_pool_info(&stride,&count,&free_blocks)){puts("Pool query failed");return 69;}
        printf("pool_stride=%u blocks=%u free=%u\n",stride,count,free_blocks);return 0;
    }
    ping=!strcmp(argv[1],"--ping");
    if(!ping && strcmp(argv[1],"--probe") && strcmp(argv[1],"--listen"))return 64;
    result=xnow_sd8686_open(&radio,&link);
    if(result){printf("Bridge unavailable or unqualified (%d); no SET commands issued\n",result);return 69;}
    if(!strcmp(argv[1],"--probe")){puts("Verified bridge present; no SET commands issued");xnow_sd8686_close(&radio);return 0;}
    if(ping) {
        int random_fd=open("/dev/urandom",O_RDONLY);ssize_t bytes=-1;
        if(random_fd>=0){bytes=read(random_fd,&token,4);close(random_fd);}
        if(bytes!=4){xnow_sd8686_close(&radio);return 71;}
        if(xnow_encode(packet,32,XNOW_PING,1,token,"X1060 LINK TEST",16,&n))return 70;
        result=xnow_mailbox_send(&link,packet);
        if(result){printf("Publish result=%d\n",result);xnow_sd8686_close(&radio);return 75;}
        printf("PUBLISHED seq=1 token=%08x; waiting for peer PONG\n",token);fflush(stdout);
    }
    for(i=0;i<200;i++) {
        result=xnow_mailbox_receive(&link,&received);
        if(result==XNOW_OK) {
            if(!xnow_decode(received.packet,32,&view)) {
                printf("RX kind=%u seq=%u token=%08x missed=%u\n",view.kind,view.sequence,view.token,received.missed);fflush(stdout);
                if(ping && view.kind==XNOW_PONG && view.sequence==1 && view.token==token){puts("MATCHED PEER PONG");xnow_sd8686_close(&radio);return 0;}
            }
        } else if(result<0){printf("Receive failed=%d\n",result);break;}
        poll(0,0,25);
    }
    xnow_sd8686_close(&radio);puts("No matched peer ACK; a published request can remain pending until peer polls");return 75;
}
