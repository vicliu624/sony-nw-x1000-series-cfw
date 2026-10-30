/* Original Cardputer ESP32-S3 laboratory peer. Serial control; no AP or IP bridge. */
#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>
#include <atomic>
#include "../../xnow_frame.h"

static uint8_t peer[6] = {0x00,0x26,0xe8,0xd3,0x57,0xd2};
static uint8_t channel = 8;
static uint32_t sequence;
static char command[96];
static size_t used;
struct Observation { uint8_t mac[6]; uint16_t length; uint8_t data[64]; };
static QueueHandle_t observations;
struct ActionObservation { uint8_t data[64]; uint16_t length; int8_t rssi; };
static QueueHandle_t actions;
static std::atomic<uint32_t> dropped{0}, tx_ok{0}, tx_fail{0};
static void observe(void *buffer,wifi_promiscuous_pkt_type_t type) {
    if(type!=WIFI_PKT_MGMT)return;
    const wifi_promiscuous_pkt_t *p=(const wifi_promiscuous_pkt_t *)buffer;
    unsigned n=p->rx_ctrl.sig_len;
    if(n<25 || (p->payload[0]&0xfc)!=0xd0 || memcmp(p->payload+10,peer,6))return;
    ActionObservation o={};o.length=n;o.rssi=p->rx_ctrl.rssi;
    memcpy(o.data,p->payload,n>sizeof(o.data)?sizeof(o.data):n);
    if(xQueueSend(actions,&o,0)!=pdTRUE)++dropped;
}
static void receive(const uint8_t *mac,const uint8_t *data,int length) {
    if(length<0) return;
    Observation o = {}; memcpy(o.mac,mac,6); o.length=(uint16_t)length;
    memcpy(o.data,data,length>64?64:length);
    if(xQueueSend(observations,&o,0)!=pdTRUE) ++dropped;
}
static void sent(const uint8_t *,esp_now_send_status_t result) {
    if(result==ESP_NOW_SEND_SUCCESS) ++tx_ok; else ++tx_fail;
}
static void status() {
    uint8_t primary; wifi_second_chan_t secondary;
    esp_wifi_get_channel(&primary,&secondary);
    Serial.printf("STATUS version=0.1.3 mac=%s channel=%u peer=%02x:%02x:%02x:%02x:%02x:%02x tx_ok=%lu tx_fail=%lu dropped=%lu\n",
      WiFi.macAddress().c_str(),primary,peer[0],peer[1],peer[2],peer[3],peer[4],peer[5],(unsigned long)tx_ok.load(),(unsigned long)tx_fail.load(),(unsigned long)dropped.load());
}
static bool setPeer(const uint8_t *mac) {
    if(esp_now_is_peer_exist(peer)) esp_now_del_peer(peer);
    memcpy(peer,mac,6); esp_now_peer_info_t p={}; memcpy(p.peer_addr,peer,6);
    p.channel=channel; p.ifidx=WIFI_IF_STA; p.encrypt=false;
    return esp_now_add_peer(&p)==ESP_OK;
}
static void execute() {
    command[used]=0;
    if(!strcmp(command,"status")) status();
    else if(!strcmp(command,"send")) {
        uint8_t data[32];size_t length=0;
        uint32_t seq=++sequence, nonce=esp_random();
        const uint8_t payload[16]="X1060-CARDPUTER";
        xnow_encode(data,sizeof(data),XNOW_PING,seq,nonce,payload,sizeof(payload),&length);
        esp_err_t e=esp_now_send(peer,data,length);
        Serial.printf("SEND seq=%lu nonce=%08lx result=%d bytes=%u\n",(unsigned long)seq,(unsigned long)nonce,e,(unsigned)length);
    } else if(!strncmp(command,"channel ",8)) {
        char *end; unsigned long n=strtoul(command+8,&end,10);
        if(*end || n<1 || n>13) Serial.println("ERROR channel 1..13");
        else { esp_err_t e=esp_wifi_set_channel(n,WIFI_SECOND_CHAN_NONE); if(e==ESP_OK) { channel=n; uint8_t copy[6];memcpy(copy,peer,6);setPeer(copy); } Serial.printf("CHANNEL result=%d\n",e); }
    } else if(!strncmp(command,"peer ",5)) {
        unsigned m[6]; char extra;
        if(sscanf(command+5,"%x:%x:%x:%x:%x:%x%c",m,m+1,m+2,m+3,m+4,m+5,&extra)!=6) Serial.println("ERROR peer MAC");
        else {uint8_t mac[6];bool valid=true;for(int i=0;i<6;i++){if(m[i]>255)valid=false;mac[i]=m[i];}Serial.printf("PEER result=%d\n",valid&&setPeer(mac));}
    } else if(!strcmp(command,"observe on")) Serial.printf("OBSERVE result=%d\n",esp_wifi_set_promiscuous(true));
    else if(!strcmp(command,"observe off")) Serial.printf("OBSERVE result=%d\n",esp_wifi_set_promiscuous(false));
    else Serial.println("COMMANDS status | send | observe on/off | channel 1..13 | peer xx:xx:xx:xx:xx:xx");
    used=0;
}
void setup() {
    Serial.begin(115200); observations=xQueueCreate(8,sizeof(Observation));actions=xQueueCreate(8,sizeof(ActionObservation));
    if(!observations || !actions) {while(true)delay(1000);}
    WiFi.mode(WIFI_STA); WiFi.disconnect();
    esp_wifi_set_ps(WIFI_PS_NONE);
    esp_err_t e=esp_wifi_set_channel(channel,WIFI_SECOND_CHAN_NONE);
    if(e!=ESP_OK || esp_now_init()!=ESP_OK) {Serial.println("INIT FAILED");while(true)delay(1000);}
    esp_now_register_recv_cb(receive);esp_now_register_send_cb(sent);
    wifi_promiscuous_filter_t filter={};filter.filter_mask=WIFI_PROMIS_FILTER_MASK_MGMT;
    esp_wifi_set_promiscuous_filter(&filter);esp_wifi_set_promiscuous_rx_cb(observe);
    uint8_t copy[6];memcpy(copy,peer,6);if(!setPeer(copy))Serial.println("PEER FAILED");
    Serial.println("XNOW LAB READY - ESP-NOW only; manual send");status();
}
void loop() {
    while(Serial.available()) {char c=Serial.read(); if(c=='\r')continue; if(c=='\n')execute();else if(used+1<sizeof(command))command[used++]=c;else{used=0;Serial.println("ERROR line too long");}}
    Observation o;
    while(xQueueReceive(observations,&o,0)==pdTRUE) {
        Serial.printf("RECV mac=%02x:%02x:%02x:%02x:%02x:%02x bytes=%u data=",o.mac[0],o.mac[1],o.mac[2],o.mac[3],o.mac[4],o.mac[5],o.length);
        for(unsigned i=0;i<o.length && i<64;i++)Serial.printf("%02x",o.data[i]);Serial.println();
        xnow_view view;
        if(o.length<=sizeof(o.data) && !memcmp(o.mac,peer,6) && !xnow_decode(o.data,o.length,&view)) {
            Serial.printf("XNOW kind=%u seq=%lu token=%08lx\n",view.kind,(unsigned long)view.sequence,(unsigned long)view.token);
            if(view.kind==XNOW_PING) {
                uint8_t pong[64];size_t n=0;
                if(!xnow_encode(pong,sizeof(pong),XNOW_PONG,view.sequence,view.token,view.payload,view.length,&n))
                    Serial.printf("PONG result=%d\n",esp_now_send(peer,pong,n));
            }
        }
    }
    ActionObservation action;
    while(xQueueReceive(actions,&action,0)==pdTRUE){
        Serial.printf("ACTION_FROM_PEER bytes=%u rssi=%d category=%u body=",action.length,action.rssi,action.data[24]);
        for(unsigned i=24;i<action.length && i<sizeof(action.data);i++)Serial.printf("%02x",action.data[i]);Serial.println();
    }
    delay(2);
}
