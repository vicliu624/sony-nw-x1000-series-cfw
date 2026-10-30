/* PC-only preview and memory-boundary check of the exact device renderer. */
#include "../runtime/platform/espnow/cardputer-chat/chat_ui.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
struct Guarded {uint16_t before[8],pixels[240*135],after[8];};
static Guarded frame;
int main(int argc,char **argv){
    for(unsigned i=0;i<8;i++)frame.before[i]=frame.after[i]=0xa55a;
    xnow_ui::Message messages[]={{"Hello from X1060.",0,1},{"Cardputer here!",1,1},{"Let's test both ways.",0,1}};
    char maximum[97];memset(maximum,'W',96);maximum[96]=0;
    xnow_ui::Message longMessage[]={{maximum,1,2}};
    xnow_ui::render(frame.pixels,longMessage,1,maximum,13,true,true,false,"NO PEER ACK");
    for(unsigned i=0;i<8;i++)assert(frame.before[i]==0xa55a&&frame.after[i]==0xa55a);
    bool empty=argc>1&&!strcmp(argv[1],"empty");
    xnow_ui::render(frame.pixels,messages,empty?0:3,empty?"":"Hello Walkman",8,!empty,true,false,
                    empty?"WAITING FOR X1060":"PEER CONFIRMED");
    for(unsigned i=0;i<8;i++)assert(frame.before[i]==0xa55a&&frame.after[i]==0xa55a);
    return fwrite(frame.pixels,2,240*135,stdout)==240*135?0:1;
}
