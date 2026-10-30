/* Narrow original SQLite ABI declarations. No modern SQLite-only API aliases. */
#ifndef XW_PLAYER_SQLITE_ABI_H
#define XW_PLAYER_SQLITE_ABI_H
typedef struct sqlite3 sqlite3;typedef struct sqlite3_stmt sqlite3_stmt;
extern int sqlite3_open_v2(const char *,sqlite3 **,int,const char *);
extern int sqlite3_close(sqlite3 *);
extern int sqlite3_exec(sqlite3 *,const char *,void *,void *,char **);
extern int sqlite3_prepare_v2(sqlite3 *,const char *,int,sqlite3_stmt **,const char **);
extern int sqlite3_step(sqlite3_stmt *);
extern int sqlite3_finalize(sqlite3_stmt *);
extern int sqlite3_column_int(sqlite3_stmt *,int);
extern long long sqlite3_column_int64(sqlite3_stmt *,int);
extern const unsigned char *sqlite3_column_text(sqlite3_stmt *,int);
extern int sqlite3_column_type(sqlite3_stmt *,int);
extern int sqlite3_column_bytes(sqlite3_stmt *,int);
extern int sqlite3_bind_int64(sqlite3_stmt *,int,long long);
extern int sqlite3_bind_int(sqlite3_stmt *,int,int);
extern int sqlite3_set_authorizer(sqlite3 *,int (*)(void *,int,const char *,const char *,const char *,const char *),void *);
extern void sqlite3_progress_handler(sqlite3 *,int,int (*)(void *),void *);
extern int sqlite3_limit(sqlite3 *,int,int);
#endif
