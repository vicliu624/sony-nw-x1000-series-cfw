#include "../runtime/apps/wireless-remote/link.h"
#include "../runtime/apps/wireless-remote/player_status.h"
#include "../runtime/apps/wireless-remote/receiver.h"
#include "../runtime/apps/wireless-remote/control.h"
#include "../runtime/apps/wireless-remote/mode_wire.h"
#include "../runtime/apps/wireless-remote/session_wire.h"
#include <assert.h>
#include <string.h>
#include <stdio.h>
static void session_tests(void){
 uint8_t key[32]={1},peer[6]={2,1,2,3,4,5},challenge[16]={1},request[64],reply[64],copy[64],decoded[16];
 struct wr_receiver r={0};assert(!wr_receiver_pair(&r,peer,key,7));r.sequence=99;r.have_status=1;
 assert(!wr_receiver_challenge(&r,challenge,request,sizeof request));
 assert(!wr_session_request_read(decoded,request,64,key)&&!memcmp(decoded,challenge,16));
 assert(!wr_session_reply(reply,64,decoded,8,key));
 struct wr_receiver before=r;
 for(unsigned i=0;i<64;i++){
  memcpy(copy,reply,64);copy[i]^=1;
  assert(wr_receiver_session_reply(&r,peer,copy,64)==-1&&!memcmp(&r,&before,sizeof r));
 }
 uint8_t wrong[6]={2,2,2,3,4,5};
 assert(wr_receiver_session_reply(&r,wrong,reply,64)==-1&&!memcmp(&r,&before,sizeof r));
 assert(wr_receiver_session_reply(&r,peer,request,64)==-1);
 assert(wr_receiver_session_reply(&r,peer,reply,64)==1&&r.session==8&&!r.sequence&&!r.have_status&&!r.challenge_pending);
 before=r;assert(wr_receiver_session_reply(&r,peer,reply,64)==-1&&!memcmp(&r,&before,sizeof r));
 assert(wr_receiver_challenge(&r,challenge,request,64)==-1);
 challenge[0]=2;r.sequence=100;r.have_status=1;
 assert(!wr_receiver_challenge(&r,challenge,request,64));
 assert(!wr_session_reply(reply,64,challenge,8,key));
 assert(!wr_receiver_session_reply(&r,peer,reply,64)&&r.sequence==100&&r.have_status);
 challenge[0]=3;assert(!wr_receiver_challenge(&r,challenge,request,64));
 assert(!wr_session_reply(reply,64,challenge,9,key));wr_receiver_cancel_challenge(&r);before=r;
 assert(wr_receiver_session_reply(&r,peer,reply,64)==-1&&!memcmp(&r,&before,sizeof r));
 challenge[0]=4;assert(!wr_receiver_challenge(&r,challenge,request,64));before=r;
 assert(wr_receiver_session_reply(&r,peer,reply,64)==-1&&!memcmp(&r,&before,sizeof r));
 assert(!wr_session_reply(reply,64,challenge,9,key)&&wr_receiver_session_reply(&r,peer,reply,64)==1);
 uint64_t value=42;memset(challenge,0,16);
 assert(wr_session_request(request,64,challenge,key)==-1&&wr_session_reply(reply,64,challenge,0,key)==-1);
 assert(wr_session_reply_read(&value,reply,63,challenge,key)==-1&&value==42);
 wr_receiver_clear(&r);
}
int main(void){
 session_tests();
 struct wr_status s={0},out,old;uint8_t wire[WR_STATUS_BYTES];
 s.session=0x123456789abcdefULL;s.sequence=1;s.valid=39;s.commands=63;s.state=3;
 s.volume=9;s.maximum=30;s.metadata_flags=7;
 strcpy(s.id,"opaque-track");strcpy(s.title,"Test \xe7\x8c\xab");strcpy(s.artist,"Artist");strcpy(s.album,"Album");
 assert(!wr_status_encode(wire,sizeof wire,&s));assert(!wr_status_decode(&out,wire,sizeof wire));
 assert(out.session==s.session&&out.volume==9&&!strcmp(out.title,s.title));old=out;
 for(size_t n=0;n<sizeof wire;n++)assert(wr_status_decode(&out,wire,n)==-1);
 assert(!memcmp(&out,&old,sizeof out));
 wire[109]=0xc0;assert(wr_status_decode(&out,wire,sizeof wire)==-1&&!memcmp(&out,&old,sizeof out));
 assert(!wr_status_encode(wire,sizeof wire,&s));wire[12]=0;
 assert(wr_status_decode(&out,wire,sizeof wire)==-1);
 s.volume=31;memset(wire,0xa5,sizeof wire);assert(wr_status_encode(wire,sizeof wire,&s)==-1&&wire[0]==0xa5);
 struct xw_player_snapshot snap;memset(&snap,0,sizeof snap);snap.valid=39;snap.state=XW_PLAY_PLAYING;
 snap.volume=9;snap.volume_max=30;snap.track.flags=7;strcpy(snap.track.title,"Real snapshot adapter");
 assert(!wr_player_status(&out,&snap,1,1,63)&&out.state==3&&!strcmp(out.title,snap.track.title));
 snap.track.title[200]='X';assert(!wr_player_status(&out,&snap,1,1,63)&&!out.title[200]);
 snap.valid=0;assert(!wr_player_status(&out,&snap,1,2,63)&&!out.valid&&!out.title[0]&&!out.volume);
 uint8_t signed_wire[WR_SIGNED_STATUS_BYTES],key[32]={1},address[6]={2,1,2,3,4,5};struct wr_receiver r={0};
 assert(!wr_receiver_pair(&r,address,key,1));
 assert(!wr_status_sign(signed_wire,sizeof signed_wire,&out,key));
 /* Independently generated Python stdlib HMAC vector for this exact frame. */
 const uint8_t expected[16]={0xe1,0x12,0x94,0xab,0x24,0x6e,0x95,0xe2,0xea,0xf7,0x88,0xc4,0xf2,0xb9,0x37,0xff};
 assert(!memcmp(signed_wire+WR_STATUS_BYTES,expected,sizeof expected));
 assert(!wr_receiver_accept(&r,address,signed_wire,sizeof signed_wire)&&r.have_status&&r.sequence==2);
 assert(wr_receiver_accept(&r,address,signed_wire,sizeof signed_wire)==-1);
 out.sequence=3;assert(!wr_status_sign(signed_wire,sizeof signed_wire,&out,key));signed_wire[50]^=1;
 assert(wr_receiver_accept(&r,address,signed_wire,sizeof signed_wire)==-1&&r.sequence==2);
 assert(!wr_status_sign(signed_wire,sizeof signed_wire,&out,key));address[5]^=1;
 assert(wr_receiver_accept(&r,address,signed_wire,sizeof signed_wire)==-1);address[5]^=1;
 assert(!wr_receiver_accept(&r,address,signed_wire,sizeof signed_wire));
 uint8_t ctrl_wire[WR_CONTROL_BYTES];struct wr_control command={1,1,XW_OP_STEP_VOLUME,-1},decoded;
 assert(!wr_control_encode(ctrl_wire,sizeof ctrl_wire,&command,key));
 assert(!wr_control_decode(&decoded,ctrl_wire,sizeof ctrl_wire,key)&&decoded.value==-1&&decoded.request==1);
 ctrl_wire[24]=1;assert(wr_control_decode(&decoded,ctrl_wire,sizeof ctrl_wire,key)==-1);
 struct wr_control_receipt receipt={1,1,XW_PLAYER_UNCERTAIN},decoded_receipt;
 assert(!wr_receipt_encode(ctrl_wire,sizeof ctrl_wire,&receipt,key));
 assert(!wr_receipt_decode(&decoded_receipt,ctrl_wire,sizeof ctrl_wire,key)&&decoded_receipt.result==XW_PLAYER_UNCERTAIN);
 assert(wr_control_decode(&decoded,ctrl_wire,sizeof ctrl_wire,key)==-1);
 struct wr_mode mode={1,1,1,5,4},received_mode;uint8_t mode_wire[WR_MODE_BYTES];
 assert(!wr_mode_encode(mode_wire,sizeof mode_wire,&mode,key));assert(!wr_mode_decode(&received_mode,mode_wire,sizeof mode_wire,key)&&received_mode.index==4);
 struct wr_mode prior_mode=received_mode;mode_wire[20]^=1;assert(wr_mode_decode(&received_mode,mode_wire,sizeof mode_wire,key)==-1&&!memcmp(&received_mode,&prior_mode,sizeof prior_mode));
 mode.native=4;assert(wr_mode_encode(mode_wire,sizeof mode_wire,&mode,key)==-1);
 mode.valid=0;mode.native=mode.index=0;assert(!wr_mode_encode(mode_wire,sizeof mode_wire,&mode,key)&&!wr_mode_decode(&received_mode,mode_wire,sizeof mode_wire,key)&&!received_mode.valid);
 wr_receiver_clear(&r);for(size_t i=0;i<sizeof r;i++)assert(!((unsigned char *)&r)[i]);
 puts("REMOTE_LINK_PASS: bounded UTF8 status, SDK adapter, authenticated reception, replay rejection and key cleanup");return 0;
}
