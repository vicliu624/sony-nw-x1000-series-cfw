/* Native Linux adapter. Firmware word commands only; no persistent writes.
 * SET is restricted to the verified bridge's TX words/request field.
 */
#include "xnow_sd8686.h"
#include "xnow_frame.h"
#include "xnow_channel.h"
#include "../../native/sha256.h"
#include "xnow_radio_build.h"
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <linux/wireless.h>
extern int xnow_original_ioctl(int,unsigned long,...) __asm__("ioctl");
static void put16(unsigned char *p,unsigned value){p[0]=value;p[1]=value>>8;}
static unsigned get16(const unsigned char *p){return p[0]|((unsigned)p[1]<<8);}
int xnow_sd8686_modules_absent(void) {
    static const char *names[]={"sd8xxx","mp200_sdio","wlan_pm_register","wlan_pwr_ctrl"};
    FILE *file=fopen("/proc/modules","r");char line[1024];unsigned bytes=0;int result=0;
    if(!file)return XNOW_IO;
    while(fgets(line,sizeof(line),file)) {
        size_t length=strlen(line),name=strcspn(line," \t\n");
        if(!length||line[length-1]!='\n'||!name||name>63||length>65536-bytes){result=XNOW_IO;break;}
        bytes+=(unsigned)length;
        for(unsigned i=0;i<4;i++)if(strlen(names[i])==name&&!memcmp(line,names[i],name))result=XNOW_PENDING;
    }
    if(ferror(file))result=XNOW_IO;
    if(fclose(file))result=XNOW_IO;
    return result;
}
static int driver_socket(void) {
    FILE *f;char info[2048];size_t n;int failed;
    if(sizeof(struct iwreq)!=32)return -1;
    f=fopen("/proc/net/wlan/info","r");if(!f)return -1;
    n=fread(info,1,sizeof(info)-1,f);failed=ferror(f);fclose(f);info[n]=0;
    if(failed || !strstr(info,"sd8686-9.70.3.p32-26409.p51-(FP4)"))return -1;
    return socket(AF_INET,SOCK_DGRAM,0);
}
static int word(int fd,uint32_t address,int set,uint32_t *value) {
    unsigned char command[2048];struct iwreq request;
    if((address&3) || !value)return -1;
    /* This internal function is reached only by the fixed metadata/code/state
     * readers and the bounded verified mailbox writer below. */
    memset(command,0,sizeof(command));put16(command,0x86);put16(command+2,20);
    put16(command+8,(unsigned)set);xnow_put32(command+12,address);
    if(set)xnow_put32(command+16,*value);
    memset(&request,0,sizeof(request));strcpy(request.ifr_name,"eth0");
    request.u.data.pointer=command;request.u.data.length=20;
    if(xnow_original_ioctl(fd,0x8be4,&request)<0 || request.u.data.length!=20 ||
       get16(command)!=0x8086 || get16(command+2)!=20 || get16(command+6))return -1;
    *value=xnow_le32(command+16);return 0;
}
int xnow_sd8686_stock_verify(void) {
    /* Scatter inputs17320..17340 are reclaimed by original11e0/11f4 after use;
     * they are deliberately excluded from this runtime identity check. */
    static const uint32_t ranges[][2]={{0x8078,64},{0x88d4,64},{0xa314,64},{0x136b0,64},
        {0x163ec,16},{0xc00026b0,4}};
    static const unsigned char expected[32]={0xea,0x35,0x48,0xde,0xf0,0x31,0xc6,0x7f,
        0xed,0xe1,0xff,0x19,0x7f,0xd2,0xde,0xf4,0xf7,0x1b,0x1b,0x6b,0x99,0x32,0xc3,0x71,
        0x2c,0x54,0xb5,0x8e,0xe1,0xfa,0x55,0x80};
    struct hb_sha256 hash;unsigned char bytes[4],digest[32];uint32_t value;
    int fd=driver_socket(),result=XNOW_IDENTITY;if(fd<0)return result;
    if(word(fd,0xc000d5a8,0,&value)){result=XNOW_IO;goto done;}
    if(value!=0x0004076c)goto done;
    hb_sha256_init(&hash);
    for(unsigned range=0;range<6;range++)for(unsigned offset=0;offset<ranges[range][1];offset+=4){
        if(word(fd,ranges[range][0]+offset,0,&value)){result=XNOW_IO;goto done;}
        xnow_put32(bytes,value);hb_sha256_update(&hash,bytes,4);
    }
    hb_sha256_final(&hash,digest);if(!memcmp(digest,expected,32))result=XNOW_OK;
done:close(fd);return result;
}
static int deep_sleep_request(int fd,unsigned char action,int *sleeping) {
    unsigned char data[128];struct iwreq request;
    memset(data,0,sizeof(data));data[0]=action;
    memset(&request,0,sizeof(request));strcpy(request.ifr_name,"eth0");
    request.u.data.pointer=data;request.u.data.length=sizeof(data);
    if(xnow_original_ioctl(fd,0x8bfb,&request)<0||request.u.data.length>sizeof(data))return XNOW_IO;
    if(action=='2') {
        /* Original strings include one trailing space, copied without NUL. */
        if(request.u.data.length==4&&!memcmp(data,"off ",4))*sleeping=0;
        else if(request.u.data.length==3&&!memcmp(data,"on ",3))*sleeping=1;
        else return XNOW_IO;
    }
    return XNOW_OK;
}
int xnow_sd8686_wake(const struct xnow_session *session) {
    int fd,sleeping=1,result;
    if(!session||!session->lease||!((session->phase==XNOW_SESSION_STARTING&&session->pending==XNOW_SESSION_WAKE)||
       (session->phase==XNOW_SESSION_STOPPING&&session->pending==XNOW_SESSION_RESTORE_WAKE)))return XNOW_IDENTITY;
    fd=driver_socket();if(fd<0)return XNOW_IDENTITY;
    result=deep_sleep_request(fd,'0',0);
    if(!result)result=deep_sleep_request(fd,'2',&sleeping);
    close(fd);
    return result||sleeping?XNOW_UNCERTAIN:XNOW_OK;
}
static int channel_command(int fd,unsigned set,unsigned target,unsigned *observed) {
    unsigned char command[2048];struct iwreq request;
    memset(command,0,sizeof(command));
    if(xnow_channel_command(command,set,target))return XNOW_ARGUMENT;
    memset(&request,0,sizeof(request));strcpy(request.ifr_name,"eth0");
    request.u.data.pointer=command;request.u.data.length=XNOW_CHANNEL_BYTES;
    if(xnow_original_ioctl(fd,0x8be4,&request)<0||request.u.data.length!=XNOW_CHANNEL_BYTES||
       xnow_channel_response(command,XNOW_CHANNEL_BYTES,set,observed))return set?XNOW_UNCERTAIN:XNOW_IO;
    return XNOW_OK;
}
int xnow_sd8686_channel_get(unsigned *channel) {
    int fd,result;if(!channel)return XNOW_ARGUMENT;
    fd=driver_socket();if(fd<0)return XNOW_IDENTITY;
    result=channel_command(fd,0,0,channel);close(fd);return result;
}
int xnow_sd8686_channel_set(struct xnow_sd8686 *radio,const struct xnow_session *session,unsigned channel) {
    uint32_t pool,magic;unsigned observed;int result;
    if(channel<1||channel>13)return XNOW_ARGUMENT;
    if(!radio||!radio->verified||radio->fd<0||!session||!session->lease||
       session->phase!=XNOW_SESSION_STARTING||session->pending!=XNOW_SESSION_CONFIGURE)return XNOW_IDENTITY;
    if(word(radio->fd,0xc000d5a8,0,&pool)||pool!=0x0003076c||
       word(radio->fd,XNOW_RADIO_STATE_BASE,0,&magic)||magic!=XNOW_MAILBOX_MAGIC)return XNOW_IDENTITY;
    result=channel_command(radio->fd,1,channel,&observed);if(result)return result;
    if(observed!=channel||channel_command(radio->fd,0,0,&observed)||observed!=channel)return XNOW_UNCERTAIN;
    return XNOW_OK;
}
static int read_mailbox(void *context,uint32_t offset,uint32_t *value) {
    struct xnow_sd8686 *radio=context;
    if(!radio->verified || offset&3 || offset>XNOW_MAILBOX_BYTES-4)return -1;
    return word(radio->fd,XNOW_RADIO_STATE_BASE+offset,0,value);
}
static int write_mailbox(void *context,uint32_t offset,uint32_t value) {
    struct xnow_sd8686 *radio=context;uint32_t magic,pool;
    if(!radio->verified || offset&3 || (offset!=4 && (offset<20 || offset>=52)))return -1;
    if(word(radio->fd,0xc000d5a8,0,&pool) || pool!=0x0003076c ||
       word(radio->fd,XNOW_RADIO_STATE_BASE,0,&magic) || magic!=XNOW_MAILBOX_MAGIC)return -1;
    return word(radio->fd,XNOW_RADIO_STATE_BASE+offset,1,&value);
}
int xnow_sd8686_pool_info(uint32_t *stride,uint32_t *count,uint32_t *free_blocks) {
    int fd=driver_socket(),result=-1;uint32_t sizes,counts;
    if(fd<0 || !stride || !count || !free_blocks){if(fd>=0)close(fd);return -1;}
    if(!word(fd,0xc000d5a8,0,&sizes) && !word(fd,0xc000d5ac,0,&counts)) {
        *stride=sizes&0xffff;*count=sizes>>16;*free_blocks=counts&0xffff;result=0;
    }
    close(fd);return result;
}
int xnow_sd8686_open(struct xnow_sd8686 *radio,struct xnow_mailbox *mailbox) {
    uint32_t value;unsigned offset;struct xnow_word_io io;int result=XNOW_IDENTITY;
    if(!radio || !mailbox)return XNOW_ARGUMENT;
    radio->verified=0;radio->fd=driver_socket();if(radio->fd<0)return XNOW_IO;
    if(word(radio->fd,0xc000d5a8,0,&value) || value!=0x0003076c)goto fail;
    for(offset=0;offset<sizeof(xnow_radio_expected_code);offset+=4) {
        if(word(radio->fd,XNOW_RADIO_CODE_BASE+offset,0,&value) ||
           value!=xnow_le32(xnow_radio_expected_code+offset))goto fail;
    }
    if(word(radio->fd,XNOW_RADIO_STATE_BASE,0,&value) || value!=XNOW_MAILBOX_MAGIC)goto fail;
    radio->verified=1;io.context=radio;io.read=read_mailbox;io.write=write_mailbox;
    result=xnow_mailbox_open(mailbox,&io);if(result)goto fail;
    return XNOW_OK;
fail:xnow_sd8686_close(radio);return result;
}
void xnow_sd8686_close(struct xnow_sd8686 *radio) {
    if(radio){if(radio->fd>=0)close(radio->fd);radio->fd=-1;radio->verified=0;}
}
