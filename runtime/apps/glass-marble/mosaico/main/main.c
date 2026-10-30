#include "marble.h"
#include "bsp/esp_mosaico.h"
#include "esp_wifi.h"
#include "esp_now.h"
#include "esp_random.h"
#include "esp_timer.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "nvs_flash.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include <math.h>
#include <string.h>
static struct gm_world world;
static uint16_t *surface;
static lv_obj_t *image,*status;
static lv_image_dsc_t picture;
static volatile unsigned calibrate=1;
static QueueHandle_t geometry_queue;
static lv_obj_t *settings,*fields[6],*error_label;
static struct gm_layout displayed_layout;
static const uint8_t broadcast[6]={255,255,255,255,255,255};
/* LVGL timer callback and simulation task communicate only through this flag. */
static void tapped(lv_event_t *event){(void)event;calibrate=1;}
static void adjust(lv_event_t *event){
 intptr_t value=(intptr_t)lv_event_get_user_data(event);unsigned index=(unsigned)(value/2);
 if(value&1)lv_spinbox_increment(fields[index]);else lv_spinbox_decrement(fields[index]);
}
static void apply(lv_event_t *event){
 (void)event;struct gm_layout l;
 l.mw=lv_spinbox_get_value(fields[0])/100.0f;l.mh=lv_spinbox_get_value(fields[1])/100.0f;
 l.xw=lv_spinbox_get_value(fields[2])/100.0f;l.xh=lv_spinbox_get_value(fields[3])/100.0f;
 l.gap=lv_spinbox_get_value(fields[4])/100.0f;l.offset=lv_spinbox_get_value(fields[5])/100.0f;
 if(!gm_layout_valid(&l)){lv_label_set_text(error_label,"Invalid size / no shared opening");return;}
 xQueueOverwrite(geometry_queue,&l);lv_obj_delete(settings);settings=0;
}
static void setup(lv_event_t *event){
 (void)event;if(settings)return;
 settings=lv_obj_create(lv_screen_active());lv_obj_set_size(settings,480,480);lv_obj_center(settings);lv_obj_set_style_bg_color(settings,lv_color_hex(0x142033),0);
 static const char *names[]={"Mosaico width","Mosaico height","X1060 width","X1060 height","Glass edge gap","X1060 top offset"};
 float values[]={displayed_layout.mw,displayed_layout.mh,displayed_layout.xw,displayed_layout.xh,displayed_layout.gap,displayed_layout.offset};
 for(unsigned i=0;i<6;i++){
  int y=12+(int)i*57;lv_obj_t *label=lv_label_create(settings);lv_label_set_text(label,names[i]);lv_obj_set_pos(label,4,y+12);
  fields[i]=lv_spinbox_create(settings);lv_obj_set_pos(fields[i],202,y);lv_obj_set_size(fields[i],118,42);lv_spinbox_set_digit_format(fields[i],5,3);lv_spinbox_set_range(fields[i],i==5?-15000:0,15000);lv_spinbox_set_step(fields[i],10);lv_spinbox_set_value(fields[i],(int32_t)lroundf(values[i]*100));
  for(unsigned k=0;k<2;k++){lv_obj_t *button=lv_button_create(settings);lv_obj_set_size(button,48,42);lv_obj_set_pos(button,328+(int)k*54,y);lv_obj_add_event_cb(button,adjust,LV_EVENT_CLICKED,(void *)(intptr_t)(i*2+k));lv_obj_t *text=lv_label_create(button);lv_label_set_text(text,k?"+":"-");lv_obj_center(text);}
 }
 error_label=lv_label_create(settings);lv_label_set_text(error_label,"Units: mm. X1060 is right of Mosaico.");lv_obj_set_pos(error_label,4,362);
 lv_obj_t *button=lv_button_create(settings);lv_obj_set_size(button,220,48);lv_obj_set_pos(button,105,397);lv_obj_add_event_cb(button,apply,LV_EVENT_CLICKED,0);lv_obj_t *text=lv_label_create(button);lv_label_set_text(text,"APPLY / RESET");lv_obj_center(text);
}
static void radio_start(void){
 ESP_ERROR_CHECK(nvs_flash_init()); /* never erase existing board NVS on failure */
 ESP_ERROR_CHECK(esp_netif_init());ESP_ERROR_CHECK(esp_event_loop_create_default());
 wifi_init_config_t cfg=WIFI_INIT_CONFIG_DEFAULT();ESP_ERROR_CHECK(esp_wifi_init(&cfg));
 ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_RAM));ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
 ESP_ERROR_CHECK(esp_wifi_start());ESP_ERROR_CHECK(esp_wifi_set_ps(WIFI_PS_NONE));ESP_ERROR_CHECK(esp_wifi_set_channel(8,WIFI_SECOND_CHAN_NONE));
 ESP_ERROR_CHECK(esp_now_init());esp_now_peer_info_t peer={0};memcpy(peer.peer_addr,broadcast,6);peer.channel=8;peer.ifidx=WIFI_IF_STA;ESP_ERROR_CHECK(esp_now_add_peer(&peer));
}
void app_main(void){
 bsp_board_variant_t variant;ESP_ERROR_CHECK(bsp_board_variant_get(&variant));ESP_ERROR_CHECK(bsp_power_init());
 struct gm_layout layout={CONFIG_GM_MOSAICO_MM/100.0f,CONFIG_GM_MOSAICO_MM/100.0f,CONFIG_GM_X_WIDTH_MM/100.0f,CONFIG_GM_X_HEIGHT_MM/100.0f,CONFIG_GM_GAP_MM/100.0f,CONFIG_GM_OFFSET_MM/100.0f};
 if(!gm_layout_valid(&layout)||!CONFIG_GM_IMU_X_SIGN||!CONFIG_GM_IMU_Y_SIGN){ESP_LOGE("marble","Invalid geometry or IMU signs");return;}
 geometry_queue=xQueueCreate(1,sizeof layout);if(!geometry_queue)return;
 displayed_layout=layout;gm_init(&world,&layout,esp_random());ESP_ERROR_CHECK(bsp_imu_init());bsp_imu_config_t imu=BSP_IMU_CONFIG_DEFAULT();ESP_ERROR_CHECK(bsp_imu_start(&imu));
 if(!bsp_display_start())return;
 surface=heap_caps_malloc(480*480*2,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);if(!surface)return;
 picture.header.magic=LV_IMAGE_HEADER_MAGIC;picture.header.cf=LV_COLOR_FORMAT_RGB565;picture.header.w=480;picture.header.h=480;picture.header.stride=960;picture.data_size=480*480*2;picture.data=(const uint8_t *)surface;
 if(!bsp_display_lock(-1))return;
 image=lv_image_create(lv_screen_active());lv_image_set_src(image,&picture);lv_obj_add_flag(image,LV_OBJ_FLAG_CLICKABLE);lv_obj_add_event_cb(image,tapped,LV_EVENT_CLICKED,0);
 status=lv_label_create(lv_screen_active());lv_obj_set_style_text_color(status,lv_color_white(),0);lv_obj_align(status,LV_ALIGN_TOP_MID,0,8);lv_label_set_text(status,"Hold level - tap to zero/reset");
 lv_obj_t *gear=lv_button_create(lv_screen_active());lv_obj_set_size(gear,90,36);lv_obj_align(gear,LV_ALIGN_BOTTOM_LEFT,6,-6);lv_obj_add_event_cb(gear,setup,LV_EVENT_CLICKED,0);lv_obj_t *text=lv_label_create(gear);lv_label_set_text(text,"SIZES");lv_obj_center(text);bsp_display_unlock();
 radio_start();float zero_x=0,zero_y=0,gx=0,gy=0;unsigned samples=0,send_failures=0,frames=0;uint8_t packet[GM_PACKET];
 int64_t last=esp_timer_get_time(),sent=0,painted=0;TickType_t tick=xTaskGetTickCount();
 for(;;){
  int64_t now=esp_timer_get_time();float dt=(now-last)/1000000.0f;last=now;float ax,ay,az;
  esp_err_t result=bsp_imu_get_accel(&ax,&ay,&az);if(result!=ESP_OK){ESP_LOGE("marble","IMU read failed; physics paused");vTaskDelay(pdMS_TO_TICKS(100));continue;}
  if(xQueueReceive(geometry_queue,&layout,0)==pdTRUE)calibrate=1;
  if(calibrate){calibrate=0;samples=0;zero_x=zero_y=0;gx=gy=0;gm_init(&world,&layout,world.session+1);}
  if(samples<50){zero_x+=ax;zero_y+=ay;samples++;if(samples==50){zero_x/=50;zero_y/=50;}}
  else{
   float x=(ax-zero_x)*CONFIG_GM_IMU_X_SIGN,y=(ay-zero_y)*CONFIG_GM_IMU_Y_SIGN;
   for(int k=0;k<CONFIG_GM_IMU_ROTATION;k++){float t=x;x=-y;y=t;}
   gx+=.18f*(x-gx);gy+=.18f*(y-gy);gm_step(&world,gx,gy,dt);
  }
  if(now-sent>=50000){world.sequence++;if(gm_encode(&world,packet,sizeof packet)>0&&esp_now_send(broadcast,packet,sizeof packet)!=ESP_OK)send_failures++;sent=now;}
  if(now-painted>=33333&&bsp_display_lock(100)){
   displayed_layout=layout;struct gm_view view={0,0,layout.mw,layout.mh,480,480};gm_render(surface,&view,&world,0);lv_obj_invalidate(image);
   if((frames++%30)==0)lv_label_set_text_fmt(status,"%s  TX queue failures: %u",samples<50?"Hold level...":"Tap: zero / reset",send_failures);
   bsp_display_unlock();painted=now;
  }
  vTaskDelayUntil(&tick,pdMS_TO_TICKS(10));
 }
}
