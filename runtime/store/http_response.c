#include "http_response.h"
#include <string.h>
static int fail(struct hb_http_response *h,int error){
 h->state=HB_HTTP_FAILED;h->error=error;h->body->state=HB_DOWNLOAD_FAILED;h->body->error=error;return error;
}
static char lower(char c){return c>='A'&&c<='Z'?(char)(c+32):c;}
static int eq(const char *a,unsigned n,const char *b){unsigned i=0;for(;i<n&&b[i];i++)if(lower(a[i])!=b[i])return 0;return i==n&&!b[i];}
static int token(char c){
 if((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9'))return 1;
 const char *p="!#$%&'*+-.^_`|~";for(unsigned i=0;p[i];i++)if(c==p[i])return 1;return 0;
}
static int number(const char *p,unsigned n,unsigned base,unsigned *out){
 unsigned value=0;if(!n)return -1;
 for(unsigned i=0;i<n;i++){
  unsigned v=p[i]>='0'&&p[i]<='9'?(unsigned)(p[i]-'0'):lower(p[i])>='a'&&lower(p[i])<='f'?(unsigned)(lower(p[i])-'a'+10):99;
  if(v>=base||value>(134217728u-v)/base)return -1;
  value=value*base+v;
 }*out=value;return 0;
}
static int complete_line(struct hb_http_response *h){
 char *p=h->line;unsigned n=h->used;
 if(h->state==HB_HTTP_STATUS){
  if(n<12||(!eq(p,8,"http/1.1")&&!eq(p,8,"http/1.0"))||p[8]!=' '||
    p[9]<'0'||p[9]>'9'||p[10]<'0'||p[10]>'9'||p[11]<'0'||p[11]>'9'||(n>12&&p[12]!=' '))return fail(h,HB_HTTP_STATUS_ERROR);
  h->status=(unsigned)(p[9]-'0')*100u+(unsigned)(p[10]-'0')*10u+(unsigned)(p[11]-'0');
  if(h->status!=200&&(!h->allow_redirects||(h->status!=301&&h->status!=302&&h->status!=303&&h->status!=307&&h->status!=308)))return fail(h,HB_HTTP_STATUS_ERROR);
  h->state=HB_HTTP_HEADERS;return 0;
 }
 if(h->state==HB_HTTP_CHUNK_SIZE){
  unsigned size;if(number(p,n,16,&size)||size>h->body->expected-h->body->received)return fail(h,HB_HTTP_FRAMING_ERROR);
  h->remaining=size;h->state=size?HB_HTTP_CHUNK_DATA:HB_HTTP_TRAILERS;return 0;
 }
 if(!n){
  if(h->state==HB_HTTP_HEADERS&&h->status!=200){if(!h->location[0])return fail(h,HB_HTTP_HEADER_ERROR);h->state=HB_HTTP_REDIRECT;return 0;}
  if(h->state==HB_HTTP_TRAILERS){h->state=HB_HTTP_COMPLETE;return 0;}
  if(h->has_length&&h->chunked)return fail(h,HB_HTTP_FRAMING_ERROR);
  if(h->chunked)h->state=HB_HTTP_CHUNK_SIZE;
  else if(h->has_length){h->remaining=h->body->expected;h->state=h->remaining?HB_HTTP_FIXED:HB_HTTP_COMPLETE;}
  else h->state=HB_HTTP_CLOSE;
  return 0;
 }
 unsigned colon=0;while(colon<n&&p[colon]!=':'){if(!token(p[colon]))return fail(h,HB_HTTP_HEADER_ERROR);colon++;}
 if(!colon||colon==n)return fail(h,HB_HTTP_HEADER_ERROR);
 unsigned first=colon+1,last=n;while(first<last&&(p[first]==' '||p[first]=='\t'))first++;
 while(last>first&&(p[last-1]==' '||p[last-1]=='\t'))last--;
 int length=eq(p,colon,"content-length"),transfer=eq(p,colon,"transfer-encoding"),encoding=eq(p,colon,"content-encoding");
 if(h->state==HB_HTTP_TRAILERS)return length||transfer||encoding?fail(h,HB_HTTP_FRAMING_ERROR):0;
 if(h->status!=200){
  if(eq(p,colon,"location")){
   unsigned size=last-first;
   if(h->location[0]||!size||size>=sizeof h->location)return fail(h,HB_HTTP_HEADER_ERROR);
   memcpy(h->location,p+first,size);h->location[size]=0;
   if(size<9||memcmp(h->location,"https://",8))return fail(h,HB_HTTP_HEADER_ERROR);
  }
  return 0;
 }
 if(length){
  unsigned value;if(h->has_length||number(p+first,last-first,10,&value)||value!=h->body->expected)return fail(h,HB_HTTP_FRAMING_ERROR);
  h->has_length=1;
 }else if(transfer){
  if(h->chunked||!eq(p+first,last-first,"chunked"))return fail(h,HB_HTTP_FRAMING_ERROR);
  h->chunked=1;
 }else if(encoding&&!eq(p+first,last-first,"identity"))return fail(h,HB_HTTP_FRAMING_ERROR);
 return 0;
}
int hb_http_response_init(struct hb_http_response *h,struct hb_download_stream *body){
 if(!h||!body||body->state!=HB_DOWNLOAD_ACTIVE)return HB_DOWNLOAD_INPUT;
 h->body=body;h->state=HB_HTTP_STATUS;h->used=h->header_bytes=h->wire_bytes=h->remaining=0;
 h->cr=h->has_length=h->chunked=h->error=0;h->status=0;h->allow_redirects=0;h->location[0]=0;return 0;
}
int hb_http_response_push(struct hb_http_response *h,const unsigned char *data,unsigned bytes){
 if(!h)return HB_DOWNLOAD_INPUT;
 if(h->state==HB_HTTP_FAILED)return h->error;
 if(!data&&bytes)return fail(h,HB_DOWNLOAD_INPUT);
 if(h->body->stop&&*h->body->stop)return fail(h,HB_DOWNLOAD_CANCELLED);
 unsigned limit=h->body->expected*16u+16384u;
 if(bytes>limit-h->wire_bytes)return fail(h,HB_DOWNLOAD_SIZE);
 h->wire_bytes+=bytes;
 while(bytes){
  if(h->state==HB_HTTP_REDIRECT)return 0; /* Redirect body is never payload. */
  if(h->body->stop&&*h->body->stop)return fail(h,HB_DOWNLOAD_CANCELLED);
  if(h->state==HB_HTTP_FIXED||h->state==HB_HTTP_CLOSE||h->state==HB_HTTP_CHUNK_DATA){
   unsigned n=bytes;if(h->state!=HB_HTTP_CLOSE&&n>h->remaining)n=h->remaining;
   int result=hb_download_stream_push(h->body,data,n);if(result)return fail(h,result);
   data+=n;bytes-=n;
   if(h->state!=HB_HTTP_CLOSE){h->remaining-=n;if(!h->remaining)h->state=h->state==HB_HTTP_FIXED?HB_HTTP_COMPLETE:HB_HTTP_CHUNK_CR;}
   continue;
  }
  unsigned char c=*data++;bytes--;
  if(h->state==HB_HTTP_COMPLETE||h->state==HB_HTTP_DONE)return fail(h,HB_HTTP_FRAMING_ERROR);
  if(h->state==HB_HTTP_CHUNK_CR){if(c!='\r')return fail(h,HB_HTTP_FRAMING_ERROR);h->state=HB_HTTP_CHUNK_LF;continue;}
  if(h->state==HB_HTTP_CHUNK_LF){if(c!='\n')return fail(h,HB_HTTP_FRAMING_ERROR);h->state=HB_HTTP_CHUNK_SIZE;continue;}
  if(h->state!=HB_HTTP_CHUNK_SIZE&&++h->header_bytes>(h->allow_redirects?16384u:8192u))return fail(h,HB_HTTP_HEADER_ERROR);
  if(h->cr){
   if(c!='\n')return fail(h,HB_HTTP_HEADER_ERROR);
   h->cr=0;h->line[h->used]=0;
   int result=complete_line(h);h->used=0;if(result)return result;
  }else if(c=='\r')h->cr=1;
  else{
   if(c=='\n'||(c<32&&c!='\t')||c>126||h->used==(h->allow_redirects?8192u:1024u))return fail(h,HB_HTTP_HEADER_ERROR);
   h->line[h->used++]=(char)c;
  }
 }return 0;
}
int hb_http_response_finish(struct hb_http_response *h){
 if(!h)return HB_DOWNLOAD_INPUT;
 if(h->state==HB_HTTP_FAILED)return h->error;
 if(h->state!=HB_HTTP_COMPLETE&&h->state!=HB_HTTP_CLOSE)return fail(h,HB_HTTP_TRUNCATED);
 int result=hb_download_stream_finish(h->body);if(result)return fail(h,result);
 h->state=HB_HTTP_DONE;return 0;
}
