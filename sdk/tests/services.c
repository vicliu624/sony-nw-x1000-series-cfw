/* Real SDK native-service client. Safe CLI tests never open a hardware node. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <x1000/services/display.h>
#include <x1000/services/touch.h>
#include <x1000/services/stat.h>
#include <x1000/services/files.h>
#include <x1000/services/sha256.h>
#include <x1000/services/process.h>
#include <x1000/services/url.h>
#include <x1000/services/dns.h>
#include <x1000/services/clock.h>
#include <x1000/services/pcm.h>
#include <x1000/services/fm_tuner.h>
#include <x1000/services/unicode_font.h>
#include <x1000/services/images.h>
#include <x1000/services/system_info.h>
#include <x1000/services/volume_policy.h>
#include <x1000/services/package_platform.h>
#include <x1000/services/package_canvas.h>
#include "rgb-fixture.h"
#ifndef HB_BUILD_VERSION
#define HB_BUILD_VERSION "unknown"
#endif
static unsigned short pixels[240u*432u];
static long (*volatile process_function)(void)=hb_linux_fork;
static int tune(void *context,int frequency){*(int *)context=frequency;return 0;}
static int sample(void *context,int *strength){(void)context;*strength=55;return 1;}
static int selftest(void){
    struct hb_touch touch;unsigned char packet[11]={0};packet[1]=1;
    hb_touch_decode(packet,&touch);if(!touch.down||!touch.in_bounds)return 1;
    struct hb_sha256 hash;unsigned char digest[32];hb_sha256_init(&hash);hb_sha256_update(&hash,(const unsigned char *)"abc",3);hb_sha256_final(&hash,digest);
    if(digest[0]!=0xba||digest[31]!=0xad)return 2;
    const char *utf8="\xe4\xbd\xa0";if(dx_utf8(&utf8)!=0x4f60||*utf8)return 3;
    unsigned short thumbnail[4];if(qq_image_thumbnail(rgb_fixture,sizeof rgb_fixture,thumbnail,2)||thumbnail[0]!=0xf800)return 4;
    struct hb_https_url url;if(hb_https_url_parse("https://example.test/a?b=1",&url)||url.port!=443||strcmp(url.host,"example.test"))return 5;
    if(!hb_https_url_parse("http://example.test/",&url))return 6;
    struct hb_dns_query dns;hb_dns_init(&dns);if(dns.state!=HB_DNS_EMPTY)return 7;hb_dns_release(&dns);
    unsigned long long now;if(hb_monotonic_millis(&now)||!now)return 8;
    struct hb_pcm_output pcm;hb_pcm_init(&pcm);if(pcm.dsp!=-1||pcm.mixer!=-1||pcm.enabled)return 9;
    int frequency=0;struct fm_radio radio;struct fm_band band={76000,108000,100};struct fm_backend backend={&frequency,tune,sample};
    if(fm_init(&radio,band,backend)||fm_tune(&radio,96000)||frequency!=96000)return 10;
    struct qq_storage_policy policy={"/dev/mtdblock/2","vfat"};
    const char *mounts="/dev/root / ext2 ro 0 0\n/dev/mtdblock/2 /contents vfat rw 0 0\n";
    struct qq_storage_directory dirs[]={{"/",1,0040000},{"/contents",2,0040000}};
    struct qq_storage_plan plan;memset(&plan,0,sizeof plan);plan.source=67108864;plan.files[0]=1;plan.reserve=1048576;plan.allocation_unit=4096;plan.available_units=65536;
    uint64_t required=0;if(qq_storage_preflight(&policy,mounts,strlen(mounts),dirs,2,&plan,&required)||required<68157440)return 11;
    struct hb_store_canvas canvas;struct hb_store_painter painter;if(hb_store_canvas_init(&canvas,pixels,240u*432u,&painter))return 12;
    painter.rect(painter.context,0,0,1,1,0x1234);if(pixels[0]!=0x1234)return 13;
    struct hb_store_platform platform;if(hb_store_native_platform(&platform)||!platform.open||!platform.close)return 14;
    struct hb_target_stat st;if(hb_target_lstat("sdk/VERSION",&st)||st.st_size<1)return 15;
    long fd=hb_file_open_read("sdk/VERSION");char buffer[64];if(fd<0||hb_file_read((int)fd,buffer,sizeof buffer)<1||hb_file_close((int)fd))return 16;
    if(!process_function)return 17;
    char size[38];hb_info_size(size,34359738368ULL);if(strcmp(size,"32.0 GiB"))return 18;
    puts("SDK services: display types, Unicode, images, URL/TLS dependencies, clock, PCM, FM model, large-volume planning, package canvas, stock files and process API passed");return 0;
}
int main(int argc,char **argv){
    if(argc==2&&!strcmp(argv[1],"--help")){puts("Native SDK service client: --selftest uses memory and ordinary source files, no network account or hardware.");return 0;}
    if(argc==2&&!strcmp(argv[1],"--version")){puts(HB_BUILD_VERSION);return 0;}
    return argc==2&&!strcmp(argv[1],"--selftest")?selftest():64;
}
