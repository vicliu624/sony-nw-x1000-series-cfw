#include "preference.h"
int hb_language_parse(const char*s,unsigned n,int original){
 if(!s)return original;
 if(n==3&&s[2]=='\n')n=2;
 if(n==2&&s[0]=='e'&&s[1]=='n')return HB_LANGUAGE_ENGLISH;
 if(n==2&&s[0]=='j'&&s[1]=='p')return HB_LANGUAGE_JAPANESE;
 return original;
}
