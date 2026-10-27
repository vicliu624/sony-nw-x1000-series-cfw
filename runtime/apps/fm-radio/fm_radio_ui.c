#include "fm_radio_ui.h"
#include <string.h>
int fm_parse_mhz(const char *s,int *khz){
 if(!s||!khz)return -1;
 int whole=0,frac=0,n=0,digits=0;
 while(*s>='0'&&*s<='9'){if(++digits>3)return -1;whole=whole*10+*s++-'0';}
 if(!digits)return -1;
 if(*s=='.'){s++;while(*s>='0'&&*s<='9'){if(++n>3)return -1;frac=frac*10+*s++-'0';}if(!n)return -1;}
 if(*s||whole>108)return -1;
 while(n++<3)frac*=10;
 *khz=whole*1000+frac;return 0;
}
void fm_ui_init(struct fm_ui *ui,struct fm_radio *radio){memset(ui,0,sizeof(*ui));ui->radio=radio;}
int fm_ui_tap(struct fm_ui *ui,int x,int y){
 struct fm_radio *r=ui->radio;
 if(x<0||x>=240||y<0||y>=432)return 0;
 if(y>=384){if(ui->page==FM_MAIN||ui->page==FM_ERROR)return 1;ui->page=FM_MAIN;return 0;}
 if(ui->page==FM_ERROR)return y>=384?1:0;
 if(ui->page==FM_INPUT){
  if(y>=104&&y<136){ui->length=0;ui->input[0]=0;ui->input_error=0;return 0;}
  if(y<144||y>=336||x<24||x>=216)return 0;
  int key=((y-144)/48)*3+(x-24)/64;
  if(key==11){int khz;if(fm_parse_mhz(ui->input,&khz)||fm_tune(r,khz))ui->input_error=1;else ui->page=FM_MAIN;return 0;}
  char c=key<9?(char)('1'+key):key==9?'.':'0';
  if(ui->length<sizeof(ui->input)-1){if(c=='.'&&strchr(ui->input,'.'))return 0;ui->input[ui->length++]=c;ui->input[ui->length]=0;ui->input_error=0;}return 0;
 }
 if(ui->page==FM_FAVORITES||ui->page==FM_STATIONS){
  unsigned count=ui->page==FM_FAVORITES?r->favorite_count:r->station_count;
  if(y>=320&&y<368){if(x<120){if(ui->offset>=5)ui->offset-=5;}else if(ui->offset+5<count)ui->offset+=5;return 0;}
  if(y>=88&&y<308){unsigned i=ui->offset+(unsigned)(y-88)/44;if(i<count){
   if(ui->page==FM_FAVORITES&&x>=180){fm_remove_favorite(r,i);if(ui->offset>=r->favorite_count&&ui->offset>=5)ui->offset-=5;}
   else {int khz=ui->page==FM_FAVORITES?r->favorites[i].khz:r->stations[i].khz;if(!fm_tune(r,khz))ui->page=FM_MAIN;}
  }}return 0;
 }
 if(y>=64&&y<112&&!r->scanning){ui->page=FM_INPUT;ui->length=0;ui->input[0]=0;ui->input_error=0;}
 else if(y>=160&&y<204)fm_step(r,x<120?-1:1);
 else if(y>=212&&y<256){if(r->scanning)fm_scan_cancel(r);else fm_scan_start(r,r->threshold);}
 else if(y>=264&&y<308)fm_favorite(r,"FAVORITE");
 else if(y>=308&&y<336&&!r->scanning){ui->page=FM_FAVORITES;ui->offset=0;}
 else if(y>=336&&y<376&&!r->scanning){ui->page=FM_STATIONS;ui->offset=0;}
 return 0;
}
