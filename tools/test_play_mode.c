#include "../runtime/platform/player/play_mode.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
int main(void){
 uint32_t value=99;
 for(uint32_t i=0;i<4;i++)assert(!xw_player_mode_menu_index(i,&value)&&value==i);
 assert(!xw_player_mode_menu_index(5,&value)&&value==4);
 const uint32_t rejected[]={4,6,255,UINT32_MAX};
 for(unsigned i=0;i<4;i++){value=99;assert(xw_player_mode_menu_index(rejected[i],&value)==-1&&value==99);}
 assert(xw_player_mode_menu_index(0,0)==-1);
 assert(!strcmp(xw_player_mode_menu_label(4),"Repeat 1 Song"));
 assert(!xw_player_mode_menu_label(5)&&!xw_player_mode_menu_label(UINT32_MAX));
 puts("PLAY_MODE_INDEX_PASS: JP1.11 five menu ordinals, native5, hidden4 and invalid-output preservation");return 0;
}
