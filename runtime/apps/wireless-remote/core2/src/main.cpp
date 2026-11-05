/* Core2 + Faces Gamepad3 development frontend; hardware qualification pending. */
#include <M5Unified.h>
#include <M5Faces.h>
#include "remote_version.h"
#include <cstdio>
#include <cstring>
#include "esp_app_desc.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_now.h"
#include "esp_wifi.h"
#include "esp_random.h"

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "../../receiver.h"
#include "../../session_wire.h"
#include "../../control.h"
#include "../../mode_wire.h"
#include "../../library_client.h"
#include "driver/gpio.h"
#include "esp_rom_sys.h"

static auto &display=M5.Display;
static M5Canvas canvas(&M5.Display);
static M5Faces_Gamepad3 pad;
static unsigned page;
static unsigned focus[3]={2,0,0};
static TickType_t mode_hint_until;
static bool pad_ready;
static uint8_t pad_previous=0xff;
static bool lcd_ready;
static bool radio_ready;
static int8_t tx_power;
static uint8_t mac[6];
static char command[192];
static size_t used;
static bool discard_line;
static wr_receiver receiver;
static wr_mode play_mode;
static bool have_mode;
static TickType_t mode_received_at;
struct packet { uint8_t source[6],data[WR_LIBRARY_REPLY_BYTES];unsigned bytes; };
static wr_library_client library;
static uint32_t library_parent_offset;
static QueueHandle_t packets;
static TickType_t last_status,challenge_sent_at;
static bool challenge_attempted;
static bool stale;
static uint32_t received_frames,accepted_status,wrong_source,bad_auth,bad_session,old_sequence;
static uint32_t command_serial,pending_command;
static TickType_t command_started;
static const char *command_state="D-PAD: TRACK/VOLUME  START: PLAY";
static void draw_status();
static uint64_t library_now(){return uint64_t(xTaskGetTickCount())*portTICK_PERIOD_MS;}
static void library_request(xw_media_view view,uint32_t offset,uint64_t revision,const char *container=nullptr){
 if(!receiver.paired||!receiver.have_status||stale||library.pending)return;
 xw_media_query query={};query.view=view;query.offset=offset;query.limit=1;query.expected_revision=revision;
 if(container){size_t n=std::strlen(container);if(n>=sizeof query.container.value)return;std::memcpy(query.container.value,container,n+1);}
 uint8_t wire[WR_LIBRARY_REQUEST_BYTES];
 if(wr_library_client_begin(&library,receiver.session,&query,library_now(),wire,sizeof wire,receiver.key))return;
 if(esp_now_send(receiver.address,wire,sizeof wire)!=ESP_OK){library.pending=0;library.have=0;library.result=XW_PLAYER_IO;}
 draw_status();
}
static void select_page(unsigned next){
 page=next;
 if(page==1&&!library.pending&&(!library.have||library.session!=receiver.session))library_request(XW_MEDIA_TRACKS,0,0);
 draw_status();
}
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
        if(ok){receiver=candidate;challenge_attempted=false;have_mode=false;play_mode={};wr_library_client_clear(&library);last_status=0;stale=false;command_serial=pending_command=0;xQueueReset(packets);}
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
static void confirm_focus(){
 if(page==0){const unsigned actions[]={4,1,5,2,3};control_key(actions[focus[0]]);}
 else if(page==1){
  unsigned f=focus[1];
  if(f<3){library_parent_offset=0;library_request(f==0?XW_MEDIA_TRACKS:f==1?XW_MEDIA_PLAYLISTS:XW_MEDIA_QUEUE,0,0);}
  else if(f==6)library_request(library.query.view,0,0,library.query.view==XW_MEDIA_PLAYLIST_TRACKS?library.query.container.value:nullptr);
  else if(library.have&&!library.pending){
   if(f==3&&library.reply.page.offset)library_request(library.query.view,library.reply.page.offset-1,library.reply.page.revision,library.query.view==XW_MEDIA_PLAYLIST_TRACKS?library.query.container.value:nullptr);
   else if(f==5&&library.reply.page.count&&library.reply.page.next_offset<library.reply.page.total)library_request(library.query.view,library.reply.page.next_offset,library.reply.page.revision,library.query.view==XW_MEDIA_PLAYLIST_TRACKS?library.query.container.value:nullptr);
   else if(f==4&&library.query.view==XW_MEDIA_PLAYLISTS&&library.reply.page.count){library_parent_offset=library.reply.page.offset;library_request(XW_MEDIA_PLAYLIST_TRACKS,0,0,library.reply.item.id.value);}
   else if(f==4)page=0;
  }
 }
 else mode_hint_until=xTaskGetTickCount()+pdMS_TO_TICKS(2000);
 draw_status();
}
static void navigate(int direction){
 const unsigned count=page==1?7:5;focus[page]=unsigned(int(focus[page])+direction+int(count))%count;draw_status();
}
static void keyboard_init(){
 pad_ready=pad.begin(&M5.In_I2C,M5FACES_BOTTOM3_ADDR,100000)==M5FACES_OK;
 pad_previous=0xff;
}
static void keyboard_step(){
 M5.update();
 if(M5.Touch.getCount()){
  const auto touch=M5.Touch.getDetail();
  if(touch.wasPressed()){
   if(touch.y>=215){select_page(touch.x<107?0:touch.x<214?1:2);}
   else if(page==1&&touch.y>=36&&touch.y<63){focus[1]=touch.x<112?0:touch.x<208?1:2;confirm_focus();}
   else if(page==1&&touch.y>=174&&touch.y<202){focus[1]=3+unsigned(touch.x<16?0:touch.x>303?287:touch.x-16)/72;confirm_focus();}
   else if(page==2&&touch.y>=57&&touch.y<197){focus[2]=unsigned(touch.y-57)/28;confirm_focus();}
   else if(!page&&touch.y>=156&&touch.y<208){
    focus[0]=touch.x<54?0:touch.x>266?4:touch.x<132?1:touch.x>188?3:2;confirm_focus();
   }
  }
 }
 if(!pad_ready)return;pad.update();uint8_t raw=pad.getState().raw;
 uint8_t pressed=uint8_t(~raw);
 if((pressed&3)==3||(pressed&12)==12){pad_previous=0xff;return;}
 uint8_t edges=pad_previous&pressed;pad_previous=raw;
 if(edges&128){page=0;focus[0]=2;draw_status();return;}
 if(edges&32){if(page==1&&library.query.view==XW_MEDIA_PLAYLIST_TRACKS&&!library.pending)library_request(XW_MEDIA_PLAYLISTS,library_parent_offset,0);else select_page(0);return;}
 if(edges&64){select_page((page+1)%3);return;}
 if(edges&16){confirm_focus();return;}
 if(edges&(1|4))navigate(-1);else if(edges&(2|8))navigate(1);
}

