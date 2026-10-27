#ifndef HB_QQMUSIC_CREDENTIAL_H
#define HB_QQMUSIC_CREDENTIAL_H
#include "qqmusic_json.h"
enum qq_auth_result {QQ_AUTH_OK,QQ_AUTH_PROTOCOL=-1,QQ_AUTH_EXPIRED=-2,
 QQ_AUTH_DEVICE_LIMIT=-3,QQ_AUTH_RESTRICTED=-4,QQ_AUTH_RATE_LIMIT=-5,
 QQ_AUTH_SIGNATURE=-6,QQ_AUTH_OTHER=-7,QQ_AUTH_IDENTITY=-8,QQ_AUTH_DENIED=-9};
struct qq_credential {
 uint64_t musicid,created_at,expires_in;
 char musickey[513],encrypt_uin[257],openid[257],refresh_token[513],
 access_token[513],refresh_key[513],unionid[257];
 unsigned login_type;
};
/* Only QQ QR credentials (loginType2); success still requires service verify.
 * Workspace and credential are cleared on failure. Caller clears input body.
 * service_code is safe numeric diagnostics, never response text. */
int qq_credential_parse(struct qq_json *,const char *,size_t,struct qq_credential *,uint64_t *service_code);
/* Unwrap CGI with checked global/item/data codes, for future playlist calls.
 * Returns nonnegative data node or a qq_auth_result error. */
int qq_cgi_data(struct qq_json *,const char *,size_t,uint64_t *service_code);
void qq_credential_clear(struct qq_credential *);
#endif
