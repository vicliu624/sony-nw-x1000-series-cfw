/* Native ESP-IDF Cardputer front end. A visible idle screen is not a player link. */
#include <M5GFX.h>
#include <cstdio>
#include <cstring>
#include "esp_app_desc.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_now.h"
#include "esp_wifi.h"
#include "esp_random.h"
#include "driver/usb_serial_jtag.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "../../receiver.h"
#include "../../session_wire.h"
#include "../../control.h"
#include "driver/gpio.h"
#include "esp_rom_sys.h"

static M5GFX display;
static bool lcd_ready;
static bool radio_ready;
static int8_t tx_power;
static uint8_t mac[6];
static char command[192];
static size_t used;
static bool discard_line;
static wr_receiver receiver;
struct packet { uint8_t source[6],data[WR_SIGNED_STATUS_BYTES];unsigned bytes; };
static QueueHandle_t packets;
static TickType_t last_status,challenge_sent_at;
static bool challenge_attempted;
static bool stale;
static uint32_t received_frames,accepted_status,wrong_source,bad_auth,bad_session,old_sequence;
static uint32_t command_serial,pending_command;
static TickType_t command_started;
static const char *command_state="A/D TRACK  W/S VOL  SPACE PLAY";
static void draw_status();
static void wipe(void *p,size_t n){volatile uint8_t *b=(volatile uint8_t *)p;while(n--)*b++=0;}
static void receive(const esp_now_recv_info_t *info,const uint8_t *data,int bytes){
    if(!info||!data||(bytes!=WR_SIGNED_STATUS_BYTES&&bytes!=WR_CONTROL_BYTES&&bytes!=WR_SESSION_BYTES)||!packets)return;
    packet p={};p.bytes=unsigned(bytes);std::memcpy(p.source,info->src_addr,6);std::memcpy(p.data,data,size_t(bytes));
    xQueueSend(packets,&p,0);
}
static void reconnect_step(){
    if(!radio_ready||!receiver.paired)return;
    if(receiver.have_status&&!stale){wr_receiver_cancel_challenge(&receiver);return;}
    TickType_t now=xTaskGetTickCount();
    if(challenge_attempted&&now-challenge_sent_at<pdMS_TO_TICKS(3000))return;
    challenge_attempted=true;challenge_sent_at=now;
    wr_receiver_cancel_challenge(&receiver);
    uint8_t challenge[16],wire[WR_SESSION_BYTES];esp_fill_random(challenge,sizeof challenge);
    if(!wr_receiver_challenge(&receiver,challenge,wire,sizeof wire)){
        if(esp_now_send(receiver.address,wire,sizeof wire)!=ESP_OK)wr_receiver_cancel_challenge(&receiver);
    }
    wipe(challenge,sizeof challenge);wipe(wire,sizeof wire);
}
static int digit(char c){return c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:c>='A'&&c<='F'?c-'A'+10:-1;}
static bool hex(const char *s,uint8_t *out,size_t n){for(size_t i=0;i<n;i++){int a=digit(s[2*i]),b=digit(s[2*i+1]);if(a<0||b<0)return false;out[i]=uint8_t(a*16+b);}return true;}
static bool pair_command(const char *s){
    // Fixed-width local USB provisioning; secrets are never echoed or persisted.
    if(std::strlen(s)!=160||s[12]!=' '||s[29]!=' '||s[94]!=' '||s[127]!=' ')return false;
    uint8_t address[6]={},session_bytes[8]={},key[32]={},lmk[16]={},pmk[16]={};
    bool ok=hex(s,address,6)&&hex(s+13,session_bytes,8)&&hex(s+30,key,32)&&hex(s+95,lmk,16)&&hex(s+128,pmk,16);
    uint64_t session=0;for(unsigned i=0;i<8;i++)session=(session<<8)|session_bytes[i];
    wr_receiver candidate={};ok=ok&&!wr_receiver_pair(&candidate,address,key,session);
    if(ok&&radio_ready&&!receiver.paired){
        esp_now_peer_info_t peer={};std::memcpy(peer.peer_addr,address,6);std::memcpy(peer.lmk,lmk,16);
        peer.channel=8;peer.ifidx=WIFI_IF_STA;peer.encrypt=true;
        ok=esp_now_set_pmk(pmk)==ESP_OK&&esp_now_add_peer(&peer)==ESP_OK;
        wipe(&peer,sizeof peer);
        if(ok){receiver=candidate;challenge_attempted=false;last_status=0;stale=false;command_serial=pending_command=0;xQueueReset(packets);}
    }else ok=false;
    wr_receiver_clear(&candidate);wipe(address,sizeof address);wipe(session_bytes,sizeof session_bytes);
    wipe(key,sizeof key);wipe(lmk,sizeof lmk);wipe(pmk,sizeof pmk);return ok;
}
static void control_key(unsigned key){
    if(!radio_ready||!receiver.paired||!receiver.have_status||stale||pending_command||command_serial==UINT32_MAX)return;
    uint32_t op;int32_t value=0;
    if(key==1)op=XW_OP_PREVIOUS;
    else if(key==2)op=XW_OP_NEXT;
    else if(key==3){op=XW_OP_STEP_VOLUME;value=1;}
    else if(key==4){op=XW_OP_STEP_VOLUME;value=-1;}
    else if(key==5){
        if(!(receiver.status.valid&1u))return;
        if(receiver.status.state==XW_PLAY_PLAYING)op=XW_OP_PAUSE;
        else if(receiver.status.state==XW_PLAY_PAUSED||receiver.status.state==XW_PLAY_STOPPED)op=XW_OP_PLAY;
        else return;
    }else return;
    if(!(receiver.status.commands&(1u<<op)))return;
    wr_control c={receiver.session,++command_serial,op,value};uint8_t wire[WR_CONTROL_BYTES];
    if(wr_control_encode(wire,sizeof wire,&c,receiver.key))return;
    esp_err_t result=esp_now_send(receiver.address,wire,sizeof wire);wipe(wire,sizeof wire);
    if(result!=ESP_OK){command_state="SEND REJECTED - NO RETRY";draw_status();return;}
    pending_command=c.request;command_started=xTaskGetTickCount();command_state="WAITING FOR PLAYER RECEIPT";draw_status();
}
static const gpio_num_t key_outputs[]={GPIO_NUM_8,GPIO_NUM_9,GPIO_NUM_11};
static const gpio_num_t key_inputs[]={GPIO_NUM_13,GPIO_NUM_15,GPIO_NUM_3,GPIO_NUM_4,GPIO_NUM_5,GPIO_NUM_6,GPIO_NUM_7};
static void keyboard_init(){
    for(auto pin:key_outputs){gpio_reset_pin(pin);gpio_set_direction(pin,GPIO_MODE_OUTPUT);gpio_set_level(pin,0);}
    for(auto pin:key_inputs){gpio_reset_pin(pin);gpio_set_direction(pin,GPIO_MODE_INPUT);gpio_set_pull_mode(pin,GPIO_PULLUP_ONLY);}
}
static void keyboard_step(){
    unsigned selected=0,count=0;
    for(unsigned row=0;row<8;row++){
        for(unsigned i=0;i<3;i++)gpio_set_level(key_outputs[i],(row>>i)&1u);
        esp_rom_delay_us(2);
        for(unsigned j=0;j<7;j++)if(!gpio_get_level(key_inputs[j])){
            count++;unsigned x=2*j+(row>3?0:1),y=3-(row&3);
            if(y==2&&x==2)selected=1;else if(y==2&&x==4)selected=2;
            else if(y==1&&x==2)selected=3;else if(y==2&&x==3)selected=4;
            else if(y==3&&x==13)selected=5;
        }
    }
    if(count!=1)selected=0;
    static unsigned candidate,stable;static TickType_t changed;
    TickType_t now=xTaskGetTickCount();
    if(selected!=candidate){candidate=selected;changed=now;}
    if(candidate!=stable&&now-changed>=pdMS_TO_TICKS(30)){stable=candidate;if(stable)control_key(stable);}
}

