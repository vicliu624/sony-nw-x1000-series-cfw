/* Portable native C mailbox layer. No files, sockets, allocation or raw memory. */
#include "xnow_mailbox.h"
#include "xnow_frame.h"
static int get(struct xnow_mailbox *m,uint32_t offset,uint32_t *value) {
    return m->io.read(m->io.context,offset,value)?XNOW_IO:XNOW_OK;
}
static int identity(struct xnow_mailbox *m) {
    uint32_t magic;
    if(!m || !m->io.read || !m->io.write)return XNOW_ARGUMENT;
    if(get(m,0,&magic))return XNOW_IO;
    return magic==XNOW_MAILBOX_MAGIC?XNOW_OK:XNOW_IDENTITY;
}
int xnow_mailbox_open(struct xnow_mailbox *m,const struct xnow_word_io *io) {
    uint32_t sequence;int result;
    if(!m || !io || !io->read || !io->write)return XNOW_ARGUMENT;
    m->io=*io;m->last_rx=0;m->inflight=0;
    result=identity(m);if(result)return result;
    if(get(m,16,&sequence))return XNOW_IO;
    if(sequence&1)return XNOW_AGAIN;
    m->last_rx=sequence;return XNOW_OK;
}
int xnow_mailbox_send(struct xnow_mailbox *m,const uint8_t packet[XNOW_PACKET_BYTES]) {
    uint32_t request,ack,next;unsigned i;int result;struct xnow_view view;
    if(!packet || xnow_decode(packet,XNOW_PACKET_BYTES,&view))return XNOW_ARGUMENT;
    result=identity(m);if(result)return result;
    if(get(m,4,&request)||get(m,8,&ack))return XNOW_IO;
    if(request!=ack)return XNOW_PENDING;
    for(i=0;i<XNOW_PACKET_BYTES;i+=4)
        if(m->io.write(m->io.context,20+i,xnow_le32(packet+i)))return XNOW_IO;
    next=request+1;if(!next)next=1;
    m->inflight=next;
    if(m->io.write(m->io.context,4,next))return XNOW_UNCERTAIN;
    return XNOW_OK;
}
int xnow_mailbox_tx_status(struct xnow_mailbox *m) {
    uint32_t ack,status;int result=identity(m);if(result)return result;
    if(!m->inflight)return XNOW_AGAIN;
    if(get(m,8,&ack))return XNOW_IO;
    if(ack!=m->inflight)return XNOW_PENDING;
    if(get(m,12,&status))return XNOW_IO;
    return status?XNOW_RADIO_REJECTED:XNOW_OK;
}
int xnow_mailbox_receive(struct xnow_mailbox *m,struct xnow_received *out) {
    struct xnow_received snapshot;uint8_t source[8];uint32_t before,after,word;
    unsigned i;int result;struct xnow_view view;
    if(!out)return XNOW_ARGUMENT;
    result=identity(m);if(result)return result;
    if(get(m,16,&before))return XNOW_IO;
    if((before&1)||before==m->last_rx)return XNOW_AGAIN;
    for(i=0;i<32;i+=4){if(get(m,52+i,&word))return XNOW_IO;xnow_put32(snapshot.packet+i,word);}
    for(i=0;i<8;i+=4){if(get(m,84+i,&word))return XNOW_IO;xnow_put32(source+i,word);}
    if(get(m,16,&after))return XNOW_IO;
    if(before!=after || (after&1))return XNOW_AGAIN;
    if(xnow_decode(snapshot.packet,32,&view))return XNOW_IDENTITY;
    memcpy(snapshot.source,source,6);snapshot.sequence=after;
    snapshot.missed=(uint32_t)(after-m->last_rx)/2-1;
    m->last_rx=after;*out=snapshot;return XNOW_OK;
}
