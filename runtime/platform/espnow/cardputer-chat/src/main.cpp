/* Original Cardputer keyboard/display chat peer. No AP, router or IP fallback. */
#include <Arduino.h>
#include <M5Cardputer.h>
#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>
#include <atomic>
#include "../chat_ui.h"
extern "C" {
#include "../../xnow_chat.h"
}
struct Incoming {uint8_t mac[6],packet[32];};
struct History {char text[97];uint32_t sequence;uint8_t mine,state;};
static QueueHandle_t incoming;
static xnow_chat chat;
static History history[8];
static unsigned historyCount,historyNext;
static uint8_t channel=8,peer[6]={255,255,255,255,255,255};
static bool paired,ready,dirty=true,discardLine;
static char editor[97],command[128],notice[40]="WAITING FOR X1060";
static size_t edited,commandSize;
static uint32_t lastRadioSend;
static std::atomic<uint32_t> macOk{0},macFail{0},drops{0};
static uint16_t displayPixels[xnow_ui::W*xnow_ui::H];
static int radioSend(const uint8_t packet[32]) {
    if(!ready)return -1;
    esp_err_t result=esp_now_send(peer,packet,32);
    if(result==ESP_OK){lastRadioSend=millis();return 0;}
    return result==ESP_ERR_ESPNOW_NO_MEM?1:-1;
}
static int sendChat(void *,const uint8_t packet[32]){return radioSend(packet);}
static void addHistory(const char *text,unsigned n,bool mine,uint32_t sequence) {
    History &h=history[historyNext];memset(&h,0,sizeof(h));memcpy(h.text,text,n);
    h.mine=mine;h.sequence=sequence;h.state=mine?0:1;
    historyNext=(historyNext+1)%8;if(historyCount<8)historyCount++;dirty=true;
}
static void event(void *,int type,const char *text,unsigned n) {
    if(type==XNOW_CHAT_MESSAGE){addHistory(text,n,false,chat.incoming_sequence);Serial.printf("CHAT_RX seq=%lu token=%08lx text=%.*s\n",(unsigned long)chat.incoming_sequence,(unsigned long)chat.incoming_token,(int)n,text);}
    else {
        for(auto &h:history)if(h.mine&&h.sequence==chat.sequence)h.state=type==XNOW_CHAT_DELIVERED?1:2;
        snprintf(notice,sizeof(notice),"%s",type==XNOW_CHAT_DELIVERED?"PEER CONFIRMED":"NO PEER ACK");
        Serial.printf("CHAT_%s seq=%lu token=%08lx text=%.*s\n",type==XNOW_CHAT_DELIVERED?"DELIVERED":"UNCONFIRMED",(unsigned long)chat.sequence,(unsigned long)chat.token,(int)n,text);dirty=true;
    }
}
static bool addPeer(const uint8_t mac[6]) {
    if(esp_now_is_peer_exist(mac))esp_now_del_peer(mac);
    esp_now_peer_info_t p={};memcpy(p.peer_addr,mac,6);p.channel=channel;p.ifidx=WIFI_IF_STA;
    return esp_now_add_peer(&p)==ESP_OK;
}
static void received(const uint8_t *mac,const uint8_t *data,int n) {
    if(n!=32)return;Incoming p;memcpy(p.mac,mac,6);memcpy(p.packet,data,32);
    if(xQueueSend(incoming,&p,0)!=pdTRUE)++drops;
}
static void sent(const uint8_t *,esp_now_send_status_t status){if(status==ESP_NOW_SEND_SUCCESS)++macOk;else ++macFail;}
static void submit(const char *text,unsigned n) {
    uint32_t token=esp_random();if(!token)token=1;
    int result=xnow_chat_submit(&chat,text,n,token,millis());
    if(result==0){addHistory(text,n,true,chat.sequence);strcpy(notice,"SENDING - WAIT FOR ACK");Serial.printf("CHAT_SUBMIT seq=%lu token=%08lx text=%.*s\n",(unsigned long)chat.sequence,(unsigned long)token,(int)n,text);}
    else strcpy(notice,result==1?"WAIT FOR CURRENT MESSAGE":"MESSAGE LENGTH 1..96");
    dirty=true;
}
static void render() {
    xnow_ui::Message messages[8];
    for(unsigned k=0;k<historyCount;k++) {
        const History &h=history[(historyNext+8-historyCount+k)%8];
        messages[k]={h.text,h.mine,h.state};
    }
    xnow_ui::render(displayPixels,messages,historyCount,editor,channel,paired,ready,chat.active,notice);
    M5Cardputer.Display.setSwapBytes(true);
    M5Cardputer.Display.pushImage(0,0,xnow_ui::W,xnow_ui::H,displayPixels);
    dirty=false;
}
static void status() {
    Serial.printf("CHAT_STATUS version=0.1.0-dev.2 channel=%u paired=%u active=%u mac_ok=%lu mac_fail=%lu drops=%lu\n",channel,paired,chat.active,(unsigned long)macOk.load(),(unsigned long)macFail.load(),(unsigned long)drops.load());
}
static void resetPeer() {
    if(chat.active){strcpy(notice,"WAIT FOR CURRENT MESSAGE");dirty=true;return;}
    if(paired&&esp_now_is_peer_exist(peer))esp_now_del_peer(peer);
    memset(peer,255,6);paired=false;addPeer(peer);strcpy(notice,"WAITING FOR X1060");dirty=true;
}
static void serialCommand() {
    command[commandSize]=0;
    if(!strcmp(command,"status"))status();
    else if(!strncmp(command,"say ",4))submit(command+4,strlen(command+4));
    else if(!strcmp(command,"pair"))resetPeer();
    else if(!strncmp(command,"channel ",8)) {
        char *end;unsigned long n=strtoul(command+8,&end,10);
        if(!*end&&n>=1&&n<=13&&!chat.active&&esp_wifi_set_channel(n,WIFI_SECOND_CHAN_NONE)==ESP_OK){channel=n;resetPeer();}
        else Serial.println("CHAT_ERROR channel rejected");
    } else Serial.println("COMMANDS status | say text | pair | channel 1..13");
    commandSize=0;
}
void setup() {
    Serial.begin(115200);auto cfg=M5.config();cfg.internal_spk=false;cfg.internal_mic=false;
    M5Cardputer.begin(cfg,true);M5Cardputer.Display.setRotation(1);
    incoming=xQueueCreate(12,sizeof(Incoming));
    xnow_chat_init(&chat,nullptr,sendChat,event);
    WiFi.persistent(false);WiFi.mode(WIFI_STA);WiFi.disconnect();esp_wifi_set_ps(WIFI_PS_NONE);
    ready=incoming&&esp_wifi_set_channel(channel,WIFI_SECOND_CHAN_NONE)==ESP_OK&&esp_now_init()==ESP_OK;
    if(ready){esp_now_register_recv_cb(received);esp_now_register_send_cb(sent);ready=addPeer(peer);}
    if(!ready)strcpy(notice,"RADIO INITIALIZATION FAILED");
    Serial.printf("XNOW_CHAT_READY result=%u mac=%s\n",ready,WiFi.macAddress().c_str());status();render();
}
void loop() {
    M5Cardputer.update();uint32_t now=millis();
    if(M5Cardputer.Keyboard.isChange()&&M5Cardputer.Keyboard.isPressed()) {
        auto key=M5Cardputer.Keyboard.keysState();
        if(key.fn&&key.word.size()&&key.word[0]=='p')resetPeer();
        else {
            for(char c:key.word)if(c>=32&&c<127&&edited<96)editor[edited++]=c;
            if(key.del&&edited)edited--;
            editor[edited]=0;
            if(key.enter&&edited&&!chat.active){submit(editor,edited);edited=0;editor[0]=0;}
            dirty=true;
        }
    }
    while(Serial.available()) {
        char c=Serial.read();if(c=='\r')continue;
        if(c=='\n'){if(!discardLine)serialCommand();discardLine=false;commandSize=0;}
        else if(!discardLine){if(commandSize+1<sizeof(command))command[commandSize++]=c;else{discardLine=true;Serial.println("CHAT_ERROR line too long");}}
    }
    Incoming p;
    while(incoming&&xQueueReceive(incoming,&p,0)==pdTRUE) {
        xnow_view view;if(xnow_decode(p.packet,32,&view))continue;
        if(paired&&memcmp(peer,p.mac,6))continue;
        if(!paired){memcpy(peer,p.mac,6);paired=addPeer(peer);dirty=true;}
        if(view.kind==XNOW_PING&&view.sequence) {
            uint8_t pong[32];size_t n;
            if(!xnow_encode(pong,32,XNOW_PONG,view.sequence,view.token,view.payload,16,&n))radioSend(pong);
        } else xnow_chat_receive(&chat,p.packet,now);
    }
    xnow_chat_tick(&chat,now);
    if(ready&&(uint32_t)(now-lastRadioSend)>=250) {
        uint8_t poll[32],body[16]={0};size_t n;
        if(!xnow_encode(poll,32,XNOW_PING,0,0,body,16,&n))radioSend(poll);
    }
    if(dirty)render();delay(2);
}
