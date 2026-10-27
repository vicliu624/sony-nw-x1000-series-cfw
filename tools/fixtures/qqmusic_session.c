#include "../../runtime/apps/qqmusic/qqmusic_session.h"
#include <assert.h>
#include <stdint.h>
int main(void) {
 struct qq_session s; uint32_t old;
 qq_session_init(&s);
 assert(qq_session_event(&s,0,QQ_VERIFIED,0)<0);
 assert(qq_session_begin(&s,100,1000)==0); old=s.generation;
 assert(qq_session_event(&s,old,QQ_VERIFIED,101)<0);
 assert(qq_session_event(&s,old,QQ_SCANNED,102)==0);
 assert(qq_session_event(&s,old,QQ_WAITING,103)==0&&s.state==QQ_QR_SCANNED);
 assert(qq_session_event(&s,old,QQ_AUTHORIZED,104)==0&&s.state!=QQ_READY);
 assert(qq_session_event(&s,old,QQ_VERIFIED,105)<0);
 assert(qq_session_event(&s,old,QQ_EXCHANGED,106)==0&&s.state!=QQ_READY);
 assert(qq_session_event(&s,old,QQ_VERIFIED,107)==0&&s.state==QQ_READY);
 assert(qq_session_tick(&s,99999)==0&&s.state==QQ_READY);
 assert(qq_session_begin(&s,200,1000)==0);
 assert(qq_session_event(&s,old,QQ_AUTHORIZED,201)<0);
 qq_session_cancel(&s);
 assert(qq_session_event(&s,s.generation,QQ_AUTHORIZED,202)<0);
 assert(qq_session_begin(&s,300,100)==0);
 assert(qq_session_event(&s,s.generation,QQ_AUTHORIZED,400)<0&&s.state==QQ_EXPIRED);
 assert(qq_session_begin(&s,500,100)==0);
 assert(qq_session_event(&s,s.generation,QQ_NETWORK_ERROR,501)==0&&s.state==QQ_FAILED);
 assert(qq_session_begin(&s,600,100)==0);
 assert(qq_session_event(&s,s.generation,QQ_DENIED,601)==0&&s.state==QQ_FAILED);
 assert(qq_session_begin(&s,700,100)==0);
 assert(qq_session_event(&s,s.generation,QQ_QR_EXPIRED,701)==0&&s.state==QQ_EXPIRED);
 assert(qq_session_begin(&s,UINT64_MAX,100)<0);
 assert(qq_session_begin(&s,0,0)<0);
 assert(qq_session_begin(&s,0,600001)<0);
 s.generation=UINT32_MAX;
 assert(qq_session_begin(&s,0,100)<0);
 assert(qq_qr_token((const unsigned char *)"abc",3)==108966u);
 assert(qq_qr_token((const unsigned char *)"",0)==0);
 return 0;
}
