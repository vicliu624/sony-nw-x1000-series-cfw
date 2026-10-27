#ifndef HB_QQMUSIC_CGI_H
#define HB_QQMUSIC_CGI_H
#include "qqmusic_json.h"
#include "qqmusic_protocol.h"
/* comm supplied by future device-identity/version policy, all values strings
 * as in fixed upstream. Requires ct,cv,tmeLoginType=2. No invented fingerprint.
 * Unsigned musicu path; signature-required responses must be surfaced. */
int qq_build_login_cgi(struct qq_request *,struct qq_json *,const char *comm,size_t bytes,const char *authorization_code);
int qq_build_verify_cgi(struct qq_request *,struct qq_json *,const char *comm,size_t bytes);
/* Anonymous Android transport session, not account authentication. Fresh only:
 * no imported uid, no cookies or refresh of another installation's session. */
int qq_build_session_cgi(struct qq_request *,struct qq_json *,const char *comm,size_t bytes);
struct qq_anonymous_session {char uid[129],sid[129];};
/* Both service status codes must succeed. Output/workspace cleared on error;
 * uid/sid are private runtime material and must never be logged. */
int qq_parse_session_cgi(struct qq_json *,const char *,size_t,struct qq_anonymous_session *);
enum qq_catalog_request_kind {QQ_REQ_CREATED,QQ_REQ_COLLECTED,QQ_REQ_FAVORITE_SONGS,QQ_REQ_PLAYLIST_SONGS};
/* comm includes actual authenticated account fields from the verified session.
 * Read-only fixed module/methods; no remote playlist mutation. size1..16.
 * Created list has no offset protocol; incomplete results must be surfaced. */
int qq_build_catalog_cgi(struct qq_request *,struct qq_json *,const char *comm,size_t,
 enum qq_catalog_request_kind,uint64_t musicid,const char *encrypt_uin,
 uint64_t playlist_id,uint64_t dirid,uint64_t offset,unsigned size);
#endif
