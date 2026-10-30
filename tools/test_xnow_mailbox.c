#include "../runtime/platform/espnow/xnow_mailbox.h"
#include "../runtime/platform/espnow/xnow_frame.h"
#include <assert.h>
#include <stdio.h>
struct mock {uint8_t data[92];int fail_offset,change_sequence,write_count;uint32_t last_write;};
static int read_word(void *p,uint32_t offset,uint32_t *out) {
    struct mock *m=p;assert(!(offset&3)&&offset+4<=sizeof(m->data));
    if(m->change_sequence && offset==84){xnow_put32(m->data+16,4);m->change_sequence=0;}
    *out=xnow_le32(m->data+offset);return 0;
}
static int write_word(void *p,uint32_t offset,uint32_t value) {
    struct mock *m=p;assert(!(offset&3)&&offset+4<=sizeof(m->data));
    assert(offset==4 || (offset>=20&&offset<52));
    m->write_count++;m->last_write=offset;
    if((int)offset==m->fail_offset)return -1;
    xnow_put32(m->data+offset,value);return 0;
}
int main(void) {
    struct mock memory={{0},-1,0,0,0};struct xnow_word_io io={&memory,read_word,write_word};
    struct xnow_mailbox link;struct xnow_received received;uint8_t packet[32];size_t n;
    assert(!xnow_encode(packet,32,XNOW_PING,42,0x12345678,"0123456789abcdef",16,&n)&&n==32);
    assert(xnow_mailbox_open(&link,&io)==XNOW_IDENTITY);xnow_put32(memory.data,XNOW_MAILBOX_MAGIC);
    assert(xnow_mailbox_open(&link,&io)==XNOW_OK);
    memory.fail_offset=24;assert(xnow_mailbox_send(&link,packet)==XNOW_IO);assert(xnow_le32(memory.data+4)==0);
    memory.fail_offset=-1;assert(xnow_mailbox_send(&link,packet)==XNOW_OK);assert(memory.last_write==4&&xnow_le32(memory.data+4)==1);
    assert(!memcmp(memory.data+20,packet,32));assert(xnow_mailbox_send(&link,packet)==XNOW_PENDING);
    assert(xnow_mailbox_tx_status(&link)==XNOW_PENDING);xnow_put32(memory.data+8,1);
    assert(xnow_mailbox_tx_status(&link)==XNOW_OK);xnow_put32(memory.data+12,0xffffffff);
    assert(xnow_mailbox_tx_status(&link)==XNOW_RADIO_REJECTED);
    memory.fail_offset=4;assert(xnow_mailbox_send(&link,packet)==XNOW_UNCERTAIN);
    memcpy(memory.data+52,packet,32);memset(memory.data+84,0x22,6);xnow_put32(memory.data+16,1);
    assert(xnow_mailbox_receive(&link,&received)==XNOW_AGAIN);xnow_put32(memory.data+16,2);
    memory.change_sequence=1;assert(xnow_mailbox_receive(&link,&received)==XNOW_AGAIN);
    assert(xnow_mailbox_receive(&link,&received)==XNOW_OK);assert(received.missed==1&&!memcmp(received.packet,packet,32));
    assert(xnow_mailbox_receive(&link,&received)==XNOW_AGAIN);
    xnow_put32(memory.data,0);assert(xnow_mailbox_send(&link,packet)==XNOW_IDENTITY);
    puts("XNOW mailbox: identity, publication ordering, failure, pending and torn snapshot checks passed");return 0;
}
