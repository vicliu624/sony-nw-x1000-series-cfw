#ifndef WR_PLAYBACK_ICON_H
#define WR_PLAYBACK_ICON_H
#include "link.h"
#include "../../platform/player/player.h"
enum wr_playback_icon {WR_ICON_UNKNOWN,WR_ICON_PLAYING,WR_ICON_PAUSED,WR_ICON_STOPPED};
/* State indicator matching the Walkman, not the inverse next-button action. */
static inline enum wr_playback_icon wr_playback_icon_for(const struct wr_status *s,int online){
 if(!online||!s||!(s->valid&XW_PF_STATE))return WR_ICON_UNKNOWN;
 if(s->state==XW_PLAY_PLAYING)return WR_ICON_PLAYING;
 if(s->state==XW_PLAY_PAUSED)return WR_ICON_PAUSED;
 if(s->state==XW_PLAY_STOPPED)return WR_ICON_STOPPED;
 return WR_ICON_UNKNOWN;
}
#endif
