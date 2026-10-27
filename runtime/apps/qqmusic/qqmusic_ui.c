#include "qqmusic_font.h"
#include "qqmusic_asset.h"
#include "qqmusic_ui.h"
#include "qqmusic_image.h"
#include "../../native/sha256.h"
#include <string.h>
#define STB_TRUETYPE_IMPLEMENTATION
#include "stb_truetype.h"
extern int sony_snprintf(char *,size_t,const char *,...) __asm__("snprintf");
static stbtt_fontinfo font;static int ready;
struct glyph_cache {unsigned cp,size,advance;int w,h,x,y;unsigned char pixels[1024];};
#define QQ_GLYPH_CACHE_ENTRIES 64u
static struct glyph_cache cache[QQ_GLYPH_CACHE_ENTRIES];static unsigned replacement;
static unsigned short *canvas,bg,ink,muted,soft,line,mint,green;
static int press_active,press_x,press_y;
static unsigned short qr_pixels[QQ_IMAGE_QR_SIDE*QQ_IMAGE_QR_SIDE];
#define RGB(r,g,b) ((unsigned short)((((r)>>3)<<11)|(((g)>>2)<<5)|((b)>>3)))
static void box(int x,int y,int w,int h,unsigned short color) {
 int row,col;for(row=y<0?0:y;row<y+h&&row<432;row++)for(col=x<0?0:x;col<x+w&&col<240;col++)canvas[row*240+col]=color;
}
static void roundbox(int x,int y,int w,int h,int radius,unsigned short color) {
 int i,j;for(j=0;j<h;j++)for(i=0;i<w;i++) {int dx=i<radius?radius-i-1:i>=w-radius?i-w+radius:0,dy=j<radius?radius-j-1:j>=h-radius?j-h+radius:0;if(dx*dx+dy*dy<=radius*radius)box(x+i,y+j,1,1,color);}
}
static unsigned short blend(unsigned short a,unsigned short b,unsigned alpha) {
 unsigned r=(((a>>11)&31)*(255-alpha)+((b>>11)&31)*alpha+127)/255;
 unsigned g=(((a>>5)&63)*(255-alpha)+((b>>5)&63)*alpha+127)/255;
 unsigned v=((a&31)*(255-alpha)+(b&31)*alpha+127)/255;
 return (unsigned short)(r<<11|g<<5|v);
}
static unsigned cp(const char **p) {
 unsigned c=(unsigned char)*(*p)++,n=0,min=0,j;
 if(c<128) return c;
 if(c>=194&&c<=223) {n=1;min=128;c&=31;}else if(c>=224&&c<=239) {n=2;min=2048;c&=15;}else if(c>=240&&c<=244) {n=3;min=65536;c&=7;}else return 0xfffd;
 for(j=0;j<n;j++) {unsigned b=(unsigned char)**p;if(!b||(b&192)!=128) return 0xfffd;(*p)++;c=c*64+(b&63);}
 return c<min||c>0x10ffff||(c>=0xd800&&c<=0xdfff)?0xfffd:c;
}
static struct glyph_cache *glyph(unsigned code,unsigned size) {
 unsigned i;int advance,bearing,w,h,x,y;float scale;unsigned char *bitmap;struct glyph_cache *g;
 for(i=0;i<QQ_GLYPH_CACHE_ENTRIES;i++) if(cache[i].size==size&&cache[i].cp==code) return &cache[i];
 g=&cache[replacement++%QQ_GLYPH_CACHE_ENTRIES];memset(g,0,sizeof(*g));g->cp=code;g->size=size;
 if(!stbtt_FindGlyphIndex(&font,(int)code)) code=0x25a1;
 scale=stbtt_ScaleForMappingEmToPixels(&font,(float)size);stbtt_GetCodepointHMetrics(&font,(int)code,&advance,&bearing);g->advance=(unsigned)(advance*scale+0.5f);
 bitmap=stbtt_GetCodepointBitmap(&font,scale,scale,(int)code,&w,&h,&x,&y);
 if(bitmap&&w>=0&&h>=0&&w<=32&&h<=32&&w*h<=1024) {g->w=w;g->h=h;g->x=x;g->y=y;memcpy(g->pixels,bitmap,(size_t)w*h);}
 stbtt_FreeBitmap(bitmap,0);return g;
}
static void text(int x,int y,int width,const char *s,unsigned size,unsigned short color) {
 int right=x+width,i,j;struct glyph_cache *g;
 if(!s||size>22) return;
 while(*s) {g=glyph(cp(&s),size);if(x+(int)g->advance>right) {box(right-10,y+(int)size-2,2,2,color);box(right-6,y+(int)size-2,2,2,color);box(right-2,y+(int)size-2,2,2,color);break;}
  for(j=0;j<g->h;j++)for(i=0;i<g->w;i++) {int px=x+g->x+i,py=y+(int)size+g->y+j;if(px>=0&&px<240&&px<right&&py>=0&&py<432)canvas[py*240+px]=blend(canvas[py*240+px],color,g->pixels[j*g->w+i]);}
  x+=(int)g->advance;
 }
}
int qq_ui_font(const unsigned char *data,size_t n) {
 static const unsigned char expected[32]=QQ_FONT_SHA256;
 struct hb_sha256 hash;unsigned char digest[32];ready=0;
 if(!data||n!=QQ_FONT_BYTES) return -1;
 hb_sha256_init(&hash);hb_sha256_update(&hash,data,(unsigned)n);hb_sha256_final(&hash,digest);
 if(memcmp(digest,expected,32)||!stbtt_InitFont(&font,data,0)) return -1;
 memset(cache,0,sizeof(cache));replacement=0;ready=1;return 0;
}
int qq_ui_font_mapped(const struct qq_asset_mapping *m){
 static const unsigned char expected[32]=QQ_FONT_SHA256;ready=0;
 if(!m||!m->data||m->bytes!=QQ_FONT_BYTES||memcmp(m->digest,expected,32)||!stbtt_InitFont(&font,m->data,0))return -1;
 memset(cache,0,sizeof(cache));replacement=0;ready=1;return 0;
}
void qq_ui_init(struct qq_native_ui *u,struct qq_music_app *app) {memset(u,0,sizeof(*u));u->app=app;u->page=app&&app->login.session.state==QQ_READY?QQ_UI_HOME:QQ_UI_LOGIN;u->quality=192;}
static void title(const char *value,int back) {if(back)text(12,29,22,"‹",22,ink);text(back?44:13,29,180,value,18,ink);}
static void button(int y,const char *label,int primary) {int pressed=press_active&&press_x>=14&&press_x<226&&press_y>=y&&press_y<y+42;roundbox(14,y,212,42,20,pressed?(primary?RGB(0,145,83):mint):(primary?green:soft));text(36,y+10+pressed,184,label,14,primary?RGB(255,255,255):ink);}
void qq_ui_touch_feedback(struct qq_native_ui *u,int x,int y,int phase,uint64_t now){
 if(!u)return;
 if(phase<0){u->touch_held=0;u->touch_until=0;u->touch_notice=2;}
 else {if(x<0||x>=240||y<0||y>=432)return;u->touch_x=x;u->touch_y=y;u->touch_held=phase!=0;u->touch_until=now>UINT64_MAX-180?UINT64_MAX:now+180;u->touch_notice=phase?0:1;}
 u->notice_until=now>UINT64_MAX-900?UINT64_MAX:now+900;
}
static void artwork(const struct qq_native_ui *u,int x,int y,int width,int height,const char *mid) {
 unsigned w=0,h=0;const unsigned short *image=mid&&u->cover?u->cover(u->cover_context,mid,&w,&h):0;int i,j;
 if(image&&w&&h&&w<=1024&&h<=1024) {for(j=0;j<height;j++)for(i=0;i<width;i++)box(x+i,y+j,1,1,image[(unsigned)j*h/(unsigned)height*w+(unsigned)i*w/(unsigned)width]);}
 else {roundbox(x,y,width,height,7,mint);text(x+width/3,y+height/4,width-width/3,"♪",(unsigned)(height>60?22:15),green);}
}
static void thumb(const struct qq_native_ui *u,int x,int y,int size,const char *mid) {artwork(u,x,y,size,size,mid);}
static void nav(unsigned selected) {static const char *labels[]={"收藏","导入","我的"};unsigned i;box(0,381,240,1,line);for(i=0;i<3;i++) {text(30+(int)i*80,393,48,labels[i],12,i==selected?green:muted);if(i==selected)roundbox(34+(int)i*80,419,17,3,1,green);}}
static int login_active(const struct qq_login *f) {
 return f->session.state==QQ_QR_WAIT||f->session.state==QQ_QR_SCANNED||f->session.state==QQ_EXCHANGE||f->session.state==QQ_VERIFY;
}
static int qr_visible(const struct qq_native_ui *u) {
 const struct qq_login *f=&u->app->login;
 return f->stage==QQ_LOGIN_POLL&&(f->session.state==QQ_QR_WAIT||f->session.state==QQ_QR_SCANNED)&&
  f->qr_bytes&&u->monotonic_ms&&u->monotonic_ms>=f->last_ms&&u->monotonic_ms<f->session.deadline_ms;
}
static int draw_qr(const struct qq_native_ui *u) {
 unsigned w,h,scale,i,j;int x,y,rc=-1;
 if(!qr_visible(u))return 0;
 if(qq_image_qr(u->app->login.qr,u->app->login.qr_bytes,qr_pixels,sizeof(qr_pixels)/sizeof(*qr_pixels),&w,&h))goto done;
 scale=196/w;if(!scale)goto done;
 box(6,119,228,228,RGB(255,255,255));x=(240-(int)(w*scale))/2;y=119+(228-(int)(h*scale))/2;
 for(j=0;j<h;j++)for(i=0;i<w;i++)box(x+(int)(i*scale),y+(int)(j*scale),(int)scale,(int)scale,qr_pixels[j*w+i]);
 rc=1;
done:qq_secret_clear(qr_pixels,sizeof(qr_pixels));return rc;
}
int qq_ui_draw(const struct qq_native_ui *u,unsigned short *pixels,size_t count) {
 struct qq_music_app *a;unsigned i;char number[96];
 if(!ready||!u||!u->app||!pixels||count!=QQ_UI_PIXELS) return -1;
 a=u->app;canvas=pixels;press_active=u->touch_held||u->monotonic_ms<u->touch_until;press_x=u->touch_x;press_y=u->touch_y;
 bg=u->dark?RGB(16,23,19):RGB(255,255,255);ink=u->dark?RGB(237,245,240):RGB(23,33,29);muted=u->dark?RGB(157,170,162):RGB(123,133,128);
 soft=u->dark?RGB(29,39,33):RGB(245,247,246);line=u->dark?RGB(42,54,46):RGB(237,240,238);mint=u->dark?RGB(23,60,41):RGB(231,249,239);green=RGB(24,185,120);
 box(0,0,240,432,bg);text(12,3,100,"Walkman",10,ink);text(205,3,30,"QQ",10,muted);
 if(u->page==QQ_UI_HOME) {
  title("我的音乐",0);text(13,70,160,"我的 QQ 音乐收藏",11,muted);
  roundbox(12,94,216,76,14,mint);roundbox(24,109,44,44,12,green);text(33,116,30,"♥",22,RGB(255,255,255));text(80,108,135,"我喜欢",17,ink);
  for(i=0;i<a->playlists.count;i++) if(a->playlists.entries[i].dirid==201) break;
  if(i<a->playlists.count) sony_snprintf(number,sizeof(number),"%llu 首歌曲",(unsigned long long)a->playlists.entries[i].songs);else memcpy(number,"同步后查看收藏",sizeof("同步后查看收藏"));text(80,135,134,number,11,muted);
  text(13,181,190,"收藏歌单",14,ink);
  {unsigned shown=0;for(i=0;i<a->playlists.count&&shown<2;i++) {int x;if(a->playlists.entries[i].dirid==201)continue;x=12+(int)shown*114;artwork(u,x,208,102,72,0);text(x,291,102,a->playlists.entries[i].title,12,ink);shown++;}}
  roundbox(12,343,216,27,8,soft);if(u->space_known)sony_snprintf(number,sizeof(number),"用户存储可用 %llu MB",(unsigned long long)(u->available_bytes/1048576));else memcpy(number,"用户存储：尚未核验",sizeof("用户存储：尚未核验"));text(22,348,202,number,10,muted);nav(0);
 } else if(u->page==QQ_UI_SONGS) {
  title(u->list_index<a->playlists.count?a->playlists.entries[u->list_index].title:"歌曲",1);text(13,76,210,"选择一首，下载到本机",12,muted);
  for(i=0;i<5&&u->song_offset+i<a->songs.count;i++) {unsigned index=u->song_offset+i;int y=104+(int)i*(u->readable?54:52);thumb(u,12,y,37,a->songs.entries[index].mid);text(60,y,163,a->songs.entries[index].title,u->readable?15:14,ink);text(60,y+23,163,a->songs.entries[index].artist,11,muted);box(60,y+46,168,1,line);}
  if(u->song_offset)text(12,398,90,"‹ 上一页",12,green);
  if(u->song_offset+5<a->songs.count||a->songs.more)text(160,398,66,"下一页 ›",12,green);
 } else if(u->page==QQ_UI_DETAIL) {
  title("歌曲详情",1);thumb(u,72,70,96,a->selected.mid);text(16,179,208,a->selected.title,18,ink);text(16,205,208,a->selected.artist,12,muted);text(16,225,208,a->selected.album,11,muted);
  text(14,255,212,"封面与歌曲信息，一起保存",11,green);text(14,282,212,"MP3 导出码率",12,ink);
  for(i=0;i<3;i++) {unsigned quality=i==0?128:i==1?192:320;roundbox(14+(int)i*72,306,67,40,8,u->quality==quality?mint:soft);sony_snprintf(number,sizeof(number),"%u kbps",quality);text(20+(int)i*72,317,59,number,11,u->quality==quality?green:ink);}
  button(363,a->pending?"正在请求音源":a->view==QQ_APP_RESOURCE_READY?"继续导入 MP3":"下载为 MP3",1);
 } else if(u->page==QQ_UI_LOGIN) {
  int shown,clock_error=u->connection_failed&&u->connection.step==QQ_STEP_CLOCK;const char *status="使用手机 QQ 扫描并确认";
  title("账号登录",0);text(14,72,212,"QQ 音乐扫码登录",18,ink);
  if(clock_error)status=u->connection.clock_skew_seconds?"设备时间与服务器不一致":u->connection.tls?"证书日期校验未通过":"设备日期异常，请检查时间";
  else if(qq_app_can_retry_login(a))status="手机确认已完成，请重试连接";
  else if(u->initializing)status=u->connecting_wifi?"正在连接 Walkman Wi-Fi":"正在连接 QQ 音乐服务";
  else if(u->connection_failed)status=u->connecting_wifi?"Walkman Wi-Fi 尚未连接":"连接未完成，请检查 Wi-Fi 与时间";
  else if(a->login.session.state==QQ_QR_SCANNED)status="已扫码，请在手机确认";
  else if(a->login.session.state==QQ_EXCHANGE||a->login.session.state==QQ_VERIFY)status="正在验证 QQ 音乐账号";
  else if(a->login.session.state==QQ_CANCELLED)status="扫码已取消，可重新获取";
  else if(a->login.session.state==QQ_EXPIRED||(login_active(&a->login)&&u->monotonic_ms>=a->login.session.deadline_ms))status="登录已过期，请重新扫码";
  else if(a->login.session.state==QQ_FAILED)status="登录未完成，请重新获取";
  text(14,100,212,status,11,muted);roundbox(6,119,228,228,10,soft);shown=clock_error?0:draw_qr(u);
  if(clock_error){
   char date[96];
   if(u->connection.clock_skew_seconds){
    unsigned delta=(unsigned)(u->connection.clock_skew_seconds<0?-(int64_t)u->connection.clock_skew_seconds:u->connection.clock_skew_seconds);
    const char *direction=u->connection.clock_skew_seconds>0?"快":"慢";
    text(22,167,198,"设备时间存在偏差",16,ink);
    sony_snprintf(date,sizeof(date),"设备 UTC  %02u:%02u",u->connection.clock_hour,u->connection.clock_minute);text(22,201,198,date,12,ink);
    sony_snprintf(date,sizeof(date),"服务 UTC  %02u:%02u",u->connection.server_hour,u->connection.server_minute);text(22,223,198,date,12,ink);
    if(delta>=3600)sony_snprintf(date,sizeof(date),"设备时间%s约 %u 小时",direction,(delta+1800)/3600);
    else sony_snprintf(date,sizeof(date),"设备时间%s约 %u 分钟",direction,(delta+30)/60);
    text(22,250,198,date,12,ink);
    if(u->connection.clock_skew_seconds>=28500&&u->connection.clock_skew_seconds<=29100){
     text(22,275,198,"保留原厂时间，仅 QQ 换算",11,muted);button(303,"设备显示北京时间",1);
    }else{text(22,278,198,"请检查设备日期和时间",12,muted);text(22,301,198,"检查后点击下方重试",11,muted);}
   }else{
   text(22,182,198,u->connection.tls?"证书日期校验失败":"设备日期异常",16,ink);
   if(u->connection.clock_year)sony_snprintf(date,sizeof(date),"检测日期：%04u-%02u-%02u",u->connection.clock_year,u->connection.clock_month,u->connection.clock_day);
   else sony_snprintf(date,sizeof(date),"无法读取设备日期");
   text(22,216,198,date,12,ink);text(22,247,198,"请检查 Walkman 设置中的",12,muted);text(22,269,198,"日期和时间，然后重试",12,muted);
   if(u->connection.tls)text(22,301,198,"时间正确时请稍后重试",10,muted);
   }
  }
  else if(shown<=0)text(22,214,198,shown<0?"二维码无效，请取消后重试":u->initializing?(u->connecting_wifi?"正在连接 Wi-Fi…":"正在连接 QQ 音乐…"):u->connection_failed?(u->connecting_wifi?"Wi-Fi 连接失败，请重试":"服务连接失败，请重试"):login_active(&a->login)?"正在获取二维码…":"等待有效登录二维码",12,muted);
  if(u->connection_failed&&shown<=0&&!clock_error){
   static const char *steps[]={"未分类","初始化","Wi-Fi","DNS","TCP","TLS","HTTP","响应"};char detail[96];unsigned s=(unsigned)u->connection.step;
   sony_snprintf(detail,sizeof(detail),"%s  E%d  D%d",s<8?steps[s]:steps[0],u->connection.error,u->connection.dns);text(20,249,202,detail,11,ink);
   sony_snprintf(detail,sizeof(detail),"TLS %d  HTTP %d  接口 %d",u->connection.tls,u->connection.http,u->connection.endpoint);text(20,271,202,detail,10,muted);
  }
  button(357,clock_error?"检查时间后重试":qq_app_can_retry_login(a)?"重试登录":u->initializing?"取消连接":login_active(&a->login)?"取消本次扫码":u->connection_failed?"重新连接并获取二维码":"获取登录二维码",qq_app_can_retry_login(a)||(!u->initializing&&!login_active(&a->login)));
 } else if(u->page==QQ_UI_ACCOUNT) {title("我的",0);text(14,86,212,"QQ 扫码账号",17,ink);text(14,132,212,"保存位置：用户存储",13,ink);text(14,171,212,"原始音频：保留",13,ink);button(246,"重新扫码登录",0);button(304,"退出 QQ 音乐",0);nav(2);
 } else if(u->page==QQ_UI_IMPORTS) {title("导入记录",0);text(16,176,208,"导入结果等待任务提供",14,muted);button(299,"去我的收藏",1);nav(1);
 } else if(u->page==QQ_UI_PROGRESS) {
  static const char *steps[]={"下载原始音频","转换为 MP3","整理封面与标签","保存到本机音乐"};
  unsigned current=u->stage<4?u->stage:3;title("正在导入",1);text(14,74,212,a->selected.title,16,ink);
  sony_snprintf(number,sizeof(number),"任务进度 %u%%",u->percent>100?100:u->percent);text(14,102,212,number,11,muted);
  roundbox(14,127,212,5,2,soft);roundbox(14,127,(int)(u->percent>100?100:u->percent)*212/100,5,2,green);
  for(i=0;i<4;i++){
   int y=149+(int)i*47;
   if(i==current)roundbox(12,y-3,216,43,8,mint);
   text(28,y,192,steps[i],13,i==current?green:i<current?ink:muted);
   text(28,y+19,192,i<current?"已完成":i==current?"正在进行…":"等待开始",10,i==current?green:muted);
   if(i==current)box(17,y+3+(int)(u->monotonic_ms/250%3)*5,3,3,green);
  }
  button(357,"取消本次导入",0);
 } else if(u->page==QQ_UI_RESULT) {title("导入结果",1);text(14,112,212,u->import_complete?"MP3 已准备好":u->import_review?"需要检查保存结果":"尚未完成导入",20,u->import_complete?green:ink);text(14,166,212,"原厂曲库识别仍需确认",12,muted);button(281,"退出 QQ 音乐",1);button(339,"继续选歌",0);}
 if(u->page==QQ_UI_LOGIN&&u->touch_notice&&u->monotonic_ms<u->notice_until)text(14,411,212,u->touch_notice==2?"触摸已取消，请轻点":"已收到触摸",11,green);
 return 0;
}
enum qq_ui_action qq_ui_tap(struct qq_native_ui *u,int x,int y) {
 struct qq_music_app *a;unsigned i;
 if(!u||!u->app||x<0||x>=240||y<0||y>=432) return QQ_UI_NONE;
 a=u->app;
 if(y>=381&&(u->page==QQ_UI_HOME||u->page==QQ_UI_IMPORTS||u->page==QQ_UI_ACCOUNT)) {u->page=x<80?QQ_UI_HOME:x<160?QQ_UI_IMPORTS:QQ_UI_ACCOUNT;return QQ_UI_CHANGED;}
 if(x<44&&y>=20&&y<62&&u->page!=QQ_UI_HOME) {
  if(u->page==QQ_UI_LOGIN&&login_active(&a->login))return QQ_UI_CANCEL;
  if(u->page==QQ_UI_PROGRESS||a->pending)return QQ_UI_CANCEL;
  if(u->page==QQ_UI_DETAIL) {
   if(a->view==QQ_APP_RESOURCE_READY&&qq_app_back(a))return QQ_UI_NONE;
   if(qq_app_back(a))return QQ_UI_NONE;
   u->page=QQ_UI_SONGS;
  } else {if(u->page==QQ_UI_SONGS&&qq_app_back(a))return QQ_UI_NONE;u->page=QQ_UI_HOME;}
  return QQ_UI_CHANGED;
 }
 if(u->page==QQ_UI_HOME) {
  if(y>=94&&y<170) {for(i=0;i<a->playlists.count;i++)if(a->playlists.entries[i].dirid==201)break;if(i==a->playlists.count)return QQ_UI_SYNC;u->list_index=i;if(qq_app_open_playlist(a,i))return QQ_UI_NONE;u->song_offset=0;u->page=QQ_UI_SONGS;return QQ_UI_OPEN_PLAYLIST;}
  if(y>=208&&y<326&&x>=12&&x<228&&(x<114||x>=126)) {
   unsigned shown=0,wanted=x<126?0:1;
   for(i=0;i<a->playlists.count;i++) {if(a->playlists.entries[i].dirid==201)continue;if(shown++==wanted)break;}
   if(i<a->playlists.count&&qq_app_open_playlist(a,i)==0){u->list_index=i;u->song_offset=0;u->page=QQ_UI_SONGS;return QQ_UI_OPEN_PLAYLIST;}
  }
 } else if(u->page==QQ_UI_SONGS) {
  if(y>=388&&x<100&&u->song_offset){u->song_offset=u->song_offset>=5?u->song_offset-5:0;return QQ_UI_CHANGED;}
  if(y>=388&&x>=140) {
   if(u->song_offset+5<a->songs.count){u->song_offset+=5;return QQ_UI_CHANGED;}
   if(a->songs.more&&qq_app_next_page(a)==0){u->song_offset=0;return QQ_UI_NEXT_PAGE;}
  }
  if(y>=104&&y<374){i=(unsigned)(y-104)/(u->readable?54:52);if(i<5&&u->song_offset+i<a->songs.count&&qq_app_select_song(a,u->song_offset+i)==0){u->selected_index=u->song_offset+i;u->page=QQ_UI_DETAIL;return QQ_UI_CHANGED;}}
 }
 else if(u->page==QQ_UI_DETAIL) {if(y>=306&&y<346){u->quality=x<86?128:x<158?192:320;return QQ_UI_CHANGED;}if(y>=363&&y<405&&!a->pending)return a->view==QQ_APP_RESOURCE_READY?QQ_UI_IMPORT:QQ_UI_AUTHORIZE;}
 else if(u->page==QQ_UI_LOGIN){
  if(y>=303&&y<345&&u->connection_failed&&u->connection.step==QQ_STEP_CLOCK&&u->connection.clock_skew_seconds>=28500&&u->connection.clock_skew_seconds<=29100&&!u->initializing&&!login_active(&a->login))return QQ_UI_TIME_UTC8;
  if(y>=357&&y<399)return qq_app_can_retry_login(a)?QQ_UI_LOGIN_RETRY:u->initializing||login_active(&a->login)?QQ_UI_CANCEL:QQ_UI_LOGIN_START;
 }
 else if(u->page==QQ_UI_ACCOUNT){if(y>=246&&y<288)return QQ_UI_LOGIN_START;if(y>=304&&y<346)return QQ_UI_RETURN_STOCK;}
 else if(u->page==QQ_UI_PROGRESS&&y>=357&&y<399)return QQ_UI_CANCEL;
 else if(u->page==QQ_UI_RESULT){if(y>=281&&y<323)return QQ_UI_RETURN_STOCK;if(y>=339&&y<381){u->page=QQ_UI_SONGS;return QQ_UI_CHANGED;}}
 else if(u->page==QQ_UI_IMPORTS&&y>=299&&y<341){u->page=QQ_UI_HOME;return QQ_UI_CHANGED;}
 return QQ_UI_NONE;
}

