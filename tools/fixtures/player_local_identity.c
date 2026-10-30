#include "../../runtime/platform/player/local_identity.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
int main(void)
{
    static const uint32_t values[]={0,1,15,16,0x7fffffffu,0x80000000u,0xffffffffu};
    struct xw_media_id id,before;uint32_t domain,object,random=0x9181060u;
    for (unsigned kind=0;kind<2;kind++) {
        for (unsigned i=0;i<2007;i++) {
            random=random*1664525u+1013904223u;
            uint32_t value=i<7?values[i]:random;
            assert(!xw_local_media_id_format(kind,value,&id));
            char expected[XW_MEDIA_ID_BYTES];
            int n=snprintf(expected,sizeof expected,"moma-object:MOMA_LC;domain=%s;type=MEDIA;id=%lx",kind?"FOLDERTREE":"DOMAINALL",(unsigned long)value);
            assert(n>0 && n<61 && !strcmp(expected,id.value));
            domain=17;object=19;
            assert(!xw_local_media_id_parse(&id,&domain,&object));
            assert(domain==kind && object==value);
        }
    }
    static const char *invalid[]={"","1","moma-object:MOMA_LC;domain=OTHER;type=MEDIA;id=1",
        "moma-object:MOMA_LC;domain=DOMAINALL;type=META;key=2;id=1",
        "moma-object:MOMA_LC;domain=FOLDERTREE;type=MEDIA;id=",
        "moma-object:MOMA_LC;domain=DOMAINALL;type=MEDIA;id=01",
        "moma-object:MOMA_LC;domain=DOMAINALL;type=MEDIA;id=00",
        "moma-object:MOMA_LC;domain=DOMAINALL;type=MEDIA;id=FFFFFFFF",
        "moma-object:MOMA_LC;domain=DOMAINALL;type=MEDIA;id=100000000",
        "moma-object:MOMA_LC;domain=DOMAINALL;type=MEDIA;id=-1",
        "moma-object:MOMA_LC;domain=DOMAINALL;type=MEDIA;id=1 ",
        "moma-object:MOMA_LC;domain=DOMAINALL;type=MEDIA;id=0x1"};
    for (unsigned i=0;i<sizeof invalid/sizeof invalid[0];i++) {
        memset(&id,0,sizeof id);assert(strlen(invalid[i])<sizeof id.value);strcpy(id.value,invalid[i]);
        before=id;domain=17;object=19;
        assert(xw_local_media_id_parse(&id,&domain,&object)==XW_PLAYER_INVALID);
        assert(domain==17 && object==19 && !memcmp(&id,&before,sizeof id));
    }
    memset(&id,'f',sizeof id);memcpy(id.value,"moma-object:MOMA_LC;domain=DOMAINALL;type=MEDIA;id=",47);
    domain=17;object=19;assert(xw_local_media_id_parse(&id,&domain,&object)==XW_PLAYER_INVALID && domain==17 && object==19);
    before=id;assert(xw_local_media_id_format(2,1,&id)==XW_PLAYER_INVALID && !memcmp(&id,&before,sizeof id));
    assert(xw_local_media_id_parse(0,&domain,&object)==XW_PLAYER_INVALID);
    assert(xw_local_media_id_parse(&id,&domain,&domain)==XW_PLAYER_INVALID);
    puts("Local-media identity: canonical native format, 4014 round trips, malformed IDs and atomic refusal passed");
    return 0;
}
