#include "qqmusic_stock_path.h"
#include <string.h>
extern int sony_snprintf(char *,size_t,const char *,...) __asm__("snprintf");
static int component(const char *s,size_t n){size_t i;if(!n||n>255||s[n-1]=='.'||s[n-1]==' '||(n==1&&s[0]=='.')||(n==2&&!memcmp(s,"..",2)))return -1;
 for(i=0;i<n;i++){unsigned char c=(unsigned char)s[i];if(c<32||c==127||strchr("\\:*?\"<>|",c))return -1;}return 0;
}
static int root(const char *s,unsigned *depth){size_t i=15,start;unsigned n=0;
 if(!s||strncmp(s,"/contents/MUSIC",15)||(s[15]&&s[15]!='/'))return -1;
 while(s[i]){if(i>=2048||s[i++]!='/')return -1;start=i;while(s[i]&&s[i]!='/'){if(++i>2048)return -1;}if(component(s+start,i-start)||++n>5)return -1;}
 *depth=n;return 0;
}
int qq_stock_music_root(const char *s){unsigned depth;return root(s,&depth);}
int qq_stock_music_path(const char *s,const struct qq_export_plan *plan,char *out,size_t capacity){
 size_t i=0,start;unsigned base,parts=0;int n;
 if(out&&capacity)out[0]=0;
 if(!out||!capacity||!plan||plan->version!=1||!memchr(plan->relative,0,sizeof(plan->relative))||root(s,&base))return -1;
 do{start=i;while(plan->relative[i]&&plan->relative[i]!='/')i++;if(component(plan->relative+start,i-start))return -1;parts++;if(!plan->relative[i])break;i++;}while(1);
 if(parts!=3||base+parts>8||i<4||strcmp(plan->relative+i-4,".mp3"))return -1;
 n=sony_snprintf(out,capacity,"%s/%s",s,plan->relative);if(n<0||(size_t)n>=capacity){out[0]=0;return -1;}return 0;
}
