#include "https_url.h"
#include <string.h>
static char lower(char c){return c>='A'&&c<='Z'?(char)(c+32):c;}
static int hex(char c){c=lower(c);return (c>='0'&&c<='9')||(c>='a'&&c<='f');}
int hb_https_url_parse(const char *input,struct hb_https_url *out){
 if(!input||!out)return -1;
 struct hb_https_url value={0};unsigned position=0;
 const char *scheme="https://";
 for(unsigned i=0;i<8;i++)if(!input[i]||lower(input[i])!=scheme[i])return -1;
 position=8;unsigned host=0,label=0;int numeric=1;
 while(input[position]&&input[position]!=':'&&input[position]!='/'&&input[position]!='?'&&input[position]!='#'){
  char c=lower(input[position++]);
  if(c=='.'){
   if(!label||value.host[host-1]=='-')return -1;
   label=0;
  }else{
   if(!((c>='a'&&c<='z')||(c>='0'&&c<='9')||c=='-')||(!label&&c=='-')||++label>63)return -1;
   if(c<'0'||c>'9')numeric=0;
  }
  if(host==253)return -1;
  value.host[host++]=c;
 }
 if(!host||!label||value.host[host-1]=='-'||numeric)return -1;
 value.host[host]=0;value.port=443;
 if(input[position]==':'){
  position++;unsigned port=0,digits=0;
  while(input[position]>='0'&&input[position]<='9'){
   unsigned digit=(unsigned)(input[position++]-'0');if(++digits>5||port>(65535u-digit)/10u)return -1;port=port*10+digit;
  }
  if(!digits||!port)return -1;
  value.port=port;
 }
 unsigned used=0;
 if(input[position]=='/'&&input[position+1]=='/')return -1;
 if(input[position]=='?'||input[position]=='#'||!input[position])value.path[used++]='/';
 else if(input[position]!='/')return -1;
 while(input[position]&&input[position]!='#'){
  unsigned char c=(unsigned char)input[position++];
  if(c<33||c>126||c=='\\'||used==2048)return -1;
  if(c=='%'){
   if(!input[position]||!input[position+1]||!hex(input[position])||!hex(input[position+1])||used>2045)return -1;
   value.path[used++]='%';value.path[used++]=input[position++];value.path[used++]=input[position++];
  }else value.path[used++]=(char)c;
 }
 /* Fragments never reach HTTP, but reject control/non-ASCII text there too. */
 while(input[position]){unsigned char c=(unsigned char)input[position++];if(c<33||c>126)return -1;}
 value.path[used]=0;*out=value;return 0;
}
int hb_https_asset_url(char *out,unsigned capacity,const char *base,const char *prefix,const char *path){
 if(!out||!capacity||!base||!prefix||!path||!*path)return -1;
 struct hb_https_url parsed;if(hb_https_url_parse(base,&parsed))return -1;
 unsigned b=(unsigned)strlen(base),p=(unsigned)strlen(prefix),n=(unsigned)strlen(path);
 if(!b||base[b-1]!='/'||strchr(base,'?')||strchr(base,'#')||p>40||n>160||path[0]=='/'||strstr(path,".."))return -1;
 for(unsigned i=0;i<p;i++)if(!((prefix[i]>='a'&&prefix[i]<='z')||(prefix[i]>='0'&&prefix[i]<='9')||prefix[i]=='-'))return -1;
 if(b+p+n*(p?2u:1u)>=capacity)return -1;
 memcpy(out,base,b);memcpy(out+b,prefix,p);unsigned used=b+p;
 static const char hex[]="0123456789abcdef";
 for(unsigned i=0;i<n;i++){
  unsigned char c=(unsigned char)path[i];if(c<33||c>126||c=='\\'||c=='?'||c=='#'||c=='%')return -1;
  if(p){out[used++]=hex[c>>4];out[used++]=hex[c&15];}else out[used++]=(char)c;
 }
 out[used]=0;return 0;
}
