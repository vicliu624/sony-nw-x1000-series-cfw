#ifndef HB_QQMUSIC_JSON_H
#define HB_QQMUSIC_JSON_H
#include <stddef.h>
#include <stdint.h>
#define QQ_JSON_NODES 8192
enum qq_json_type {QQ_JSON_OBJECT,QQ_JSON_ARRAY,QQ_JSON_STRING,QQ_JSON_NUMBER,QQ_JSON_LITERAL};
struct qq_json_node {size_t start,end;unsigned next;enum qq_json_type type;};
struct qq_json {const char *text;size_t bytes;unsigned used;struct qq_json_node nodes[QQ_JSON_NODES];};
/* No allocation. Max 256 KiB input, 8192 nodes, depth16, keys <=128 decoded UTF-8 bytes.
 * Full upstream metadata for a playlist/song page must fit, not only fields
 * selected by this client. ARM workspace is 128 KiB, caller-owned/bounded.
 * Rejects duplicate decoded keys, invalid UTF-8, NUL and unpaired surrogates.
 * Workspace references caller input; clear both after processing credentials. */
int qq_json_parse(struct qq_json *,const char *,size_t);
int qq_json_get(const struct qq_json *,unsigned object,const char *key);
int qq_json_string(const struct qq_json *,unsigned node,char *out,size_t cap);
int qq_json_uint(const struct qq_json *,unsigned node,uint64_t *out);
#endif
