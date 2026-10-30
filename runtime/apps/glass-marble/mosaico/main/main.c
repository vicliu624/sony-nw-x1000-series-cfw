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
#include "freertos/semphr.h"
#include <math.h>
#include <string.h>
#include <stdatomic.h>
static struct gm_world world;
static uint8_t packet[GM_PACKET];
static uint16_t *surface,*small;
static SemaphoreHandle_t scene_lock;
static struct gm_world render_world;
static atomic_uint sensor_samples,radio_errors,render_us,simulation_us,draw_rate,tx_rate;
static atomic_int flip_x=1,flip_y=1,input_rotation=CONFIG_GM_IMU_ROTATION,show_perf;
static atomic_uint panel_rotation=3,rotation_request=4;
static float down_x=-1,down_y=0;
static lv_obj_t *image,*status;
static lv_image_dsc_t picture;
static atomic_uint calibrate=1;
static QueueHandle_t geometry_queue;
static lv_obj_t *settings,*fields[6],*error_label;
static struct gm_layout displayed_layout;
static const uint8_t broadcast[6]={255,255,255,255,255,255};
/* LVGL timer callback and simulation task communicate only through this flag. */
static void tapped(lv_event_t *event){(void)event;atomic_store(&calibrate,1);}
static void flip_axis(lv_event_t *event){
 atomic_int *value=(intptr_t)lv_event_get_user_data(event)?&flip_y:&flip_x;atomic_store(value,-atomic_load(value));
}
static void rotate_input(lv_event_t *event){(void)event;atomic_store(&input_rotation,(atomic_load(&input_rotation)+1)&3);}
static void rotate_panel(lv_event_t *event){(void)event;unsigned next=(atomic_load(&panel_rotation)+1)&3;atomic_store(&panel_rotation,next);atomic_store(&rotation_request,next);}
static void toggle_perf(lv_event_t *event){(void)event;atomic_store(&show_perf,!atomic_load(&show_perf));}
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
  int y=12+(int)i*52;lv_obj_t *label=lv_label_create(settings);lv_label_set_text(label,names[i]);lv_obj_set_pos(label,4,y+12);
  fields[i]=lv_spinbox_create(settings);lv_obj_set_pos(fields[i],202,y);lv_obj_set_size(fields[i],118,42);lv_spinbox_set_digit_format(fields[i],5,3);lv_spinbox_set_range(fields[i],i==5?-15000:0,15000);lv_spinbox_set_step(fields[i],10);lv_spinbox_set_value(fields[i],(int32_t)lroundf(values[i]*100));
  for(unsigned k=0;k<2;k++){lv_obj_t *button=lv_button_create(settings);lv_obj_set_size(button,48,42);lv_obj_set_pos(button,328+(int)k*54,y);lv_obj_add_event_cb(button,adjust,LV_EVENT_CLICKED,(void *)(intptr_t)(i*2+k));lv_obj_t *text=lv_label_create(button);lv_label_set_text(text,k?"+":"-");lv_obj_center(text);}
 }
 error_label=lv_label_create(settings);lv_label_set_text(error_label,"mm | reset while holding upright");lv_obj_set_pos(error_label,4,325);
 static const char *motion[]={"FLIP X","FLIP Y","INPUT 90"};
 for(unsigned i=0;i<3;i++){
  lv_obj_t *button=lv_button_create(settings);lv_obj_set_size(button,132,34);lv_obj_set_pos(button,4+(int)i*142,352);
  lv_obj_add_event_cb(button,i<2?flip_axis:rotate_input,LV_EVENT_CLICKED,(void *)(intptr_t)i);lv_obj_t *text=lv_label_create(button);lv_label_set_text(text,motion[i]);lv_obj_center(text);
 }
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
static void render_task(void *unused){
 (void)unused;TickType_t tick=xTaskGetTickCount();unsigned frames=0;int64_t window=esp_timer_get_time();
 for(;;){
  if(xSemaphoreTake(scene_lock,portMAX_DELAY)!=pdTRUE)continue;
  render_world=world;xSemaphoreGive(scene_lock);
  int64_t began=esp_timer_get_time();
  struct gm_view view={0,0,render_world.layout.mw,render_world.layout.mh,240,240};
  gm_render(small,&view,&render_world,0);
  if(bsp_display_lock(20)){
   displayed_layout=render_world.layout;
   (void)gm_scale2x(surface,480,480,small,240*240);lv_obj_invalidate(image);
   unsigned samples=atomic_load(&sensor_samples);
   if(samples<50)lv_label_set_text(status,"Hold upright as mounted...");
   else if(atomic_load(&show_perf))lv_label_set_text_fmt(status,"Draw %u/s | sim %ums | draw %ums | TX %u/s",atomic_load(&draw_rate),atomic_load(&simulation_us)/1000,atomic_load(&render_us)/1000,atomic_load(&tx_rate));
   else lv_label_set_text(status,atomic_load(&radio_errors)?"Radio busy - retrying":"Tilt gently - tap to reset");
   frames++;
   bsp_display_unlock();
  }
  atomic_store(&render_us,(unsigned)(esp_timer_get_time()-began));
  int64_t now=esp_timer_get_time();if(now-window>=1000000){atomic_store(&draw_rate,(unsigned)((int64_t)frames*1000000/(now-window)));frames=0;window=now;}
  if(xTaskDelayUntil(&tick,pdMS_TO_TICKS(33))==pdFALSE){vTaskDelay(1);tick=xTaskGetTickCount();}
 }
}
void app_main(void){
 bsp_board_variant_t variant;ESP_ERROR_CHECK(bsp_board_variant_get(&variant));ESP_ERROR_CHECK(bsp_power_init());
 struct gm_layout layout={CONFIG_GM_MOSAICO_MM/100.0f,CONFIG_GM_MOSAICO_MM/100.0f,CONFIG_GM_X_WIDTH_MM/100.0f,CONFIG_GM_X_HEIGHT_MM/100.0f,CONFIG_GM_GAP_MM/100.0f,CONFIG_GM_OFFSET_MM/100.0f};
 if(!gm_layout_valid(&layout)||!CONFIG_GM_IMU_X_SIGN||!CONFIG_GM_IMU_Y_SIGN){ESP_LOGE("marble","Invalid geometry or IMU signs");return;}
 geometry_queue=xQueueCreate(1,sizeof layout);scene_lock=xSemaphoreCreateMutex();if(!geometry_queue||!scene_lock)return;
 displayed_layout=layout;gm_init(&world,&layout,esp_random());ESP_ERROR_CHECK(bsp_imu_init());bsp_imu_config_t imu=BSP_IMU_CONFIG_DEFAULT();ESP_ERROR_CHECK(bsp_imu_start(&imu));
 /* On the formal unit, camera-up/USB-left requires 270 degrees. Verified from
  * the user's physical 0-degree and 90-degree panel observations. */
 bsp_display_config_t display_config=BSP_DISPLAY_DEFAULT_CONFIG();display_config.rotation=BSP_DISPLAY_ROTATE_270;
 if(!bsp_display_start_with_config(&display_config))return;
 surface=heap_caps_calloc(480*480,2,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);small=heap_caps_calloc(240*240,2,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);if(!surface||!small)return;
 picture.header.magic=LV_IMAGE_HEADER_MAGIC;picture.header.cf=LV_COLOR_FORMAT_RGB565;picture.header.w=480;picture.header.h=480;picture.header.stride=960;picture.data_size=480*480*2;picture.data=(const uint8_t *)surface;
 if(!bsp_display_lock(-1))return;
 image=lv_image_create(lv_screen_active());lv_image_set_src(image,&picture);lv_obj_add_flag(image,LV_OBJ_FLAG_CLICKABLE);lv_obj_add_event_cb(image,tapped,LV_EVENT_CLICKED,0);
 status=lv_label_create(lv_screen_active());lv_obj_set_style_text_color(status,lv_color_white(),0);lv_obj_set_style_bg_color(status,lv_color_hex(0x142638),0);lv_obj_set_style_bg_opa(status,180,0);lv_obj_set_style_pad_all(status,4,0);lv_obj_align(status,LV_ALIGN_TOP_MID,0,8);lv_label_set_text(status,"Hold upright as mounted...");lv_obj_add_flag(status,LV_OBJ_FLAG_CLICKABLE);lv_obj_add_event_cb(status,toggle_perf,LV_EVENT_CLICKED,0);
 lv_obj_t *gear=lv_button_create(lv_screen_active());lv_obj_set_size(gear,90,36);lv_obj_align(gear,LV_ALIGN_BOTTOM_LEFT,6,-6);lv_obj_add_event_cb(gear,setup,LV_EVENT_CLICKED,0);lv_obj_t *text=lv_label_create(gear);lv_label_set_text(text,"SETUP");lv_obj_center(text);
 lv_obj_t *rotate=lv_button_create(lv_screen_active());lv_obj_set_size(rotate,96,36);lv_obj_align(rotate,LV_ALIGN_BOTTOM_RIGHT,-6,-6);lv_obj_add_event_cb(rotate,rotate_panel,LV_EVENT_CLICKED,0);lv_obj_t *rotate_text=lv_label_create(rotate);lv_label_set_text(rotate_text,"ROTATE");lv_obj_center(rotate_text);bsp_display_unlock();
 radio_start();
 if(xTaskCreatePinnedToCore(render_task,"aquarium_draw",8192,0,2,0,1)!=pdPASS){ESP_LOGE("marble","Renderer task unavailable");return;}
 float average_x=0,average_y=0,gx=0,gy=1;unsigned samples=0,tx_count=0;
 int64_t last=esp_timer_get_time(),sent=0,logged=last;TickType_t tick=xTaskGetTickCount();
 for(;;){
  unsigned requested=atomic_exchange(&rotation_request,4);
  if(requested<4){static const bsp_display_rotation_t rotations[]={BSP_DISPLAY_ROTATE_0,BSP_DISPLAY_ROTATE_90,BSP_DISPLAY_ROTATE_180,BSP_DISPLAY_ROTATE_270};ESP_ERROR_CHECK(bsp_display_set_rotation(rotations[requested]));last=esp_timer_get_time();tick=xTaskGetTickCount();}
  int64_t now=esp_timer_get_time();float dt=(now-last)/1000000.0f;last=now;float ax,ay,az;
  esp_err_t result=bsp_imu_get_accel(&ax,&ay,&az);
  if(result!=ESP_OK){ESP_LOGE("marble","IMU read failed; physics paused");vTaskDelay(pdMS_TO_TICKS(100));continue;}
  if(xQueueReceive(geometry_queue,&layout,0)==pdTRUE)atomic_store(&calibrate,1);
  xSemaphoreTake(scene_lock,portMAX_DELAY);
  if(atomic_exchange(&calibrate,0)){samples=0;average_x=average_y=0;gx=0;gy=1;gm_init(&world,&layout,world.session+1);}
  if(samples<50){
   average_x+=ax;average_y+=ay;samples++;
   if(samples==50){float x=average_x/50,y=average_y/50,length=sqrtf(x*x+y*y);if(length>.45f){down_x=x/length;down_y=y/length;}else{samples=0;average_x=average_y=0;}}
   gm_step(&world,0,1,dt);
  }else{
   /* Specific-force calibration establishes the physical downward screen axis,
    * rather than subtracting the complete gravity vector as a sensor bias. */
   float x=-down_y*ax+down_x*ay,y=down_x*ax+down_y*ay,mx,my;
   gm_map_tilt(x*CONFIG_GM_IMU_X_SIGN,y*CONFIG_GM_IMU_Y_SIGN,(unsigned)atomic_load(&input_rotation),atomic_load(&flip_x),atomic_load(&flip_y),&mx,&my);
   float alpha=dt/(.20f+dt);gx+=(mx-gx)*alpha;gy+=(my-gy)*alpha;
   int64_t began=esp_timer_get_time();gm_step(&world,gx,gy,dt);atomic_store(&simulation_us,(unsigned)(esp_timer_get_time()-began));
  }
  atomic_store(&sensor_samples,samples);int transmit=now-sent>=50000;
  if(transmit){world.sequence++;if(gm_encode(&world,packet,sizeof packet)<0)transmit=0;sent=now;}
  xSemaphoreGive(scene_lock);
  if(transmit){esp_err_t send=esp_now_send(broadcast,packet,sizeof packet);atomic_store(&radio_errors,send!=ESP_OK);if(send==ESP_OK)tx_count++;}
  if(now-logged>=1000000){atomic_store(&tx_rate,tx_count);tx_count=0;logged=now;}
  if(xTaskDelayUntil(&tick,pdMS_TO_TICKS(10))==pdFALSE){vTaskDelay(1);tick=xTaskGetTickCount();}
 }
}
