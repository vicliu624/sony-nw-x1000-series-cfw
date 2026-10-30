/* Standard Espressif interoperability bench. No XNOW framing or persistence. */
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include "esp_now.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_idf_version.h"
#include "driver/usb_serial_jtag.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"

#if ESP_IDF_VERSION < ESP_IDF_VERSION_VAL(5,5,1)
#error This bench requires ESP-IDF 5.5.1 or newer
#endif
typedef struct { unsigned kind; uint8_t src[6], dst[6]; int length, status;
    uint8_t data[1564]; } Event;
static QueueHandle_t events;
static portMUX_TYPE lock = portMUX_INITIALIZER_UNLOCKED;
static unsigned dropped;
static bool busy, pmk_set;
static bool capture_enabled;
static uint8_t capture_source[6];
static bool completion_pending;
static int completion_status;
static char line[3100];
static size_t line_used;
static bool line_discard;
static uint8_t payload[ESP_NOW_MAX_DATA_LEN_V2];
static void wipe(void *p, size_t n) { volatile uint8_t *v=p; while(n--)*v++=0; }
static void enqueue(Event *e) {
    if(xQueueSend(events,e,0)!=pdTRUE){portENTER_CRITICAL(&lock);dropped++;portEXIT_CRITICAL(&lock);}
}
static void received(const esp_now_recv_info_t *i,const uint8_t *p,int n) {
    if(!i||n<0||n>ESP_NOW_MAX_DATA_LEN_V2||(!p&&n))return;
    Event e={.kind=1,.length=n};memcpy(e.src,i->src_addr,6);memcpy(e.dst,i->des_addr,6);
    if(n){memcpy(e.data,p,n);}
    enqueue(&e);
}
static void captured(void *buffer,wifi_promiscuous_pkt_type_t type){
    if(!buffer||type!=WIFI_PKT_MGMT)return;
    const wifi_promiscuous_pkt_t *packet=buffer;
    int n=packet->rx_ctrl.sig_len;
    if(packet->rx_ctrl.rx_state||n<59||n>1564)return;
    const uint8_t *p=packet->payload;
    if(p[0]!=0xd0||(p[1]&0xc7)!=0x40||p[22]&15||memcmp(p+16,"\xff\xff\xff\xff\xff\xff",6))return;
    portENTER_CRITICAL(&lock);
    bool selected=capture_enabled&&!memcmp(p+10,capture_source,6);
    portEXIT_CRITICAL(&lock);
    if(!selected)return;
    Event e={.kind=2,.length=n};if(n){memcpy(e.data,p,n);}
    enqueue(&e);
}
static void sent(const esp_now_send_info_t *i,esp_now_send_status_t s) {
    (void)i;
    /* Only one send is outstanding. RX saturation cannot consume this slot. */
    portENTER_CRITICAL(&lock);
    if(busy&&!completion_pending){completion_status=s;completion_pending=true;}
    portEXIT_CRITICAL(&lock);
}
static int take_completion(int *status){int ready=0;portENTER_CRITICAL(&lock);if(completion_pending){*status=completion_status;completion_pending=false;busy=false;ready=1;}portEXIT_CRITICAL(&lock);return ready;}
static int digit(char c){if(c>='0'&&c<='9')return c-'0';if(c>='a'&&c<='f')return c-'a'+10;if(c>='A'&&c<='F')return c-'A'+10;return -1;}
static int hex(const char *s,uint8_t *out,size_t cap){size_t n=strlen(s);if(n%2||n/2>cap)return -1;for(size_t j=0;j<n;j++)if(digit(s[j])<0)return -1;for(size_t j=0;j<n/2;j++)out[j]=(digit(s[j*2])<<4)|digit(s[j*2+1]);return (int)(n/2);}
static void printhex(const uint8_t *p,int n){while(n--)printf("%02x",*p++);}
static void status(void){uint32_t version=0;uint8_t mac[6],ch=0;wifi_second_chan_t second;esp_now_peer_num_t peers={0};esp_now_get_version(&version);esp_wifi_get_mac(WIFI_IF_STA,mac);esp_wifi_get_channel(&ch,&second);esp_now_get_peer_num(&peers);portENTER_CRITICAL(&lock);unsigned drops=dropped;bool pending=busy;portEXIT_CRITICAL(&lock);printf("STATUS bench=0.1.3 espnow=%lu max=%d channel=%u peers=%d encrypted=%d busy=%u drops=%u mac=",(unsigned long)version,ESP_NOW_MAX_DATA_LEN_V2,ch,peers.total_num,peers.encrypt_num,pending,drops);printhex(mac,6);puts("");}
static void command(char *s){
    char *save=NULL,*cmd=strtok_r(s," ",&save),*a=strtok_r(NULL," ",&save),*b=strtok_r(NULL," ",&save),*extra=strtok_r(NULL," ",&save);
    uint8_t mac[6],key[16];esp_err_t result=ESP_ERR_INVALID_ARG;
    if(!cmd)return;
    portENTER_CRITICAL(&lock);bool pending=busy;portEXIT_CRITICAL(&lock);
    if(!strcmp(cmd,"status")&&!a){status();return;}
    if(pending){puts("ERROR busy");return;}
    if(!strcmp(cmd,"capture")&&a&&!b){
        if(!strcmp(a,"off")){
            result=esp_wifi_set_promiscuous(false);
            if(result==ESP_OK){portENTER_CRITICAL(&lock);capture_enabled=false;wipe(capture_source,6);portEXIT_CRITICAL(&lock);}
        }else if(hex(a,mac,6)==6&&!(mac[0]&1)&&memcmp(mac,"\0\0\0\0\0\0",6)){
            /* Stop before replacing the filter, including callback races. */
            result=esp_wifi_set_promiscuous(false);
            if(result==ESP_OK){portENTER_CRITICAL(&lock);capture_enabled=false;memcpy(capture_source,mac,6);portEXIT_CRITICAL(&lock);
                wifi_promiscuous_filter_t filter={.filter_mask=WIFI_PROMIS_FILTER_MASK_MGMT};
                result=esp_wifi_set_promiscuous_filter(&filter);
                if(result==ESP_OK)result=esp_wifi_set_promiscuous_rx_cb(captured);
                if(result==ESP_OK){portENTER_CRITICAL(&lock);capture_enabled=true;portEXIT_CRITICAL(&lock);result=esp_wifi_set_promiscuous(true);}
                if(result!=ESP_OK){portENTER_CRITICAL(&lock);capture_enabled=false;portEXIT_CRITICAL(&lock);}
            }
        }
    }
    else if(!strcmp(cmd,"pmk")&&a&&!b&&hex(a,key,16)==16){result=esp_now_set_pmk(key);if(result==ESP_OK)pmk_set=true;}
    else if(!strcmp(cmd,"peer")&&a&&b&&!extra&&hex(a,mac,6)==6){
        esp_now_peer_info_t p={.ifidx=WIFI_IF_STA};memcpy(p.peer_addr,mac,6);
        if(!strcmp(b,"plain"))result=esp_now_add_peer(&p);
        else if(pmk_set&&!(mac[0]&1)&&hex(b,p.lmk,16)==16){p.encrypt=true;result=esp_now_add_peer(&p);}
        wipe(&p,sizeof p);
    }else if(!strcmp(cmd,"delete")&&a&&!b&&hex(a,mac,6)==6)result=esp_now_del_peer(mac);
    else if(!strcmp(cmd,"send")&&a&&b&&!extra&&hex(a,mac,6)==6){
        int n=!strcmp(b,"-")?0:hex(b,payload,sizeof payload);
        if(n>=0){portENTER_CRITICAL(&lock);busy=true;portEXIT_CRITICAL(&lock);result=esp_now_send(mac,payload,n);if(result!=ESP_OK){portENTER_CRITICAL(&lock);busy=false;portEXIT_CRITICAL(&lock);}}
    }
    wipe(key,sizeof key);wipe(payload,sizeof payload);printf("RESULT %d\n",(int)result);
}
static void feed(uint8_t c){
    if(c=='\n'){if(line_discard)puts("ERROR invalid-line");else{line[line_used]=0;command(line);}wipe(line,sizeof line);line_used=0;line_discard=false;}
    else if(c!='\r'){if(c<32||c>126||line_used+1>=sizeof line)line_discard=true;else if(!line_discard)line[line_used++]=(char)c;}
}
static void print_event(const Event *e){
    if(e->kind==2){printf("CAPTURE fcs=1 length=%d frame=",e->length);}
    else{printf("RX src=");printhex(e->src,6);printf(" dst=");printhex(e->dst,6);printf(" length=%d data=",e->length);}
    printhex(e->data,e->length);puts("");
}
void app_main(void){
    events=xQueueCreate(8,sizeof(Event));configASSERT(events);
    usb_serial_jtag_driver_config_t serial={.tx_buffer_size=4096,.rx_buffer_size=4096};ESP_ERROR_CHECK(usb_serial_jtag_driver_install(&serial));
    ESP_ERROR_CHECK(esp_netif_init());ESP_ERROR_CHECK(esp_event_loop_create_default());
    wifi_init_config_t config=WIFI_INIT_CONFIG_DEFAULT();config.nvs_enable=0;
    ESP_ERROR_CHECK(esp_wifi_init(&config));ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_RAM));
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));ESP_ERROR_CHECK(esp_wifi_start());
    ESP_ERROR_CHECK(esp_wifi_set_ps(WIFI_PS_NONE));ESP_ERROR_CHECK(esp_wifi_set_channel(8,WIFI_SECOND_CHAN_NONE));
    ESP_ERROR_CHECK(esp_now_init());ESP_ERROR_CHECK(esp_now_register_recv_cb(received));ESP_ERROR_CHECK(esp_now_register_send_cb(sent));
    /* No peers, automatic messages, router connection, keys or saved state. */
    status();
    for(;;){int completed;if(take_completion(&completed))printf("TX status=%d\n",completed);
        uint8_t input[64];int count=usb_serial_jtag_read_bytes(input,sizeof input,pdMS_TO_TICKS(10));
        for(int n=0;n<count;n++){feed(input[n]);}
        wipe(input,sizeof input);
        Event e;for(unsigned budget=0;budget<8&&xQueueReceive(events,&e,0)==pdTRUE;budget++){print_event(&e);wipe(&e,sizeof e);}
    }
}
