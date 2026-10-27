#include "qqmusic_http.h"
#include "qqmusic_protocol.h"
#include <string.h>
static char lower(char c) {return c>='A'&&c<='Z'?(char)(c+32):c;}
static int same(const char *a,const char *b) {
 while(*a&&*b) if(lower(*a++)!=lower(*b++)) return 0;
 return *a==*b;
}
static int field(const char *s) {
 if(!*s) return 0;
 for(;*s;s++) if(!((*s>='a'&&*s<='z')||(*s>='A'&&*s<='Z')||(*s>='0'&&*s<='9')||*s=='-')) return 0;
 return 1;
}
static int line(const char *s,size_t n,size_t *offset,char *out,size_t cap) {
 size_t i=*offset,k=0;
 while(i<n&&i<16384) {
  unsigned char c=(unsigned char)s[i++];
  if(c=='\r') {
   if(i>=n||s[i++]!='\n') return -1;
   out[k]=0;*offset=i;return 0;
  }
  /* Field values may contain HTAB/opaque obs-text. Names and interpreted
   * values are validated separately; CR/LF framing is never relaxed. */
  if((c<32&&c!=9)||c==127||k+1>=cap) return -1;
  out[k++]=(char)c;
 }
 return -1;
}
/* Strict IMF-fixdate metadata only. Never used to set the device clock. */
static int http_date(const char *s,uint64_t *out){
 static const char *months[]={"Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"};
 static const char *weekdays[]={"Sun","Mon","Tue","Wed","Thu","Fri","Sat"};
 static const unsigned lengths[]={31,28,31,30,31,30,31,31,30,31,30,31};
 unsigned i,month,year=0,day,hour,minute,second,days=0,leap;
 if(strlen(s)!=29||s[3]!=','||s[4]!=' '||s[7]!=' '||s[11]!=' '||s[16]!=' '||s[19]!=':'||s[22]!=':'||strcmp(s+25," GMT"))return -1;
 for(i=0;i<7;i++)if(!memcmp(s,weekdays[i],3))break;
 if(i==7)return -1;
 for(month=0;month<12;month++)if(!memcmp(s+8,months[month],3))break;
 if(month==12)return -1;
 for(i=0;i<29;i++)if((i==5||i==6||(i>=12&&i<=15)||i==17||i==18||i==20||i==21||i==23||i==24)&&(s[i]<'0'||s[i]>'9'))return -1;
 for(i=12;i<=15;i++)year=year*10+(unsigned)(s[i]-'0');
 day=(unsigned)(s[5]-'0')*10+(unsigned)(s[6]-'0');hour=(unsigned)(s[17]-'0')*10+(unsigned)(s[18]-'0');
 minute=(unsigned)(s[20]-'0')*10+(unsigned)(s[21]-'0');second=(unsigned)(s[23]-'0')*10+(unsigned)(s[24]-'0');
 leap=year%4==0&&(year%100!=0||year%400==0);
 if(year<1970||year>2038||!day||day>lengths[month]+(month==1&&leap)||hour>23||minute>59||second>59)return -1;
 for(i=1970;i<year;i++)days+=365+(i%4==0&&(i%100!=0||i%400==0));
 for(i=0;i<month;i++)days+=lengths[i]+(i==1&&leap);
 *out=((uint64_t)days+day-1)*86400+hour*3600+minute*60+second;
 return *out<=2147483647ULL?0:-1;
}
int qq_http_parse_head(const char *s,size_t n,const char *host,const char *path,
 uint64_t now,struct qq_cookie_jar *jar,struct qq_http_head *out,size_t *consumed) {
 struct qq_cookie_jar staged;struct qq_http_head h;char text[2049];
 size_t offset=0;unsigned flags=0,cookies=0;int rc=-1;
 memset(&staged,0,sizeof(staged));memset(&h,0,sizeof(h));memset(text,0,sizeof(text));
 if(out) qq_secret_clear(out,sizeof(*out));
 if(consumed) *consumed=0;
 if(!s||!out||!consumed) goto done;
 if(jar) staged=*jar;
 if(line(s,n,&offset,text,sizeof(text))||strlen(text)<12||
    (strncmp(text,"HTTP/1.1 ",9)&&strncmp(text,"HTTP/1.0 ",9))) goto done;
 if(text[9]<'0'||text[9]>'9'||text[10]<'0'||text[10]>'9'||text[11]<'0'||text[11]>'9'||(text[12]&&text[12]!=' ')) goto done;
 h.status=(unsigned)(text[9]-'0')*100u+(unsigned)(text[10]-'0')*10u+(unsigned)(text[11]-'0');
 if(h.status!=200&&h.status!=301&&h.status!=302&&h.status!=303&&h.status!=307&&h.status!=308){rc=-3;goto done;}
 for(;;) {
  char *value,*end;unsigned flag=0;
  if(line(s,n,&offset,text,sizeof(text))) goto done;
  if(!*text) break;
  value=strchr(text,':');if(!value) goto done;*value++=0;
  if(!field(text)) goto done;
  while(*value==' '||*value=='\t') value++;
  end=value+strlen(value);while(end>value&&(end[-1]==' '||end[-1]=='\t')) *--end=0;
  if(same(text,"Set-Cookie")) {
   if(!jar) continue;
   if(++cookies>QQ_COOKIE_LIMIT)goto done;
   (void)qq_cookie_set(&staged,host,path,value,strlen(value),now); /* Ignore invalid/out-of-scope cookies; never widen their scope. */
   continue;
  }
  if(same(text,"Content-Length")) flag=1;
  else if(same(text,"Transfer-Encoding")) flag=2;
  else if(same(text,"Location")) flag=4;
  else if(same(text,"Content-Type")) flag=8;
  else if(same(text,"Content-Encoding")) flag=16;
  else if(same(text,"Date")){
   /* Ambiguous/invalid optional dates disable the hint, not body parsing. */
   if(flags&32){h.has_date=0;flags|=64;continue;}
   flags|=32;if(!(flags&64)&&!http_date(value,&h.server_date))h.has_date=1;
   continue;
  }
  if(flag&&(flags&flag)){rc=-5;goto done;}
  flags|=flag;
  if(flag==1) {
   const char *p=value;if(!*p) goto done;
   for(;*p;p++) {unsigned d=(unsigned)(*p-'0');if(d>9||h.length>(UINT64_MAX-d)/10) goto done;h.length=h.length*10+d;}
   h.has_length=1;
  } else if(flag==2) {
   if(!same(value,"chunked")) goto done;
   h.chunked=1;
  } else if(flag==4) {
   if(!*value||strlen(value)>=sizeof(h.location)) goto done;
   memcpy(h.location,value,strlen(value)+1);
  } else if(flag==8) {
   if(!*value||strlen(value)>=sizeof(h.content_type)) goto done;
   memcpy(h.content_type,value,strlen(value)+1);
  } else if(flag==16&&!same(value,"identity")&&h.status==200){rc=-4;goto done;}
 }
 if(offset>16384||(h.has_length&&h.chunked)||(h.status!=200&&!h.location[0])) goto done;
 /* Validate even a response with no cookies against supported HTTPS origins. */
 if(jar) {char scratch[1];struct qq_cookie_jar empty;memset(&empty,0,sizeof(empty));
  if(qq_cookie_header(&empty,host,path,now,scratch,sizeof(scratch))) goto done;}
 if(jar) *jar=staged;
 *out=h;*consumed=offset;rc=0;
done:
 qq_cookie_clear(&staged);qq_secret_clear(&h,sizeof(h));qq_secret_clear(text,sizeof(text));return rc;
}
static int append(char *out,size_t cap,size_t *used,const char *s,size_t n) {
 if(n>=cap-*used) return -1;
 memcpy(out+*used,s,n);*used+=n;out[*used]=0;return 0;
}
static int text_append(char *out,size_t cap,size_t *used,const char *s) {
 return append(out,cap,used,s,strlen(s));
}
static int bounded_text(const char *s,size_t cap,size_t *n) {
 size_t i;for(i=0;i<cap;i++) {
  unsigned char c=(unsigned char)s[i];if(!c) {*n=i;return 0;}
  if(c<33||c>126||c=='#'||c=='\\') return -1;
 }return -1;
}
static int body_text(const char *s,size_t cap,size_t *n) {
 size_t i;for(i=0;i<cap;i++) {
  unsigned char c=(unsigned char)s[i];if(!c) {*n=i;return 0;}
  if(c<32||c>126) return -1;
 }return -1;
}
static const char cover_prefix[]="/music/photo_new/T002R500x500M000";
int qq_http_album_cover_path_valid(const char *path){
 size_t i,n,prefix=sizeof(cover_prefix)-1;if(!path)return 0;
 for(n=0;n<prefix+64+5&&path[n];n++){}
 if(n<=prefix+4||n>prefix+64+4||strncmp(path,cover_prefix,prefix)||strcmp(path+n-4,".jpg"))return 0;
 for(i=prefix;i<n-4;i++)if(!((path[i]>='a'&&path[i]<='z')||(path[i]>='A'&&path[i]<='Z')||(path[i]>='0'&&path[i]<='9')))return 0;
 return 1;
}
int qq_build_album_cover(struct qq_request *r,const char *mid){
 size_t i,n;if(!r)return -1;qq_secret_clear(r,sizeof(*r));if(!mid)return -1;
 for(n=0;n<=64&&mid[n];n++)if(!((mid[n]>='a'&&mid[n]<='z')||(mid[n]>='A'&&mid[n]<='Z')||(mid[n]>='0'&&mid[n]<='9')))return -1;
 if(!n||n>64)return -1;
 i=sizeof(cover_prefix)-1;memcpy(r->path,cover_prefix,i);memcpy(r->path+i,mid,n);memcpy(r->path+i+n,".jpg",5);
 r->host="y.gtimg.cn";r->method="GET";r->album_cover=1;return 0;
}
int qq_http_request_wire(const struct qq_request *r,const struct qq_cookie_jar *jar,
 uint64_t now,char *out,size_t cap,size_t *bytes) {
 char cookie[4097],path[2049],length[12];size_t used=0,pn,bn,q;int rc=-1;
 memset(cookie,0,sizeof(cookie));memset(path,0,sizeof(path));memset(length,0,sizeof(length));
 if(bytes) *bytes=0;
 if(!out||!cap) return -1;
 qq_secret_clear(out,cap);
 if(!r||!jar||!bytes||!r->host||!r->method||
    (strcmp(r->method,"GET")&&strcmp(r->method,"POST"))||
    bounded_text(r->path,sizeof(r->path),&pn)||!pn||r->path[0]!='/'||r->path[1]=='/'||
    body_text(r->body,sizeof(r->body),&bn)||r->json_body>1||r->qimei>1||r->anonymous_session>1||r->album_cover>1||r->qimei+r->anonymous_session+r->album_cover>1||(!strcmp(r->method,"GET")&&bn)) goto wire_done;
 for(q=0;q<pn&&r->path[q]!='?';q++) path[q]=r->path[q];
 if(r->qimei){
  size_t i;uint64_t timestamp=0;
  if(strcmp(r->host,"api.tencentmusic.com")||strcmp(r->path,"/tme/trpc/proxy")||strcmp(r->method,"POST")||!r->json_body||!bn||r->cookie[0])goto wire_done;
  for(i=0;i<sizeof(r->qimei_time)&&r->qimei_time[i];i++){
   unsigned digit=(unsigned)(r->qimei_time[i]-'0');if(digit>9||timestamp>(UINT64_MAX-digit)/10)goto wire_done;timestamp=timestamp*10+digit;
  }
  if(!i||i==sizeof(r->qimei_time)||!timestamp||(timestamp>now?timestamp-now:now-timestamp)>60)goto wire_done;
  for(i=0;i<32;i++)if(!((r->qimei_sign[i]>='0'&&r->qimei_sign[i]<='9')||(r->qimei_sign[i]>='a'&&r->qimei_sign[i]<='f')))goto wire_done;
  if(r->qimei_sign[32])goto wire_done;
 }else if(r->anonymous_session){
  if(strcmp(r->host,"u.y.qq.com")||strcmp(r->path,"/cgi-bin/musicu.fcg")||strcmp(r->method,"POST")||!r->json_body||!bn||r->cookie[0])goto wire_done;
 }else if(r->album_cover){
  if(strcmp(r->host,"y.gtimg.cn")||strcmp(r->method,"GET")||r->json_body||bn||r->cookie[0]||!qq_http_album_cover_path_valid(r->path))goto wire_done;
 }else if(qq_cookie_header(jar,r->host,path,now,cookie,sizeof(cookie))) goto wire_done;
#define ADD(s) do {if(text_append(out,cap,&used,(s))) goto wire_done;} while(0)
 ADD(r->method);ADD(" ");ADD(r->path);ADD(" HTTP/1.1\r\nHost: ");ADD(r->host);
 if(r->qimei){
  ADD("\r\nUser-Agent: QQMusic\r\nmethod: GetQimei\r\nservice: trpc.tme_datasvr.qimeiproxy.QimeiProxy\r\nappid: qimei_qq_android\r\nsign: ");ADD(r->qimei_sign);ADD("\r\ntimestamp: ");ADD(r->qimei_time);ADD("\r\n");
 }else ADD("\r\nUser-Agent: WalkmanMate-X1060/0.1\r\n");
 ADD("Accept: */*\r\nAccept-Encoding: identity\r\nConnection: close\r\n");
 if(!strcmp(r->host,"ssl.ptlogin2.qq.com")||!strcmp(r->host,"ssl.ptlogin2.graph.qq.com")) ADD("Referer: https://xui.ptlogin2.qq.com/\r\n");
 if(cookie[0]) {ADD("Cookie: ");ADD(cookie);ADD("\r\n");}
 if(!strcmp(r->method,"POST")) {
  size_t v=bn,i=sizeof(length)-1;
  do {length[--i]=(char)('0'+v%10);v/=10;} while(v);
  ADD(r->json_body?"Content-Type: application/json\r\nContent-Length: ":"Content-Type: application/x-www-form-urlencoded\r\nContent-Length: ");ADD(length+i);ADD("\r\n");
 }
 ADD("\r\n");if(append(out,cap,&used,r->body,bn)) goto wire_done;
 *bytes=used;rc=0;
#undef ADD
wire_done:
 qq_secret_clear(cookie,sizeof(cookie));qq_secret_clear(path,sizeof(path));qq_secret_clear(length,sizeof(length));
 if(rc<0) qq_secret_clear(out,cap);
 return rc;
}