static void draw_idle() {
    if (!lcd_ready) return;
    display.fillScreen(0x0843);
    display.fillRect(0, 0, 240, 25, 0x1248);
    display.setFont(&lgfx::fonts::efontCN_12);
    display.setTextSize(1);
    display.setTextColor(0xffff, 0x1248);
    display.drawString("WALKMAN REMOTE", 8, 6);
    display.setTextColor(0xffe0, 0x0843);
    display.drawString("NO PLAYER SESSION", 8, 37);
    display.setTextColor(0xffff, 0x0843);
    display.drawString("Waiting for real X1060 data", 8, 59);
    display.setTextColor(0xad55, 0x0843);
    display.drawString("Controls disabled until linked", 8, 78);
    char line[64];
    std::snprintf(line, sizeof line, "ESP-NOW %s  CH8", radio_ready ? "IDLE" : "ERROR");
    display.drawString(line, 8, 101);
    display.setTextColor(0x7fef, 0x0843);
    display.drawString(esp_app_get_description()->version, 8, 118);
}

static void status() {
    std::printf("REMOTE_RX frames=%lu accepted=%lu source=%lu auth=%lu session=%lu sequence=%lu\n",
        (unsigned long)received_frames,(unsigned long)accepted_status,(unsigned long)wrong_source,
        (unsigned long)bad_auth,(unsigned long)bad_session,(unsigned long)old_sequence);
    std::printf("REMOTE_STATUS version=%s lcd=%u board=%u width=%ld height=%ld radio=%u tx_power_quarter_dbm=%d paired=%u player_session=%u mac=%02x%02x%02x%02x%02x%02x\n",
        esp_app_get_description()->version, lcd_ready, unsigned(display.getBoard()),
        long(display.width()), long(display.height()), radio_ready, int(tx_power),receiver.paired,receiver.have_status&&!stale,
        mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
}
static void draw_status(){
    if(!receiver.have_status){draw_idle();return;}
    if(!lcd_ready)return;
    display.fillScreen(0x0843);display.setTextColor(0xffff,0x0843);
    display.setClipRect(0,0,240,135);
    display.drawString(stale?"PLAYER LINK LOST":"WALKMAN REMOTE",8,4);
    const wr_status &s=receiver.status;
    const char *states[]={"UNKNOWN","STOPPED","PAUSED","PLAYING","BUFFERING"};
    display.drawString(stale?"Controls disabled":(s.valid&1?states[s.state]:"STATE UNAVAILABLE"),8,24);
    display.drawString(s.valid&4?s.title:"No track information",8,45);
    display.drawString(s.artist,8,65);display.drawString(s.album,8,83);
    char line[64];if(!stale&&(s.valid&32))std::snprintf(line,sizeof line,"VOL %ld / %ld",long(s.volume),long(s.maximum));
    else std::snprintf(line,sizeof line,"Waiting for fresh status");display.drawString(line,8,101);
    display.drawString(command_state,8,119);
    display.clearClipRect();
}

extern "C" void app_main() {
    usb_serial_jtag_driver_config_t console = {};
    console.tx_buffer_size = 4096;
    console.rx_buffer_size = 1024;
    ESP_ERROR_CHECK(usb_serial_jtag_driver_install(&console));
    lcd_ready = display.init();
    if (lcd_ready) {
        display.setRotation(1);
        display.setBrightness(96);
    }
    draw_idle();
    keyboard_init();

    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    wifi_init_config_t config = WIFI_INIT_CONFIG_DEFAULT();
    config.nvs_enable = 0;
    esp_err_t result = esp_wifi_init(&config);
    if (result == ESP_OK) result = esp_wifi_set_storage(WIFI_STORAGE_RAM);
    if (result == ESP_OK) result = esp_wifi_set_mode(WIFI_MODE_STA);
    if (result == ESP_OK) result = esp_wifi_start();
    if (result == ESP_OK) result = esp_wifi_set_ps(WIFI_PS_NONE);
    if (result == ESP_OK) result = esp_wifi_set_channel(8, WIFI_SECOND_CHAN_NONE);
    if (result == ESP_OK) result = esp_now_init();
    radio_ready = result == ESP_OK;
    packets=xQueueCreate(4,sizeof(packet));
    if(!packets)radio_ready=false;
    if(radio_ready&&esp_now_register_recv_cb(receive)!=ESP_OK)radio_ready=false;
    if (radio_ready) {
        // Pinned IDF documents 8 quarter-dBm as its minimum accepted TX limit.
        if (esp_wifi_set_max_tx_power(8) != ESP_OK) std::puts("REMOTE_TX_LIMIT_REJECTED");
        if (esp_wifi_get_max_tx_power(&tx_power) != ESP_OK) tx_power = -1;
        esp_wifi_get_mac(WIFI_IF_STA, mac);
    }
    // No automatic pairing/router connection. Reconnect only to the paired peer.
    draw_idle();
    status();
    for (;;) {
        uint8_t bytes[64];
        int count = usb_serial_jtag_read_bytes(bytes, sizeof bytes, pdMS_TO_TICKS(20));
        for (int i = 0; i < count; ++i) {
            char c = char(bytes[i]);
            if (c == '\r') continue;
            if (c == '\n') {
                command[used] = 0;
                if(discard_line)std::puts("REMOTE_COMMAND_REJECTED");
                else if (!std::strcmp(command, "status")) status();
                else if (!std::strcmp(command, "redraw")) { draw_status(); std::puts("REMOTE_REDRAW_DONE"); }
                else if (!std::strncmp(command,"pair ",5))std::puts(pair_command(command+5)?"REMOTE_PAIRED_RAM_ONLY":"REMOTE_PAIR_REJECTED");
                else if (!std::strcmp(command,"unpair")){
                    if(receiver.paired)esp_now_del_peer(receiver.address);
                    wr_receiver_clear(&receiver);challenge_attempted=false;if(packets)xQueueReset(packets);stale=false;pending_command=0;draw_idle();std::puts("REMOTE_UNPAIRED");
                }else std::puts("COMMANDS status | redraw | pair | unpair");
                wipe(command,sizeof command);discard_line=false;
                used = 0;
            } else if(!discard_line&&c>=32&&c<127&&used+1<sizeof command)command[used++]=c;
            else discard_line=true;
        }
        packet p;
        while(packets&&xQueueReceive(packets,&p,0)==pdTRUE){
            received_frames++;
            if(p.bytes==WR_SIGNED_STATUS_BYTES&&receiver.paired){
                wr_status decoded;
                if(std::memcmp(p.source,receiver.address,6))wrong_source++;
                else if(wr_status_verify(&decoded,p.data,p.bytes,receiver.key))bad_auth++;
                else if(decoded.session!=receiver.session)bad_session++;
                else if(decoded.sequence<=receiver.sequence)old_sequence++;
            }
            if(p.bytes==WR_SESSION_BYTES&&!std::memcmp(p.data,"WRP1",4)){
                int changed=wr_receiver_session_reply(&receiver,p.source,p.data,p.bytes);
                if(changed>0){
                    pending_command=0;command_serial=0;stale=true;
                    command_state="CONNECTED - WAITING FOR STATUS";
                    draw_status();
                }
            }else if(p.bytes==WR_CONTROL_BYTES&&receiver.paired&&!std::memcmp(p.source,receiver.address,6)){
                wr_control_receipt receipt;
                if(!wr_receipt_decode(&receipt,p.data,p.bytes,receiver.key)&&receipt.session==receiver.session&&pending_command&&receipt.request==pending_command){
                    pending_command=0;
                    command_state=receipt.result==XW_PLAYER_ACCEPTED?"ACCEPTED - WAIT FOR STATUS":receipt.result==XW_PLAYER_OK?"PLAYER COMMAND RETURNED OK":receipt.result==XW_PLAYER_UNCERTAIN?"UNCERTAIN - NOT REPEATED":"PLAYER REJECTED COMMAND";
                    draw_status();
                }
            }else if(!wr_receiver_accept(&receiver,p.source,p.data,p.bytes)){
                accepted_status++;
                last_status=xTaskGetTickCount();stale=false;draw_status();
            }
        }
        if(receiver.have_status&&!stale&&xTaskGetTickCount()-last_status>pdMS_TO_TICKS(5000)){stale=true;draw_status();}
        if(pending_command&&xTaskGetTickCount()-command_started>pdMS_TO_TICKS(3000)){pending_command=0;command_state="NO RECEIPT - NOT REPEATED";draw_status();}
        reconnect_step();
        keyboard_step();
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}
