#ifndef HB_STORE_HTTPS_URL_H
#define HB_STORE_HTTPS_URL_H
struct hb_https_url {char host[254],path[2049];unsigned port;};
/* Absolute HTTPS DNS-name profile, optional port, ASCII escaped path/query.
 * Rejects userinfo/bracket literals/all-numeric hosts/controls and invalid
 * path percent escapes. Does not classify noncanonical numeric DNS names or
 * resolve/connect. Fragment is discarded, empty path becomes /. */
int hb_https_url_parse(const char *,struct hb_https_url *);
/* Empty prefix preserves hierarchical hosting. Nonempty prefix selects flat
 * release assets: prefix + lowercase hex of the logical package-relative path. */
int hb_https_asset_url(char *,unsigned,const char *,const char *,const char *);
#endif
