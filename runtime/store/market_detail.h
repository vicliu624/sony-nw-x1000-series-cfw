#ifndef HB_MARKET_DETAIL_H
#define HB_MARKET_DETAIL_H
#include "semver.h"
#include "remote_catalog.h"
#include "ui_loop.h"
#include "cleanup_plan.h"
#include "../native/app_list_art.h"
#include "../native/frontend.h"
#include <sys/stat.h>
#include <errno.h>
#include <stdio.h>
#include "target_abi.h"
enum hb_market_status {HB_MARKET_NEW,HB_MARKET_CURRENT,HB_MARKET_UPDATE,HB_MARKET_DOWNGRADE,HB_MARKET_CONFLICT,HB_MARKET_INVALID,HB_MARKET_LEGACY};
struct hb_market_local {enum hb_market_status status;int present;char version[33];unsigned char identity[32];};
static inline int hb_market_inspect(const char *apps,const struct hb_package_download_plan *plan,volatile int *stop,struct hb_bundle *scratch,struct hb_market_local *local){
 char path[512];struct stat st;memset(local,0,sizeof *local);
 if(snprintf(path,sizeof path,"%s/%s",apps,plan->bundle.package.id)>=(int)sizeof path)return -1;
 const char *markers[]={".install-",".backup-",".pending-",".committed-",".cleanup-"};
 for(unsigned i=0;i<5;i++){
  char marker[512];if(snprintf(marker,sizeof marker,"%s/%s%s",apps,markers[i],plan->bundle.package.id)>=(int)sizeof marker)return -1;
  if(!lstat(marker,&st)){local->present=!lstat(path,&st);local->status=HB_MARKET_INVALID;return 0;}
  if(errno!=ENOENT)return -1;
 }
 if(lstat(path,&st)){if(errno==ENOENT){local->status=HB_MARKET_NEW;return 0;}return -1;}
 local->present=1;
 if(!S_ISDIR(st.st_mode)||hb_bundle_check(path,plan->bundle.package.id,stop,scratch)||hb_bundle_identity(scratch,local->identity)){local->status=HB_MARKET_INVALID;return 0;}
 strcpy(local->version,scratch->package.version);int compare;
 if(hb_semver_compare(plan->bundle.package.version,local->version,&compare)){local->status=HB_MARKET_LEGACY;return 0;}
 local->status=compare>0?HB_MARKET_UPDATE:compare<0?HB_MARKET_DOWNGRADE:memcmp(local->identity,plan->identity,32)?HB_MARKET_CONFLICT:HB_MARKET_CURRENT;
 return 0;
}
static inline const char *hb_market_status_name(enum hb_market_status s){
 switch(s){case HB_MARKET_NEW:return "Not installed";case HB_MARKET_CURRENT:return "Installed / up to date";case HB_MARKET_UPDATE:return "Update available";case HB_MARKET_DOWNGRADE:return "Newer version installed";case HB_MARKET_CONFLICT:return "Same version / different build";case HB_MARKET_INVALID:return "Local files need attention";default:return "Legacy version / cannot compare";}
}
static inline const char *hb_market_action(enum hb_market_status s){return s==HB_MARKET_NEW?"Download":s==HB_MARKET_CURRENT?"Reinstall":s==HB_MARKET_UPDATE?"Update":s==HB_MARKET_DOWNGRADE?"Downgrade":"Unavailable";}
/* Word wrapping is bounded and returns the total line count, including pages. */
static inline unsigned hb_market_paragraph(const struct hb_store_painter *p,const char *value,unsigned page){
 unsigned at=0,line=0;
 while(value&&value[at]&&at<1024){
  while(value[at]==' ')at++;
  if(!value[at])break;
  unsigned start=at,end=at,last=at;int width=0;
  while(value[end]&&end<1024){unsigned c=(unsigned char)value[end];if(c<32||c>126)c='?';int advance=hb_ui_advance[c-32];if(width+advance>212)break;width+=advance;if(value[end]==' ')last=end;end++;}
  if(value[end]&&last>start)end=last;
  if(end==start)end++;
  if(line/7==page){char text[65];unsigned n=end-start;if(n>64)n=64;memcpy(text,value+start,n);text[n]=0;hb_art_text(p,14,202+(int)(line%7)*19,212,text,HB_ART_TEXT,HB_ART_BG);}
  at=end;line++;
 }return line?line:1;
}
static inline int hb_market_detail_draw(const struct hb_remote_entry *e,const struct hb_market_local *local,unsigned tab,unsigned page,int confirm,const struct hb_store_painter *p){
 hb_art_header(p,"App details",0);p->rect(p->context,202,10,30,24,HB_ART_BG);
 const struct hb_app_art *art=hb_art_find(e->id);hb_art_icon(p,14,54,art);
 hb_art_text(p,60,54,165,e->title[0]?e->title:art->title,HB_ART_TEXT,HB_ART_BG);
 char line[80];hb_art_text(p,60,75,164,e->channel[0]?e->channel:"Legacy source",HB_ART_MUTED,HB_ART_BG);
 p->rect(p->context,12,104,104,27,tab?HB_ART_ROW:0x19e9);p->rect(p->context,124,104,104,27,tab?0x19e9:HB_ART_ROW);
 hb_art_text(p,40,108,76,"About",HB_ART_TEXT,tab?HB_ART_ROW:0x19e9);hb_art_text(p,148,108,76,"Changes",HB_ART_TEXT,tab?0x19e9:HB_ART_ROW);
 snprintf(line,sizeof line,"Installed: %s",local->present?(local->version[0]?local->version:"unverified"):"none");hb_art_text(p,14,140,214,line,HB_ART_MUTED,HB_ART_BG);
 snprintf(line,sizeof line,"Available: %s / %u KB",e->version,(e->download_bytes+1023)/1024);hb_art_text(p,14,158,214,line,HB_ART_MUTED,HB_ART_BG);
 hb_art_text(p,14,178,214,hb_market_status_name(local->status),0x6df6,HB_ART_BG);
 const char *description=e->description;
 const char *body=confirm?"This installs an older app. Back up app data first: an older version may not understand newer data. Back cancels. Confirm continues.":tab?(e->changes[0]?e->changes:"This older source does not provide version-specific release notes."):(*description?description:"This older source does not provide an app description. Package identity and hashes are still verified before installation.");
 char warning[1024];
 if(local->status>=HB_MARKET_CONFLICT){snprintf(warning,sizeof warning,"Installation blocked: check local files or select a correctly versioned package on your PC. %s",body);body=warning;}
 unsigned lines=hb_market_paragraph(p,body,page),pages=(lines+6)/7;
 hb_art_text(p,14,348,55,page?"Prev":"",HB_ART_MUTED,HB_ART_BG);snprintf(line,sizeof line,"%u / %u",page+1,pages);hb_art_text(p,100,348,60,line,HB_ART_MUTED,HB_ART_BG);hb_art_text(p,192,348,40,page+1<pages?"Next":"",HB_ART_MUTED,HB_ART_BG);
 p->rect(p->context,8,384,224,1,0x2148);hb_art_text(p,20,401,90,"Back",HB_ART_TEXT,HB_ART_BG);
 hb_art_text(p,136,401,96,confirm?"Confirm":hb_market_action(local->status),local->status<HB_MARKET_CONFLICT?0x6df6:HB_ART_MUTED,HB_ART_BG);
 return (int)pages;
}
/* 1 explicit download approval; 0 back to catalog; negative stop/UI failure. */
static inline int hb_market_detail_run(const struct hb_remote_entry *e,const struct hb_market_local *local,const struct hb_store_painter *p,const struct hb_store_ui_io *io){
 unsigned tab=0,page=0;int confirm=0,pressed=0,cancel=0,sx=0,sy=0,lx=0,ly=0;
 int pages=hb_market_detail_draw(e,local,tab,page,confirm,p);if(io->present(io->context))return -2;
 for(;;){unsigned char packet[11];int event=io->next(io->context,packet);if(event<0)return event==-1?-1:-2;if(!event)continue;if(event!=1)return -2;
  struct hb_touch t;hb_touch_decode(packet,&t);
  if(t.down){if(!pressed){sx=(int)t.x;sy=(int)t.y;cancel=0;}if(!t.in_bounds||(int)t.x-sx>12||sx-(int)t.x>12||(int)t.y-sy>12||sy-(int)t.y>12)cancel=1;lx=(int)t.x;ly=(int)t.y;pressed=1;continue;}
  if(!pressed)continue;
  pressed=0;if(cancel)continue;
  if(ly>=384){if(lx<120)return 0;if(local->status<HB_MARKET_CONFLICT){if(local->status==HB_MARKET_DOWNGRADE&&!confirm){confirm=1;page=0;}else return 1;}}
  else if(!confirm&&ly>=104&&ly<131){tab=lx>=120;page=0;}
  else if(ly>=336&&ly<378){if(lx<80&&page)page--;else if(lx>=160&&page+1<(unsigned)pages)page++;}
  pages=hb_market_detail_draw(e,local,tab,page,confirm,p);if(io->present(io->context))return -2;
 }
}
#endif
