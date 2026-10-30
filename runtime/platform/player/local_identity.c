#include "local_identity.h"
typedef char identity_capacity[(XW_MEDIA_ID_BYTES>=61u)?1:-1];
static const char all[]="moma-object:MOMA_LC;domain=DOMAINALL;type=MEDIA;id=";
static const char folders[]="moma-object:MOMA_LC;domain=FOLDERTREE;type=MEDIA;id=";

int xw_local_media_id_format(uint32_t domain,uint32_t object,struct xw_media_id *out)
{
    struct xw_media_id value={0};
    if (!out || domain>1) return XW_PLAYER_INVALID;
    const char *prefix=domain?folders:all;
    unsigned used=0,shift=28;
    while (*prefix) value.value[used++]=*prefix++;
    while (shift && !(object>>shift)) shift-=4;
    for (;;) {
        value.value[used++]="0123456789abcdef"[(object>>shift)&15u];
        if (!shift) break;
        shift-=4;
    }
    *out=value;
    return 0;
}

static unsigned prefix_bytes(const char *text,const char *prefix)
{
    unsigned n=0;
    while (prefix[n]) {if (text[n]!=prefix[n]) return 0;n++;}
    return n;
}

int xw_local_media_id_parse(const struct xw_media_id *id,uint32_t *domain,uint32_t *object)
{
    if (!id || !domain || !object || domain==object) return XW_PLAYER_INVALID;
    unsigned at=prefix_bytes(id->value,all),kind=0,n=0;
    uint32_t number=0;
    if (!at) {at=prefix_bytes(id->value,folders);kind=1;}
    if (!at) return XW_PLAYER_INVALID;
    unsigned leading_zero=id->value[at]=='0';
    while (at<XW_MEDIA_ID_BYTES && id->value[at]) {
        unsigned c=(unsigned char)id->value[at++],digit;
        if (n==8 || (leading_zero && n)) return XW_PLAYER_INVALID;
        if (c>='0' && c<='9') digit=c-'0';
        else if (c>='a' && c<='f') digit=c-'a'+10;
        else return XW_PLAYER_INVALID;
        number=(number<<4)|digit;n++;
    }
    if (!n || at==XW_MEDIA_ID_BYTES) return XW_PLAYER_INVALID;
    *domain=kind;*object=number;
    return 0;
}