static void draw_idle(){draw_status();}

static void status() {
    std::printf("REMOTE_RX frames=%lu accepted=%lu source=%lu auth=%lu session=%lu sequence=%lu\n",
        (unsigned long)received_frames,(unsigned long)accepted_status,(unsigned long)wrong_source,
        (unsigned long)bad_auth,(unsigned long)bad_session,(unsigned long)old_sequence);
    std::printf("REMOTE_STATUS version=%s lcd=%u board=%u width=%ld height=%ld radio=%u tx_power_quarter_dbm=%d paired=%u player_session=%u mac=%02x%02x%02x%02x%02x%02x\n",
        XW_REMOTE_VERSION, lcd_ready, unsigned(display.getBoard()),
        long(display.width()), long(display.height()), radio_ready, int(tx_power),receiver.paired,receiver.have_status&&!stale,
        mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
}
static void clipped(const char *text,int x,int y,int width,uint16_t color){
 canvas.setClipRect(x,y,width,20);canvas.setTextColor(color);canvas.drawString(text,x,y);canvas.clearClipRect();
}
static void draw_status(){
 if(!lcd_ready)return;
 constexpr uint16_t bg=0x0863,card=0x10e5,muted=0x94d4,white=0xef9d,mint=0x7f53;
 auto &g=canvas;g.fillScreen(bg);g.setFont(&lgfx::fonts::efontCN_12);g.setTextSize(1);
 const bool online=receiver.have_status&&!stale;
 g.setTextColor(white);g.drawString("WALKMAN",16,10);g.setTextColor(muted);g.drawString("REMOTE",84,10);
 g.fillCircle(264,16,3,online?mint:0xd4c9);g.setTextColor(online?mint:muted);g.drawString(online?"LIVE":"IDLE",274,10);
 g.drawFastHLine(16,30,288,0x2127);
 const char *mode_names[]={"Normal","Repeat","Shuffle","Shuffle & Repeat","Repeat 1 Song"};
 const bool mode_known=online&&have_mode&&play_mode.valid&&play_mode.session==receiver.session&&xTaskGetTickCount()-mode_received_at<pdMS_TO_TICKS(15000);
 if(page==2){
  g.setTextColor(white);g.drawString("PLAY MODE",18,35);
  for(unsigned i=0;i<5;i++){
   int y=57+28*i;bool selected=mode_known&&play_mode.index==i;
   g.fillRoundRect(16,y,288,25,7,selected?0x1a69:card);
   if(focus[2]==i)g.drawRoundRect(16,y,288,25,7,0xf5c9);
   g.drawCircle(30,y+12,4,selected?mint:muted);if(selected)g.fillCircle(30,y+12,2,mint);
   g.setTextColor(selected?mint:white);g.drawString(mode_names[i],44,y+6);
  }
  g.setTextColor(muted);g.drawString(xTaskGetTickCount()<mode_hint_until?"Change mode on your Walkman":mode_known?"A: details   B: back":"Waiting for the stock play mode",18,202);
 }else if(page==1){
  const char *views[]={"Tracks","Playlists","Queue"};
  for(unsigned i=0;i<3;i++){
   int x=16+96*i;g.fillRoundRect(x,36,92,26,6,card);if(focus[1]==i)g.drawRoundRect(x,36,92,26,6,0xf5c9);
   bool selected=i==0?library.query.view==XW_MEDIA_TRACKS:i==1?(library.query.view==XW_MEDIA_PLAYLISTS||library.query.view==XW_MEDIA_PLAYLIST_TRACKS):library.query.view==XW_MEDIA_QUEUE;
   g.setTextColor(selected?mint:muted);g.drawString(views[i],x+8,43);
  }
  g.fillRoundRect(16,69,288,98,9,card);
  const bool available=online&&library.have&&library.session==receiver.session;
  if(library.pending){g.setTextColor(muted);g.drawString("Reading from Walkman...",28,89);}
  else if(available&&library.reply.page.count){
   clipped(library.reply.item.title[0]?library.reply.item.title:"Untitled",28,78,264,white);
   clipped(library.reply.item.artist,28,100,264,muted);clipped(library.reply.item.album,28,120,264,muted);
   char position[56];if(library.reply.page.total==XW_MEDIA_TOTAL_UNKNOWN)std::snprintf(position,sizeof position,"Item %lu",(unsigned long)library.reply.page.offset+1);else std::snprintf(position,sizeof position,"Item %lu / %lu",(unsigned long)library.reply.page.offset+1,(unsigned long)library.reply.page.total);
   g.setTextColor(mint);g.drawString(position,28,145);
  }else{
   const char *message=!online?"Connect your Walkman":available?"No items":library.result==XW_PLAYER_UNSUPPORTED?"View not supported by player":library.result==XW_PLAYER_STALE?"Library changed - choose Reload":library.result?"No result - choose Reload":"Choose a library view";
   g.setTextColor(muted);g.drawString(message,28,95);
  }
  const char *actions[]={"Prev",library.query.view==XW_MEDIA_PLAYLISTS?"Open":"Playing","Next","Reload"};
  for(unsigned i=0;i<4;i++){int x=16+72*i;g.fillRoundRect(x,174,68,27,6,card);if(focus[1]==i+3)g.drawRoundRect(x,174,68,27,6,0xf5c9);g.setTextColor(white);g.drawString(actions[i],x+8,182);}
  g.setTextColor(muted);g.drawString("Read only   A: select   B: back",18,203);
 }else{
  g.fillRoundRect(16,43,102,102,12,0x1a08);
  for(int y=51;y<140;y+=8)g.drawFastHLine(23,y,88,0x2249);
  g.fillCircle(67,94,35,0x0863);g.drawCircle(67,94,29,0x318a);g.drawCircle(67,94,23,0x2127);
  g.fillCircle(67,94,12,mint);g.fillCircle(67,94,3,0x0863);
  const wr_status &v=receiver.status;
  g.setTextColor(mint);g.drawString(online?"NOW PLAYING":"CONNECT YOUR WALKMAN",134,43);
  clipped(online&&(v.valid&4)&&v.title[0]?v.title:"No track selected",134,65,171,white);
  clipped(online&&(v.valid&4)?v.artist:"Waiting for player information",134,85,171,muted);
  clipped(online&&(v.valid&4)?v.album:"",134,102,171,muted);
  char volume[40];if(online&&(v.valid&32))std::snprintf(volume,sizeof volume,"VOL %ld / %ld",long(v.volume),long(v.maximum));else std::snprintf(volume,sizeof volume,"VOL --");
  g.setTextColor(white);g.drawString(volume,134,123);
  unsigned bar=0;if(online&&(v.valid&32)&&v.maximum>v.minimum)bar=unsigned((v.volume-v.minimum)*78/(v.maximum-v.minimum));
  g.fillRoundRect(226,128,78,4,2,0x2948);if(bar)g.fillRoundRect(226,128,bar,4,2,mint);
  g.setTextColor(muted);g.drawString(mode_known?mode_names[play_mode.index]:"Mode unavailable",18,148);
  for(int x: {34,104,160,216,286})g.fillCircle(x,184,x==160?22:16,x==160?mint:card);
  const int positions[]={34,104,160,216,286};g.drawCircle(positions[focus[0]],184,focus[0]==2?25:19,0xf5c9);
  g.setTextColor(white);g.drawString("-",31,178);g.drawString("+",283,178);
  g.fillTriangle(111,176,111,192,99,184,white);g.drawFastVLine(96,176,16,white);
  g.fillTriangle(209,176,209,192,221,184,white);g.drawFastVLine(224,176,16,white);
  if(online&&(v.valid&1)&&v.state==XW_PLAY_PLAYING){g.fillRect(153,176,4,16,bg);g.fillRect(163,176,4,16,bg);}
  else g.fillTriangle(155,175,155,193,169,184,bg);
 }
 g.fillRect(0,215,320,25,card);const char *tabs[]={"Playing","Library","Modes"};
 for(unsigned i=0;i<3;i++){g.setTextColor(page==i?mint:muted);g.drawString(tabs[i],28+107*i,222);if(page==i)g.fillRoundRect(26+107*i,215,46,2,1,mint);}
 canvas.pushSprite(0,0);
}

void setup() {
 Serial.begin(115200);
 auto board=M5.config();board.internal_mic=false;board.internal_spk=false;board.external_spk=false;
 M5.begin(board);display.setRotation(1);display.setBrightness(96);canvas.setPsram(true);canvas.setColorDepth(16);lcd_ready=canvas.createSprite(320,240)!=nullptr;
    draw_idle();
    keyboard_init();

    ESP_ERROR_CHECK(esp_netif_init());
    esp_err_t loop_result=esp_event_loop_create_default();
    if(loop_result!=ESP_OK&&loop_result!=ESP_ERR_INVALID_STATE)ESP_ERROR_CHECK(loop_result);
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
        int count=0;while(Serial.available()&&count<int(sizeof bytes))bytes[count++]=uint8_t(Serial.read());
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
                    wr_receiver_clear(&receiver);wr_library_client_clear(&library);challenge_attempted=false;have_mode=false;if(packets)xQueueReset(packets);stale=false;pending_command=0;draw_idle();std::puts("REMOTE_UNPAIRED");
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
                    have_mode=false;play_mode={};wr_library_client_clear(&library);
                    draw_status();
                }
            }else if(p.bytes==WR_LIBRARY_REPLY_BYTES&&!std::memcmp(p.data,"WLBR",4)&&receiver.paired&&!std::memcmp(p.source,receiver.address,6)){
                if(!wr_library_client_accept(&library,p.data,p.bytes,receiver.key)&&page==1)draw_status();
            }else if(p.bytes==WR_MODE_BYTES&&!std::memcmp(p.data,"WRM1",4)&&receiver.paired&&!std::memcmp(p.source,receiver.address,6)){
                wr_mode received;
                if(!wr_mode_decode(&received,p.data,p.bytes,receiver.key)&&received.session==receiver.session&&(!have_mode||received.sequence>play_mode.sequence)){
                    play_mode=received;have_mode=true;mode_received_at=xTaskGetTickCount();draw_status();
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
        if(wr_library_client_tick(&library,library_now())&&page==1)draw_status();
        reconnect_step();
        keyboard_step();
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}

void loop(){delay(10);}
