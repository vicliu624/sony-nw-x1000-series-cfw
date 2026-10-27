/* Original software-drawn pocket-radio skin, inspired by Sony SRF-M97/M98.
 * No product photograph, bitmap texture, fake signal meter or unsupported band. */
#define RGB(r,g,b) ((unsigned short)((((r)>>3)<<11)|(((g)>>2)<<5)|((b)>>3)))
#define BG RGB(24,28,31)
#define PANEL RGB(185,190,188)
#define LINE RGB(118,126,126)
#define WHITE RGB(39,46,45)
#define MUTED RGB(86,95,94)
#define ACCENT RGB(39,61,47)
#define LCD RGB(171,188,160)
#define LCD_INK RGB(33,49,35)
static unsigned short chassis[HB_DISPLAY_PIXELS];
static int chassis_ready,skin_down,skin_x,skin_y;
static void box(int x,int y,int w,int h,unsigned short c){
 for(int j=y<0?0:y;j<y+h&&j<432;j++)for(int i=x<0?0:x;i<x+w&&i<240;i++)canvas[j*240+i]=c;
}
static int rounded(int x,int y,int w,int h,int radius){
 int dx=x<radius?radius-x-1:x>=w-radius?x-(w-radius):0;
 int dy=y<radius?radius-y-1:y>=h-radius?y-(h-radius):0;
 return dx*dx+dy*dy<=radius*radius;
}
static void roundbox(int x,int y,int w,int h,int radius,unsigned short c){
 for(int j=0;j<h;j++)for(int i=0;i<w;i++)if(rounded(i,j,w,h,radius))box(x+i,y+j,1,1,c);
}
static unsigned short blend(unsigned short a,unsigned short b,int n,int d){
 int ar=(a>>11)&31,ag=(a>>5)&63,ab=a&31;
 int br=(b>>11)&31,bg=(b>>5)&63,bb=b&31;
 return (unsigned short)(((ar+(br-ar)*n/d)<<11)|((ag+(bg-ag)*n/d)<<5)|(ab+(bb-ab)*n/d));
}
static void bevel(int x,int y,int w,int h,int radius,unsigned short top,unsigned short bottom){
 for(int j=0;j<h;j++){unsigned short c=blend(top,bottom,j,h-1);for(int i=0;i<w;i++)if(rounded(i,j,w,h,radius))box(x+i,y+j,1,1,c);}
}
static void disc(int cx,int cy,int radius,unsigned short top,unsigned short bottom){
 for(int dy=-radius;dy<=radius;dy++){unsigned short c=blend(top,bottom,dy+radius,2*radius);
  for(int dx=-radius;dx<=radius;dx++)if(dx*dx+dy*dy<=radius*radius)box(cx+dx,cy+dy,1,1,c);
 }
}
static void label(int x,int y,const char *s,int scale,unsigned short color){
 for(;*s;s++,x+=6*scale){
  int g=*s>='0'&&*s<='9'?*s-'0':*s>='A'&&*s<='Z'?*s-'A'+10:-1;
  if(*s=='.'){box(x+scale,y+6*scale,scale,scale,color);continue;}
  if(*s=='-'){box(x,y+3*scale,5*scale,scale,color);continue;}
  if(*s=='+'){box(x,y+3*scale,5*scale,scale,color);box(x+2*scale,y+scale,scale,5*scale,color);continue;}
  if(g<0)continue;
  for(int j=0;j<7;j++)for(int i=0;i<5;i++)if(glyph[g][j]&(1<<(4-i)))box(x+i*scale,y+j*scale,scale,scale,color);
 }
}
static void centered(int x,int y,int w,const char *s,int scale,unsigned short color){label(x+(w-(int)strlen(s)*6*scale+scale)/2,y,s,scale,color);}
static void button(int x,int y,int w,int h,const char *s,int dark){
 int down=skin_down&&skin_x>=x&&skin_x<x+w&&skin_y>=y&&skin_y<y+h;
 roundbox(x,y+2,w,h,8,RGB(78,86,88));
 if(dark)bevel(x,y+down,w,h-2,8,down?RGB(43,50,51):RGB(79,87,88),RGB(37,44,46));
 else bevel(x,y+down,w,h-2,8,down?RGB(164,171,171):RGB(231,234,230),down?RGB(196,202,199):RGB(164,173,172));
 if(!down)box(x+9,y+1,w-18,1,dark?RGB(117,124,124):RGB(246,247,242));
 centered(x,y+(h-7)/2+down,w,s,1,dark?RGB(224,232,220):WHITE);
}
static void lcd_panel(int x,int y,int w,int h){
 roundbox(x-3,y-3,w+6,h+6,9,RGB(100,108,106));
 roundbox(x-2,y-2,w+4,h+4,8,RGB(38,44,42));
 bevel(x,y,w,h,6,RGB(166,182,155),RGB(174,190,163));
 box(x+6,y+2,w-12,1,RGB(113,130,108));
}
static void lcd_number(const char *s,int y){
 static const unsigned char masks[]={63,6,91,79,102,109,125,7,127,111};
 int width=0;for(const char *p=s;*p;p++)width+=*p=='.'?10:24;
 int x=(240-width+4)/2;
 const int segments[7][4]={{3,0,14,3},{17,3,3,12},{17,18,3,12},{3,30,14,3},{0,18,3,12},{0,3,3,12},{3,15,14,3}};
 for(;*s;s++){
  if(*s=='.'){roundbox(x,y+29,4,4,1,LCD_INK);x+=10;continue;}
  if(*s<'0'||*s>'9')continue;
  for(int k=0;k<7;k++){const int *a=segments[k];roundbox(x+a[0],y+a[1],a[2],a[3],1,(masks[*s-'0']&(1<<k))?LCD_INK:RGB(151,172,143));}
  x+=24;
 }
}
static void screw(int x,int y){
 disc(x,y,3,RGB(111,120,121),RGB(223,228,224));box(x-2,y,5,1,RGB(94,102,102));
}
static void shell(void){
 if(chassis_ready){memcpy(canvas,chassis,sizeof(canvas));return;}
 for(int y=0;y<432;y++)box(0,y,240,1,blend(RGB(41,47,51),RGB(17,21,24),y,431));
 roundbox(21,17,210,409,23,RGB(8,11,13));
 bevel(14,8,214,414,23,RGB(235,237,230),RGB(91,104,106));
 for(int y=12;y<418;y++)for(int x=18;x<224;x++)if(rounded(x-18,y-12,206,406,20)){
  int edge=x<30?30-x:x>207?207-x:0;
  int grain=((y*13+x*3)%7)-3;
  int v=204+edge+grain-(y*9/432);
  box(x,y,1,1,RGB(v,v+3,v+1));
 }
 box(23,39,1,344,RGB(239,241,234));box(219,39,1,344,RGB(136,147,147));
 /* Side seam and ridges imply the mechanical jog wheel; they are decoration. */
 roundbox(224,167,9,44,3,RGB(79,89,92));
 for(int y=170;y<208;y+=4)box(225,y,7,1,RGB(165,173,172));
 label(29,23,"SONY",2,RGB(54,61,60));label(177,27,"FM",1,RGB(74,84,82));
 screw(30,399);screw(210,399);
 memcpy(chassis,canvas,sizeof(canvas));chassis_ready=1;
}
static void draw(struct fm_ui *ui){
 struct fm_radio *r=ui->radio;char line[40];shell();skin_down=ui->touch_down;skin_x=ui->touch_x;skin_y=ui->touch_y;
 if(ui->simulated)label(177,40,"DEMO",1,MUTED);
 if(ui->page==FM_ERROR){
  lcd_panel(25,68,190,188);
  centered(30,111,180,"RADIO NOT READY",1,LCD_INK);
  centered(30,148,180,"UNABLE TO START",1,LCD_INK);
  centered(30,167,180,"THE FM RECEIVER",1,LCD_INK);
  centered(30,211,180,"RETURN AND TRY AGAIN",1,LCD_INK);
  button(55,390,130,27,"BACK TO APPS",0);return;
 }
 if(ui->page==FM_INPUT){
  lcd_panel(28,62,184,43);label(38,69,"TUNE FREQUENCY",1,LCD_INK);
  label(38,85,ui->length?ui->input:"0.0",2,LCD_INK);label(182,91,"MHZ",1,LCD_INK);
  button(52,110,136,24,ui->input_error?"INVALID - CLEAR":"CLEAR INPUT",0);
  static const char *keys[]={"1","2","3","4","5","6","7","8","9",".","0","OK"};
  for(int k=0;k<12;k++){int x=(k%3)*64+28,y=144+(k/3)*48;
   int down=skin_down&&skin_x>=x&&skin_x<x+56&&skin_y>=y+3&&skin_y<y+43;
   button(x,y+3,56,40,"",k==11);centered(x,y+14+down,56,keys[k],2,k==11?RGB(224,232,220):WHITE);
  }
  centered(24,353,192,"76.0 - 108.0 MHZ",1,MUTED);
  button(55,390,130,27,"BACK TO RADIO",0);return;
 }
 if(ui->page==FM_FAVORITES||ui->page==FM_STATIONS){
  int favorites=ui->page==FM_FAVORITES;unsigned count=favorites?r->favorite_count:r->station_count;
  struct fm_station *stations=favorites?r->favorites:r->stations;
  lcd_panel(25,61,190,248);label(35,71,favorites?"PRESET MEMORY":"STATION LIST",1,LCD_INK);
  snprintf(line,sizeof(line),"%02u",count);label(190,71,line,1,LCD_INK);
  if(!count){centered(27,163,186,"NO STATIONS YET",1,LCD_INK);centered(27,183,186,favorites?"SAVE A FREQUENCY":"START A BAND SCAN",1,LCD_INK);}
  for(unsigned j=0;j<5&&ui->offset+j<count;j++){
   struct fm_station *station=&stations[ui->offset+j];int y=88+(int)j*44;
   box(33,y+38,174,1,RGB(140,158,131));snprintf(line,sizeof(line),"%d.%d",station->khz/1000,(station->khz%1000)/100);
   label(37,y+11,line,2,LCD_INK);label(109,y+18,"MHZ",1,LCD_INK);if(favorites)label(186,y+18,"DEL",1,LCD_INK);
  }
  button(25,326,88,31,"PREV",0);button(127,326,88,31,"NEXT",0);
  button(55,390,130,27,"BACK TO RADIO",0);return;
 }
 /* Circular LCD and double bezel echo the lighter-size M97/M98 form. */
 disc(120,104,72,RGB(246,247,241),RGB(121,132,131));
 disc(120,104,69,RGB(34,42,42),RGB(83,93,91));
 disc(120,104,64,RGB(164,181,154),RGB(174,189,162));
 centered(54,58,132,"FM",1,LCD_INK);
 snprintf(line,sizeof(line),"%d.%d",r->frequency/1000,(r->frequency%1000)/100);lcd_number(line,84);
 centered(54,124,132,"MHZ",1,LCD_INK);
 centered(54,141,132,r->error?"TUNER ERROR":r->scanning?"SEARCHING":"TAP TO TUNE",1,LCD_INK);
 button(27,175,86,27,"- TUNE",0);button(127,175,86,27,"TUNE +",0);
 centered(24,208,192,"SYNTHESIZED TUNING",1,MUTED);
 button(27,225,186,27,r->scanning?"CANCEL SEARCH":"AUTO SEARCH",1);
 centered(24,261,192,"PRESET MEMORY",1,MUTED);
 button(53,280,134,25,"+ SAVE STATION",0);
 snprintf(line,sizeof(line),"MEMORY  %02u",r->favorite_count);label(32,321,line,1,WHITE);label(178,321,"LIST",1,MUTED);
 box(29,334,182,1,RGB(160,169,164));
 snprintf(line,sizeof(line),"STATIONS  %02u",r->station_count);label(32,350,line,1,WHITE);label(178,350,"LIST",1,MUTED);
 const char *notice=ui->storage_notice==-5?"SAVE NOT SYNCED":ui->storage_notice==-2?"PRESETS DAMAGED":ui->storage_notice==-3?"SAVING UNAVAILABLE":ui->storage_notice<0?"SAVE FAILED - TAP":"POCKET FM RECEIVER";
 centered(26,374,188,notice,1,MUTED);
 button(55,390,130,27,"BACK TO APPS",0);
}
