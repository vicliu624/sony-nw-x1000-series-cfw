/* Bounded optional package presentation. Invalid/missing files use generic art. */
#ifndef HB_APP_PRESENTATION_H
#define HB_APP_PRESENTATION_H
#include "linux_files.h"
#include "app_list_art.h"
#define HB_PRESENTATION_BYTES 2746
struct hb_presentation {char title[49],summary[97];unsigned short pixels[1296];struct hb_app_art art;};
static inline int hb_presentation_string(const unsigned char *p,unsigned n){
 unsigned i=0;while(i<n&&p[i]){if(p[i]<32||p[i]>126)return 0;i++;}
 if(!i||i==n)return 0;
 while(i<n)if(p[i++])return 0;
 return 1;
}
static inline int hb_presentation_decode(struct hb_presentation *out,const unsigned char *data,unsigned size){
 const char *magic="HBART001";
 if(size!=HB_PRESENTATION_BYTES)return 0;
 for(unsigned i=0;i<8;i++)if(data[i]!=(unsigned char)magic[i])return 0;
 if(!hb_presentation_string(data+8,49)||!hb_presentation_string(data+57,97))return 0;
 for(unsigned i=0;i<49;i++)out->title[i]=(char)data[8+i];
 for(unsigned i=0;i<97;i++)out->summary[i]=(char)data[57+i];
 for(unsigned i=0;i<1296;i++)out->pixels[i]=(unsigned short)(data[154+i*2]|((unsigned)data[155+i*2]<<8));
 out->art.id="external";out->art.title=out->title;out->art.subtitle=out->summary;out->art.pixels=out->pixels;return 1;
}
static inline int hb_presentation_load(struct hb_presentation *out,const char *folder){
 char path[256];unsigned n=0;const char *suffix="/presentation.bin";
 while(folder[n]){if(n>=238)return 0;path[n]=folder[n];n++;}
 for(unsigned i=0;;i++){path[n+i]=suffix[i];if(!suffix[i])break;}
 if(!hb_path_is_not_link(path))return 0;
 long fd=hb_file_open_resource(path,HB_PRESENTATION_BYTES);if(fd<0)return 0;
 unsigned char data[HB_PRESENTATION_BYTES+1];unsigned used=0;int valid=1;
 while(used<sizeof data){long got=hb_file_read((int)fd,data+used,sizeof data-used);if(got<0){valid=0;break;}if(!got)break;used+=(unsigned)got;}
 if(hb_file_close((int)fd)<0)valid=0;
 return valid&&hb_presentation_decode(out,data,used);
}
#endif