static uint32_t visual_hash(uint32_t h,const void *data,size_t n){const unsigned char *p=data;while(n--){h^=*p++;h*=16777619u;}return h;}
uint32_t qq_ui_frame_key(const struct qq_native_ui *u){
 struct qq_native_ui v;const struct qq_music_app *a;uint32_t h=2166136261u;unsigned timed;
 if(!u||!u->app)return 0;
 a=u->app;v=*u;v.monotonic_ms=0;v.touch_until=0;v.notice_until=0;
 v.touch_held=u->touch_held||u->monotonic_ms<u->touch_until;
 if(u->monotonic_ms>=u->notice_until)v.touch_notice=0;
 h=visual_hash(h,&v,sizeof(v));
 h=visual_hash(h,&a->view,sizeof(a->view));h=visual_hash(h,&a->pending,sizeof(a->pending));
 h=visual_hash(h,&a->login.session.state,sizeof(a->login.session.state));h=visual_hash(h,&a->login.stage,sizeof(a->login.stage));
 if(u->page==QQ_UI_HOME)h=visual_hash(h,&a->playlists,sizeof(a->playlists));
 if(u->page==QQ_UI_SONGS){h=visual_hash(h,&a->songs,sizeof(a->songs));h=visual_hash(h,&a->playlists,sizeof(a->playlists));}
 if(u->page==QQ_UI_DETAIL||u->page==QQ_UI_PROGRESS)h=visual_hash(h,&a->selected,sizeof(a->selected));
 if(u->page==QQ_UI_LOGIN){timed=qr_visible(u);h=visual_hash(h,&timed,sizeof(timed));h=visual_hash(h,&a->login.qr_bytes,sizeof(a->login.qr_bytes));if(timed)h=visual_hash(h,a->login.qr,a->login.qr_bytes);timed=qq_app_can_retry_login(a);h=visual_hash(h,&timed,sizeof(timed));}
 if(u->page==QQ_UI_PROGRESS){timed=(unsigned)(u->monotonic_ms/250%3);h=visual_hash(h,&timed,sizeof(timed));}
 return h;
}
int qq_ui_press_overlay(const struct qq_native_ui *u,unsigned short *pixels,size_t count){
 int x,y,left,top,w=22,h=22;
 if(!u||!pixels||count!=QQ_UI_PIXELS)return -1;
 canvas=pixels;x=u->touch_x;y=u->touch_y;left=x-11;top=y-11;
 /* An immediate outline preserves the already rasterized button label. */
 if(x>=14&&x<226){
  if((u->page==QQ_UI_LOGIN||u->page==QQ_UI_PROGRESS)&&y>=357&&y<399){left=14;top=357;w=212;h=42;}
  else if(u->page==QQ_UI_DETAIL&&y>=363&&y<405){left=14;top=363;w=212;h=42;}
 }
 box(left,top,w,2,RGB(0,130,77));box(left,top+h-2,w,2,RGB(0,130,77));box(left,top,2,h,RGB(0,130,77));box(left+w-2,top,2,h,RGB(0,130,77));return 0;
}
