#ifndef WR_STARTUP_RESULT_H
#define WR_STARTUP_RESULT_H
/* Private service exit: no live player capability remains. The supervisor
 * still requires independent radio DONE/cookie/EOF and a reaped owner. */
#define WR_SERVICE_START_RETIRED 75
/* Existing owner prepare failure: the post-setup parent view is not valid. */
enum { WR_OWNER_PREPARE_VIEW_FAILED = -4104 };
enum wr_service_start_stage {
    WR_START_HANDOFF = 1,
    WR_START_RADIO_CLIENT,
    WR_START_PLAYER_HELLO,
    WR_START_SENDER,
    WR_START_WORKER,
    WR_START_PLAYER_CAPABILITIES
};
#endif
