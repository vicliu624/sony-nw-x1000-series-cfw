/* Fixed-address read-only firmware identity probe. No arbitrary address or SET. */
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <unistd.h>
#include <sys/socket.h>
#include <linux/wireless.h>
extern int original_ioctl(int,unsigned long,...) __asm__("ioctl");
static void le16(unsigned char *b,unsigned v){b[0]=v;b[1]=v>>8;}
static unsigned rd16(const unsigned char *b){return b[0]|((unsigned)b[1]<<8);}
static void le32(unsigned char *b,uint32_t v){unsigned i;for(i=0;i<4;i++)b[i]=v>>(i*8);}
static int read_word(int fd,uint32_t address,unsigned char out[4]) {
    unsigned char cmd[2048];struct iwreq r;
    memset(cmd,0,sizeof(cmd));le16(cmd,0x86);le16(cmd+2,20);le32(cmd+12,address);
    memset(&r,0,sizeof(r));strcpy(r.ifr_name,"eth0");r.u.data.pointer=cmd;r.u.data.length=20;
    if(original_ioctl(fd,0x8be4,&r)<0){perror("hostcmd GET");return -1;}
    if(r.u.data.length!=20 || rd16(cmd)!=0x8086 || rd16(cmd+2)!=20 || rd16(cmd+6)!=0){puts("Unexpected firmware response");return -1;}
    memcpy(out,cmd+16,4);return 0;
}
int main(int argc,char **argv,char **env){
    FILE *f;char info[2048];size_t n;int fd,rc;unsigned char cmd[2048];struct iwreq r;
    (void)env;
    if(argc!=2 || (strcmp(argv[1],"--read-identity-word") && strcmp(argv[1],"--verify-code") && strcmp(argv[1],"--verify-layout") && strcmp(argv[1],"--gap-survey"))){
        puts("radio-identity 0.1.3\n--read-identity-word: fixed GET of c00065a0.\n--verify-code: read four fixed 64-byte code ranges.\n--verify-layout: fixed pool/init/scatter/callback reads.\n--gap-survey: read fixed c0000e00..c0001000 range; does not prove it is free.\nVerified driver only; no writes.");return argc==2&&!strcmp(argv[1],"--help")?0:64;
    }
    if(sizeof(r)!=32){puts("ABI mismatch");return 70;}
    f=fopen("/proc/net/wlan/info","r");if(!f){perror("driver identity");return 69;}
    n=fread(info,1,sizeof(info)-1,f);rc=ferror(f);fclose(f);info[n]=0;
    if(rc || !strstr(info,"sd8686-9.70.3.p32-26409.p51-(FP4)")){puts("Unqualified driver; refusing command");return 69;}
    fd=socket(AF_INET,SOCK_DGRAM,0);if(fd<0){perror("socket");return 71;}
    if(!strcmp(argv[1],"--verify-layout")){
        static const uint32_t regions[][2]={{0x163ec,16},{0x17328,8},{0x17338,8},{0xc00026b0,4},{0xc000d5a8,4}};
        unsigned i,j;unsigned char word[4];
        for(i=0;i<5;i++)for(j=0;j<regions[i][1];j+=4){
            uint32_t address=regions[i][0]+j;
            if(read_word(fd,address,word)){close(fd);return 71;}
            printf("LAYOUT %08x %02x%02x%02x%02x\n",address,word[0],word[1],word[2],word[3]);
        }
        close(fd);return 0;
    }
    if(!strcmp(argv[1],"--gap-survey")) {
        unsigned j;unsigned char word[4];
        for(j=0;j<512;j+=4){
            uint32_t address=0xc0000e00+j;
            if(read_word(fd,address,word)){close(fd);return 71;}
            printf("GAP %08x %02x%02x%02x%02x\n",address,word[0],word[1],word[2],word[3]);
        }
        close(fd);return 0;
    }
    if(!strcmp(argv[1],"--verify-code")) {
        static const uint32_t regions[]={0x8078,0x88d4,0xa314,0x136b0};
        unsigned i,j;unsigned char word[4];
        for(i=0;i<4;i++)for(j=0;j<64;j+=4){
            uint32_t address=regions[i]+j;
            if(read_word(fd,address,word)){close(fd);return 71;}
            printf("CODE %08x %02x%02x%02x%02x\n",address,word[0],word[1],word[2],word[3]);
        }
        close(fd);return 0;
    }
    memset(cmd,0,sizeof(cmd));le16(cmd,0x86);le16(cmd+2,20);
    /* Header8; action=GET0/reserved0; address; response word. */
    le16(cmd+8,0);le32(cmd+12,0xc00065a0);
    memset(&r,0,sizeof(r));strcpy(r.ifr_name,"eth0");r.u.data.pointer=cmd;r.u.data.length=20;
    rc=original_ioctl(fd,0x8be4,&r);close(fd);
    if(rc<0){perror("hostcmd GET");return 71;}
    if(r.u.data.length!=20 || rd16(cmd)!=0x8086 || rd16(cmd+2)!=20 || rd16(cmd+6)!=0){puts("Unexpected firmware response");return 76;}
    printf("identity_word=%02x%02x%02x%02x expected=2449643a\n",cmd[16],cmd[17],cmd[18],cmd[19]);
    return memcmp(cmd+16,"$Id:",4)?65:0;
}
