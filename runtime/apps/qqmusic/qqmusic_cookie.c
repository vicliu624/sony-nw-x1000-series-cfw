#include "qqmusic_cookie.h"
#include "qqmusic_protocol.h"
#include <string.h>
static char lower(char c) { return c>='A'&&c<='Z'?(char)(c+32):c; }
static int same(const char *a,const char *b) {
 while(*a&&*b) if(lower(*a++)!=lower(*b++)) return 0;
 return *a==*b;
}
static int origin_ok(const char *s) {
 return s&&(!strcmp(s,"ssl.ptlogin2.qq.com")||!strcmp(s,"ssl.ptlogin2.graph.qq.com")||
 !strcmp(s,"graph.qq.com")||!strcmp(s,"y.qq.com")||!strcmp(s,"u.y.qq.com"));
}
static int domain_match(const char *host,const char *domain) {
 size_t h=strlen(host), d=strlen(domain);
 return h>=d&&!strcmp(host+h-d,domain)&&(h==d||host[h-d-1]=='.');
}
static int copy(char *out,size_t cap,const char *s,size_t n) {
 if(n>=cap) return -1;
 memcpy(out,s,n); out[n]=0; return 0;
}
static int name_ok(const char *s) {
 if(!*s) return 0;
 while(*s) {
  unsigned char c=(unsigned char)*s++;
  if(!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='_'||c=='-')) return 0;
 }
 return 1;
}
static int value_ok(const char *s) {
 while(*s) {
  unsigned char c=(unsigned char)*s++;
  if(c<33||c>126||c=='"'||c==','||c==';'||c=='\\') return 0;
 }
 return 1;
}
static int leap(unsigned y) { return y%4==0&&(y%100!=0||y%400==0); }
/* RFC 6265 cookie-date tokens: HTTP cookies also use legacy hyphenated and
 * two-digit-year dates. This is deliberately not an HTTP Date header parser. */
