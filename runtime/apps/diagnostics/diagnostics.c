/* External read-only diagnostics. C + stock libc; no Sony internal addresses. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../../native/frontend.h"
#include "../../native/linux_devices.h"
#include "../../native/linux_signals.h"
#include "../../native/font.inc"

static unsigned short surface[HB_DISPLAY_PIXELS];
static volatile int stopped;
static char mtd[4097],mounts[8193],memory[4097];
static int mtd_ok,mounts_ok,memory_ok;
static void decimal(char *out,unsigned value) {
    char reverse[10];unsigned used=0;
    do{reverse[used++]=(char)('0'+value%10);value/=10;}while(value);
    for(unsigned i=0;i<used;i++)out[i]=reverse[used-i-1];
    out[used]=0;
}

static int read_proc(const char *name,char *buffer,unsigned capacity) {
    const char *root=getenv("HB_DIAG_PROC_ROOT");
    if(!root)root="/proc";
    char path[512];
    if(strlen(root)+strlen(name)+2>sizeof path){buffer[0]=0;return -1;}
    unsigned n=0;while(root[n]){path[n]=root[n];n++;}path[n++]='/';
    unsigned j=0;do{path[n++]=name[j];}while(name[j++]);
    FILE *file=fopen(path,"rb");if(!file){buffer[0]=0;return -1;}
    unsigned used=(unsigned)fread(buffer,1,capacity-1,file);
    int failed=ferror(file);if(fclose(file))failed=1;
    buffer[used]=0;return failed?-1:0;
}
static void collect(void) {
    mtd_ok=read_proc("mtd",mtd,sizeof mtd)==0;
    mounts_ok=read_proc("mounts",mounts,sizeof mounts)==0;
    memory_ok=read_proc("meminfo",memory,sizeof memory)==0;
}
static int mtd1_bytes(unsigned *value) {
    const char *line=mtd;
    while(*line){
        if(!strncmp(line,"mtd1:",5)){
            const char *p=line+5;while(*p==' '||*p=='\t')p++;
            unsigned result=0,digits=0;
            while(digits<8){unsigned c=(unsigned char)*p,n;
                if(c>='0'&&c<='9')n=c-'0';else if(c>='a'&&c<='f')n=c-'a'+10;else if(c>='A'&&c<='F')n=c-'A'+10;else break;
                result=(result<<4)|n;p++;digits++;
            }
            if(digits!=8||(*p!=' '&&*p!='\t'))return -1;
            *value=result;return 0;
        }
        const char *next=strchr(line,'\n');if(!next)break;line=next+1;
    }
    return -1;
}
static void box(int x,int y,int w,int h,unsigned short color) {
    for(int j=y;j<y+h&&j<432;j++)for(int i=x;i<x+w&&i<240;i++)surface[j*240+i]=color;
}
static void text(int x,int y,const char *s,int scale) {
    for(;*s&&x<228;s++,x+=6*scale){
        unsigned c=(unsigned char)*s;if(c>='a'&&c<='z')c-=32;
        int index=c>='0'&&c<='9'?(int)(c-'0'):c>='A'&&c<='Z'?(int)(c-'A'+10):-1;
        if(index<0)continue;
        for(int j=0;j<7;j++)for(int i=0;i<5;i++)if(glyph[index][j]&(1<<(4-i)))box(x+i*scale,y+j*scale,scale,scale,0xffff);
    }
}
static void draw(unsigned refresh) {
    unsigned value;char number[32];box(0,0,240,432,refresh%2?0x0320:0x001f);
    text(12,18,"DEVICE CHECK",2);text(12,64,getenv("HB_DIAG_PROC_ROOT")?"PC TEST DATA":"READ ONLY STATUS",1);
    text(12,100,"PROC MTD",1);text(150,100,mtd_ok?"YES":"NO",1);
    text(12,128,"MTD1 BYTES",1);
    if(mtd_ok&&!mtd1_bytes(&value)){decimal(number,value);text(12,150,number,2);}
    else text(12,150,"UNAVAILABLE",2);
    text(12,200,"PROC MOUNTS",1);text(150,200,mounts_ok?"YES":"NO",1);
    text(12,228,"PROC MEMINFO",1);text(150,228,memory_ok?"YES":"NO",1);
    text(12,278,"NO FILES WRITTEN",1);text(12,310,"TAP TO REFRESH",1);
    box(0,384,240,48,0x18c3);text(18,402,"BACK TO APPS",2);
}
static int graphical(void) {
    struct hb_devices devices;unsigned refresh=0;int pressed=0,cancel=0,x=0,y=0,input_failed=0;
    if(hb_stop_signals_install(&stopped))return 2;
    collect();draw(refresh);
    if(hb_devices_open(&devices,surface,HB_DISPLAY_PIXELS,&stopped))return stopped?0:2;
    hb_devices_present(&devices);
    while(!stopped&&!devices.failed){
        hb_devices_flush(&devices);unsigned char packet[11];int received=hb_devices_next_touch(&devices,packet,50);
        if(received<0){input_failed=!stopped;break;}
        if(!received)continue;
        struct hb_touch touch;hb_touch_decode(packet,&touch);
        if(touch.down){if(!pressed){x=touch.x;y=touch.y;cancel=0;}pressed=1;
            if(!touch.in_bounds||(int)touch.x-x>12||x-(int)touch.x>12||(int)touch.y-y>12||y-(int)touch.y>12)cancel=1;
            continue;
        }
        if(!pressed)continue;
        pressed=0;
        if(cancel||!touch.in_bounds)continue;
        if(y>=384)break;
        collect();draw(++refresh);hb_devices_present(&devices);
    }
    int failed=devices.failed||input_failed;if(hb_devices_close(&devices)<0)return 2;
    return stopped?0:failed?2:0;
}
int main(int argc,char **argv) {
    if(argc==1)return graphical();
    if(argc==2&&!strcmp(argv[1],"--help")){puts("Device Check: read /proc/mtd, /proc/mounts, /proc/meminfo. Tap refresh; BACK returns. No log files or raw storage access.");return 0;}
    if(argc==2&&!strcmp(argv[1],"--dump")){
        unsigned bytes;collect();puts("DEVICE CHECK - STDOUT ONLY");
        if(mtd_ok&&!mtd1_bytes(&bytes)){char number[16];decimal(number,bytes);fputs("MTD1_BYTES=",stdout);puts(number);}else puts("MTD1_BYTES=UNAVAILABLE");
        puts("[mtd]");fputs(mtd,stdout);puts("\n[mounts]");fputs(mounts,stdout);puts("\n[meminfo]");fputs(memory,stdout);puts("");
        return mtd_ok&&mounts_ok&&memory_ok?0:1;
    }
    return 64;
}
