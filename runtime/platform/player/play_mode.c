#include "play_mode.h"
const char *xw_player_mode_menu_label(uint32_t menu_index){
 static const char *const names[]={"Normal","Repeat","Shuffle","Shuffle&Repeat","Repeat 1 Song"};
 return menu_index<5?names[menu_index]:0;
}
int xw_player_mode_menu_index(uint32_t native_mode,uint32_t *menu_index){
 if(!menu_index)return -1;
 uint32_t value;
 switch(native_mode){case 0:case 1:case 2:case 3:value=native_mode;break;case 5:value=4;break;default:return -1;}
 *menu_index=value;return 0;
}
