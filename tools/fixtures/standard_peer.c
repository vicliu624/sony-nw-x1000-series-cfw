#include "standard_peer_stubs.h"
#include <stdlib.h>
#include <string.h>
#include "../../runtime/platform/espnow/standard-peer/main/peer.c"
struct MockQueue { unsigned count,cap,read,write;size_t size;unsigned char *data; };
static unsigned sends,adds,keys,deletes;static int send_result;static size_t sent_length;
static uint8_t sent_data[1470];static esp_now_peer_info_t added;
static bool promiscuous;
esp_err_t esp_wifi_set_promiscuous(bool p){promiscuous=p;return 0;}
esp_err_t esp_wifi_set_promiscuous_filter(const wifi_promiscuous_filter_t *p){assert(p->filter_mask==WIFI_PROMIS_FILTER_MASK_MGMT);return 0;}
esp_err_t esp_wifi_set_promiscuous_rx_cb(void (*p)(void *,wifi_promiscuous_pkt_type_t)){assert(p==captured);return 0;}
QueueHandle_t xQueueCreate(unsigned n,size_t size){struct MockQueue *q=calloc(1,sizeof *q);assert(q);q->data=calloc(n,size);assert(q->data);q->cap=n;q->size=size;return q;}
int xQueueSend(QueueHandle_t q,const void *p,unsigned ticks){(void)ticks;if(q->count==q->cap)return 0;memcpy(q->data+q->write*q->size,p,q->size);q->write=(q->write+1)%q->cap;q->count++;return 1;}
int xQueueReceive(QueueHandle_t q,void *p,unsigned ticks){(void)ticks;if(!q->count)return 0;memcpy(p,q->data+q->read*q->size,q->size);q->read=(q->read+1)%q->cap;q->count--;return 1;}
esp_err_t esp_now_set_pmk(const uint8_t *p){(void)p;keys++;return 0;}
esp_err_t esp_now_add_peer(const esp_now_peer_info_t *p){adds++;added=*p;return 0;}
esp_err_t esp_now_del_peer(const uint8_t *p){(void)p;deletes++;return 0;}
esp_err_t esp_now_send(const uint8_t *m,const uint8_t *p,size_t n){(void)m;sends++;sent_length=n;memcpy(sent_data,p,n);return send_result;}
esp_err_t esp_now_get_version(uint32_t *v){*v=2;return 0;}
esp_err_t esp_now_get_peer_num(esp_now_peer_num_t *p){memset(p,0,sizeof *p);return 0;}
esp_err_t esp_wifi_get_mac(int i,uint8_t *m){(void)i;memset(m,0,6);return 0;}
esp_err_t esp_wifi_get_channel(uint8_t *c,wifi_second_chan_t *s){*c=8;*s=0;return 0;}
esp_err_t esp_wifi_init(const wifi_init_config_t *p){assert(!p->nvs_enable);return 0;}
esp_err_t esp_wifi_set_storage(int p){(void)p;return 0;}
esp_err_t esp_wifi_set_mode(int p){(void)p;return 0;}
esp_err_t esp_wifi_set_ps(int p){(void)p;return 0;}
esp_err_t esp_wifi_set_channel(int p,int s){(void)p;(void)s;return 0;}
esp_err_t esp_wifi_start(void){return 0;}
esp_err_t esp_netif_init(void){return 0;}
esp_err_t esp_event_loop_create_default(void){return 0;}
esp_err_t esp_now_init(void){return 0;}
esp_err_t esp_now_register_recv_cb(void (*p)(const esp_now_recv_info_t *,const uint8_t *,int)){(void)p;return 0;}
esp_err_t esp_now_register_send_cb(void (*p)(const esp_now_send_info_t *,esp_now_send_status_t)){(void)p;return 0;}
esp_err_t usb_serial_jtag_driver_install(const usb_serial_jtag_driver_config_t *p){(void)p;return 0;}
int usb_serial_jtag_read_bytes(void *p,size_t n,unsigned t){(void)p;(void)n;(void)t;return 0;}
static void run(const char *s){char b[3100];assert(strlen(s)<sizeof b);strcpy(b,s);command(b);}
int main(int argc,char **argv){
 events=xQueueCreate(8,sizeof(Event));
 if(argc==2){
   FILE *input=fopen(argv[1],"rb");assert(input);wifi_promiscuous_pkt_t packet={0};
   size_t n=fread(packet.payload,1,sizeof packet.payload,input);assert(feof(input)||n==sizeof packet.payload);assert(fgetc(input)==EOF);fclose(input);
   packet.rx_ctrl.sig_len=(unsigned)n;run("capture 020000000000");captured(&packet,WIFI_PKT_MGMT);
   Event event;assert(xQueueReceive(events,&event,0));print_event(&event);assert(!events->count);
   free(events->data);free(events);return 0;
 }
 assert(argc==1);
 wifi_promiscuous_pkt_t raw={.rx_ctrl={.sig_len=59}};raw.payload[0]=0xd0;raw.payload[1]=0x40;raw.payload[10]=2;memset(raw.payload+16,255,6);
 captured(&raw,WIFI_PKT_MGMT);assert(!events->count&&!promiscuous);
 run("capture 020000000000");assert(promiscuous&&capture_enabled);
 captured(&raw,WIFI_PKT_MGMT);Event capture;assert(xQueueReceive(events,&capture,0)&&capture.kind==2&&capture.length==59&&!memcmp(capture.data,raw.payload,59));
 raw.rx_ctrl.sig_len=1564;captured(&raw,WIFI_PKT_MGMT);assert(xQueueReceive(events,&capture,0)&&capture.length==1564);
 raw.rx_ctrl.sig_len=1565;captured(&raw,WIFI_PKT_MGMT);assert(!events->count);
 raw.rx_ctrl.sig_len=59;raw.payload[10]=4;captured(&raw,WIFI_PKT_MGMT);assert(!events->count);
 raw.payload[10]=2;raw.rx_ctrl.rx_state=1;captured(&raw,WIFI_PKT_MGMT);assert(!events->count);
 run("capture off");assert(!promiscuous&&!capture_enabled);raw.rx_ctrl.rx_state=0;captured(&raw,WIFI_PKT_MGMT);assert(!events->count);
 /* A full RX queue must not consume a TX completion or release busy early. */
 uint8_t m[6]={2},data[1470]={0};esp_now_recv_info_t info={m,m};
 /* IDF may represent a zero-length payload with a null data pointer. */
 received(&info,NULL,0);Event zero;
 assert(xQueueReceive(events,&zero,0)&&zero.kind==1&&zero.length==0);
 received(&info,NULL,1);assert(!events->count);
 received(NULL,data,0);assert(!events->count);
 received(&info,data,-1);assert(!events->count);
 received(&info,data,1471);assert(!events->count);

 for(unsigned i=0;i<8;i++)received(&info,data,1470);
 assert(events->count==8);busy=true;sent(NULL,0);
 assert(busy); /* Released only after the command task consumes completion. */
 assert(dropped==0);
 int completed=-1;assert(take_completion(&completed)==1&&completed==0&&!busy);
 assert(take_completion(&completed)==0);
 received(&info,data,1470);assert(dropped==1);
 Event e;for(unsigned i=0;i<8;i++){assert(xQueueReceive(events,&e,0));assert(e.length==1470&&!memcmp(e.data,data,1470));}
 unsigned before=sends;run("send 020000000000 0001ff");assert(sends==before+1&&busy&&sent_length==3&&sent_data[0]==0&&sent_data[2]==255);
 run("send 020000000000 00");assert(sends==before+1);
 sent(NULL,1);assert(take_completion(&completed)&&completed==1&&!busy);
 run("send 020000000000 0z");run("send 020000000000 0");run("send 020000000000 00 extra");assert(sends==before+1);
 run("peer 020000000000 00000000000000000000000000000000");assert(!adds);
 run("pmk 000102030405060708090a0b0c0d0e0f");assert(keys==1&&pmk_set);
 run("peer ffffffffffff 00000000000000000000000000000000");assert(!adds);
 run("peer 020000000000 000102030405060708090a0b0c0d0e0f");assert(adds==1&&added.encrypt&&added.lmk[15]==15);
 run("peer ffffffffffff plain");assert(adds==2&&!added.encrypt);
 run("delete 020000000000");assert(deletes==1);
 char long_command[3100];strcpy(long_command,"send 020000000000 ");size_t offset=strlen(long_command);
 for(unsigned i=0;i<1470;i++){long_command[offset+2*i]="0123456789abcdef"[(i>>4)&15];long_command[offset+2*i+1]="0123456789abcdef"[i&15];}
 long_command[offset+2940]=0;run(long_command);assert(sent_length==1470&&sent_data[1469]==(1469&255)&&busy);
 sent(NULL,0);assert(take_completion(&completed));
 long_command[offset+2940]='0';long_command[offset+2941]='0';long_command[offset+2942]=0;before=sends;run(long_command);assert(sends==before&&!busy);
 send_result=123;run("send 020000000000 -");assert(sends==before+1&&sent_length==0&&!busy);send_result=0;
 for(unsigned i=0;i<sizeof payload;i++)assert(payload[i]==0);
 before=keys;const char *pmk="pmk 000102030405060708090a0b0c0d0e0f";
 for(unsigned i=0;pmk[i];i++){feed(pmk[i]);}feed(0);feed('\n');assert(keys==before&&!line_used&&!line_discard);
 for(unsigned i=0;i<4000;i++){feed('x');}feed('\n');assert(!line_used&&!line_discard);
 for(unsigned i=0;pmk[i];i++){feed(pmk[i]);}feed('\r');feed('\n');assert(keys==before+1);
 for(unsigned i=0;i<sizeof line;i++)assert(line[i]==0);
 puts("capture default-off, selected source, min/max/oversize, RX errors and stop passed");
 puts("completion isolated from saturated RX queue");
 puts("binary1470, oversize, invalid hex, peer encryption policy, busy and immediate failures passed");
 free(events->data);free(events);return 0;
}
