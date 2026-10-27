/* Actual stb renderer: derivative glyphs must match their original outlines. */
#include "../../runtime/apps/qqmusic/qqmusic_font.h"
#include "../../runtime/apps/qqmusic/qqmusic_ui.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "stb_truetype.h"
#ifdef __arm__
extern size_t sony_fread(void *,size_t,size_t,FILE *) __asm__("fread");
extern int sony_fprintf(FILE *,const char *,...) __asm__("fprintf");
#define fread sony_fread
#define fprintf sony_fprintf
#endif
static unsigned char sheet[480*120*3];
static unsigned char *load(const char *path,size_t *size){FILE *f=fopen(path,"rb");long n;unsigned char *p;assert(f&&!fseek(f,0,SEEK_END));n=ftell(f);assert(n>0&&n<20*1024*1024&&!fseek(f,0,SEEK_SET));*size=(size_t)n;p=malloc(*size);assert(p&&fread(p,1,*size,f)==*size&&!fclose(f));return p;}
int main(int argc,char **argv){
 static const unsigned codes[]={0x97f3,0x4e50,0x6536,0x85cf,0x4e0b,0x8f7d,0x7e41,0x9ad4,0x65e5,0x672c,0x8a9e,0x304b,0x306a,0x30ab,0x30ca,'Q','Q',0xe9};
 unsigned char *old,*current;size_t old_size,size;stbtt_fontinfo original,derivative;unsigned i,j;FILE *f;
 assert(argc==4);old=load(argv[1],&old_size);current=load(argv[2],&size);assert(size==QQ_FONT_BYTES&&size<old_size/4);
 assert(qq_ui_font(current,size)==0&&qq_ui_font(current,size-1)==-1&&qq_ui_font(old,old_size)==-1);
 assert(stbtt_InitFont(&original,old,0)&&stbtt_InitFont(&derivative,current,0));memset(sheet,255,sizeof(sheet));
 for(j=0;j<4;j++){
  float old_scale=stbtt_ScaleForPixelHeight(&original,11.0f+j*4),new_scale=stbtt_ScaleForPixelHeight(&derivative,11.0f+j*4);
  for(i=0;i<sizeof(codes)/sizeof(codes[0]);i++){
   int a,b,c,d,x1,y1,x2,y2,w1,h1,w2,h2;unsigned char *one,*two;
   assert(stbtt_FindGlyphIndex(&derivative,(int)codes[i])>0);
   stbtt_GetCodepointHMetrics(&original,(int)codes[i],&a,&b);stbtt_GetCodepointHMetrics(&derivative,(int)codes[i],&c,&d);assert(a==c&&b==d);
   one=stbtt_GetCodepointBitmap(&original,0,old_scale,(int)codes[i],&w1,&h1,&x1,&y1);
   two=stbtt_GetCodepointBitmap(&derivative,0,new_scale,(int)codes[i],&w2,&h2,&x2,&y2);
   assert(one&&two&&w1==w2&&h1==h2&&x1==x2&&y1==y2&&!memcmp(one,two,(size_t)w1*h1));
   if(j==3){int x,y;for(y=0;y<h2;y++)for(x=0;x<w2;x++){int px=8+(int)i*25+x+x2,py=40+y+y2;if(px>=0&&px<480&&py>=0&&py<120){unsigned at=(unsigned)(py*480+px)*3;sheet[at]=sheet[at+1]=sheet[at+2]=(unsigned char)(255-two[y*w2+x]);}}}
   stbtt_FreeBitmap(one,0);stbtt_FreeBitmap(two,0);
  }
 }
 {int w,h,x,y;unsigned char *missing=stbtt_GetGlyphBitmap(&derivative,0,stbtt_ScaleForPixelHeight(&derivative,22),0,&w,&h,&x,&y);assert(missing&&w>0&&h>0);stbtt_FreeBitmap(missing,0);}
 f=fopen(argv[3],"wb");assert(f&&fprintf(f,"P6\n480 120\n255\n")>0&&fwrite(sheet,1,sizeof(sheet),f)==sizeof(sheet)&&!fclose(f));
 free(old);free(current);puts("Subset font accepted; Chinese/Traditional/Japanese/Latin raster and metrics match original; fallback visible");return 0;
}