static int delimiter(unsigned char c){return c==9||(c>=32&&c<=47)||(c>=59&&c<=64)||(c>=91&&c<=96)||(c>=123&&c<=126);}
static int date_number(const char *s,size_t n,unsigned maximum,unsigned *out,size_t *used){
 size_t k=0;unsigned value=0;
 while(k<n&&s[k]>='0'&&s[k]<='9'){if(k==maximum)return -1;value=value*10+(unsigned)(s[k]-'0');k++;}
 if(!k)return -1;
 *out=value;*used=k;return 0;
}
static int date_time(const char *s,size_t n,unsigned *h,unsigned *m,unsigned *sec){
 size_t a,b,c;
 if(date_number(s,n,2,h,&a)||a>=n||s[a]!=':')return -1;
 a++;if(date_number(s+a,n-a,2,m,&b)||a+b>=n||s[a+b]!=':')return -1;
 a+=b+1;if(date_number(s+a,n-a,2,sec,&c))return -1;
 return 0;
}
static int date(const char *s,uint64_t *out){
 static const char *months[]={"jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"};
 static const unsigned lengths[]={31,28,31,30,31,30,31,31,30,31,30,31};
 unsigned flags=0,d=0,y=0,h=0,m=0,sec=0,mo=0,days=0,i;size_t at=0;
 while(s[at]){
  size_t start,n,used;unsigned value;
  while(s[at]&&delimiter((unsigned char)s[at]))at++;
  start=at;while(s[at]&&!delimiter((unsigned char)s[at]))at++;n=at-start;if(!n)break;
  if(!(flags&1)&&!date_time(s+start,n,&h,&m,&sec)){flags|=1;continue;}
  if(!(flags&2)&&!date_number(s+start,n,2,&value,&used)){d=value;flags|=2;continue;}
  if(!(flags&4)&&n>=3){
   for(i=0;i<12;i++)if(lower(s[start])==months[i][0]&&lower(s[start+1])==months[i][1]&&lower(s[start+2])==months[i][2])break;
   if(i<12){mo=i;flags|=4;continue;}
  }
  if(!(flags&8)&&!date_number(s+start,n,4,&value,&used)&&used>=2){y=value;flags|=8;}
 }
 if(flags!=15)return -1;
 if(y>=70&&y<=99)y+=1900;else if(y<=69)y+=2000;
 if(y<1601||y>9999||h>23||m>59||sec>59||!d||d>lengths[mo]+(mo==1&&leap(y)))return -1;
 if(y<1970){*out=0;return 0;}
 for(i=1970;i<y;i++)days+=365u+(unsigned)leap(i);
 for(i=0;i<mo;i++)days+=lengths[i]+(i==1&&leap(y));
 *out=((uint64_t)days+d-1)*86400u+h*3600u+m*60u+sec;return 0;
}
static int path_ok(const char *s) {
 if(!s||s[0]!='/') return 0;
 for(;*s;s++) if((unsigned char)*s<33||(unsigned char)*s>126||*s=='?'||*s=='#'||*s=='\\') return 0;
 return 1;
}
static int path_match(const char *request,const char *cookie) {
 size_t n=strlen(cookie);
 return !strncmp(request,cookie,n)&&(!request[n]||cookie[n-1]=='/'||request[n]=='/');
}
void qq_cookie_clear(struct qq_cookie_jar *j) { if(j) qq_secret_clear(j,sizeof(*j)); }
int qq_cookie_set(struct qq_cookie_jar *jar,const char *origin,const char *path,
 const char *input,size_t n,uint64_t now) {
 char line[2049],*p,*next,*eq; struct qq_cookie c;
 unsigned attrs=0; int rc=-1,slot=-1; size_t i;
 uint64_t age=0; int has_age=0,remove=0;
 memset(&c,0,sizeof(c)); memset(line,0,sizeof(line));
 if(!jar||!origin_ok(origin)||!path_ok(path)||!input||!n||n>=sizeof(line)||memchr(input,0,n)) goto done;
 for(i=0;i<n;i++) if(((unsigned char)input[i]<32&&input[i]!=9)||(unsigned char)input[i]>126) goto done;
 memcpy(line,input,n); p=line; next=strchr(p,';'); if(next) *next++=0;
 eq=strchr(p,'='); if(!eq) goto done; *eq++=0;
 {size_t length=strlen(p);while(length&&(p[length-1]==' '||p[length-1]=='\t'))p[--length]=0;
  while(*eq==' '||*eq=='\t')eq++;
  length=strlen(eq);while(length&&(eq[length-1]==' '||eq[length-1]=='\t'))eq[--length]=0;}
 if(copy(c.name,sizeof(c.name),p,strlen(p))||copy(c.value,sizeof(c.value),eq,strlen(eq))||!name_ok(c.name)||!value_ok(c.value)) goto done;
 if(copy(c.domain,sizeof(c.domain),origin,strlen(origin))) goto done;
 c.host_only=1; c.used=1;
 { const char *last=strrchr(path,'/'); size_t length=(size_t)(last-path);
   if(!length) strcpy(c.path,"/"); else if(copy(c.path,sizeof(c.path),path,length)) goto done; }
 while(next) {
  unsigned bit=0; p=next; next=strchr(p,';'); if(next) *next++=0;
  while(*p==' '||*p=='\t') p++;
  { size_t len=strlen(p); while(len&&(p[len-1]==' '||p[len-1]=='\t')) p[--len]=0; }
  if(!*p) continue;
  eq=strchr(p,'='); if(eq) *eq++=0;
  {size_t length=strlen(p);while(length&&(p[length-1]==' '||p[length-1]=='\t'))p[--length]=0;
   if(eq){while(*eq==' '||*eq=='\t')eq++;length=strlen(eq);while(length&&(eq[length-1]==' '||eq[length-1]=='\t'))eq[--length]=0;}}
  if(same(p,"Domain")) bit=1;
  else if(same(p,"Path")) bit=2;
  else if(same(p,"Secure")) bit=4;
  else if(same(p,"Max-Age")) bit=8;
  else if(same(p,"Expires")) bit=16;
  else if(same(p,"HttpOnly")) bit=32;
  else if(same(p,"SameSite")) bit=64;
  else continue; /* Unknown attributes cannot widen scope. */
  if(attrs&bit) goto done;
  attrs|=bit;
  if(bit==1) {
   size_t k; if(!eq||!*eq) goto done; if(*eq=='.') eq++;
   if(copy(c.domain,sizeof(c.domain),eq,strlen(eq))) goto done;
   for(k=0;c.domain[k];k++) {
    c.domain[k]=lower(c.domain[k]);
    if(!((c.domain[k]>='a'&&c.domain[k]<='z')||(c.domain[k]>='0'&&c.domain[k]<='9')||c.domain[k]=='.'||c.domain[k]=='-')) goto done;
   }
   if(!domain_match(origin,c.domain)||!domain_match(c.domain,"qq.com")) goto done;
   c.host_only=0;
  } else if(bit==2) {
   if(!eq||!path_ok(eq)||copy(c.path,sizeof(c.path),eq,strlen(eq))) goto done;
  } else if(bit==4||bit==32) {
   if(eq) goto done;
   if(bit==4) c.secure=1;
  } else if(bit==8) {
   size_t k=0; int negative=0;
   if(!eq||!*eq) goto done;
   if(eq[k]=='-') {negative=1;k++;}
   if(!eq[k]) goto done;
   for(;eq[k];k++) {
    unsigned d=(unsigned)(eq[k]-'0');
    if(d>9||age>(UINT64_MAX-d)/10) goto done;
    age=age*10+d;
   }
   has_age=1; remove=negative||!age;
  } else if(bit==16) {
   if(eq&&!date(eq,&c.expires))c.persistent=1; /* Invalid Expires is ignored, as by browsers. */
  } else if(bit==64 && (!eq||(!same(eq,"Lax")&&!same(eq,"Strict")&&!same(eq,"None")))) goto done;
 }
 if(has_age) {
  if(!remove&&now>UINT64_MAX-age) goto done;
  c.expires=remove?0:now+age; c.persistent=1;
 }
 if(c.persistent&&c.expires<=now) remove=1;
 for(i=0;i<QQ_COOKIE_LIMIT;i++) {
  const struct qq_cookie *old=&jar->entries[i];
  if(old->used&&!strcmp(old->name,c.name)&&!strcmp(old->domain,c.domain)&&!strcmp(old->path,c.path)) {slot=(int)i;break;}
 }
 if(slot<0&&remove) {rc=0;goto done;}
 if(slot<0) for(i=0;i<QQ_COOKIE_LIMIT;i++) if(!jar->entries[i].used||
    (jar->entries[i].persistent&&jar->entries[i].expires<=now)) {slot=(int)i;break;}
 if(slot<0) goto done;
 qq_secret_clear(&jar->entries[slot],sizeof(c));
 if(!remove) jar->entries[slot]=c;
 rc=0;
done:
 qq_secret_clear(&c,sizeof(c)); qq_secret_clear(line,sizeof(line)); return rc;
}
int qq_cookie_header(const struct qq_cookie_jar *jar,const char *host,const char *path,
 uint64_t now,char *out,size_t cap) {
 size_t used=0,i,j; unsigned selected[QQ_COOKIE_LIMIT]={0}; int rc=-1;
 if(!out||!cap) return -1;
 qq_secret_clear(out,cap);
 if(!jar||!origin_ok(host)||!path_ok(path)) return -1;
 for(i=0;i<QQ_COOKIE_LIMIT;i++) {
  const struct qq_cookie *c=&jar->entries[i]; size_t a,b,need;
  if(!c->used||(c->persistent&&c->expires<=now)||
     (c->host_only?strcmp(host,c->domain)!=0:!domain_match(host,c->domain))||!path_match(path,c->path)) continue;
  for(j=0;j<i;j++) if(selected[j]&&!strcmp(c->name,jar->entries[j].name)) goto done;
  a=strlen(c->name); b=strlen(c->value); need=a+b+1+(used?2:0);
  if(need>=cap-used) goto done;
  if(used) {out[used++]=';';out[used++]=' ';}
  memcpy(out+used,c->name,a); used+=a; out[used++]='=';
  memcpy(out+used,c->value,b);used+=b;out[used]=0;selected[i]=1;
 }
 rc=0;
done:
 if(rc<0) qq_secret_clear(out,cap);
 return rc;
}
