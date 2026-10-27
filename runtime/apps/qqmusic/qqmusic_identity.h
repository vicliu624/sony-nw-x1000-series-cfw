#ifndef HB_QQMUSIC_IDENTITY_H
#define HB_QQMUSIC_IDENTITY_H
#include "qqmusic_runtime.h"
struct qq_identity {
 char comm[1025],guid[65];unsigned char previous[48];unsigned ready,have_previous;
 unsigned session_pending,session_bound,qimei_bound;
 volatile int *stop;
 int (*seed)(unsigned char out[48],volatile int *);
};
/* Fresh object only. Explicit non-account identity/version policy; no invented
 * fingerprint, imported credentials or service-validity claim. NULL seed uses
 * stock-compatible /dev/urandom. Caller keeps object stable during network use. */
int qq_identity_init(struct qq_identity *,const char *comm,const char *guid,volatile int *,int (*seed)(unsigned char[48],volatile int *));
int qq_identity_prepare(void *,struct qq_runtime_material *);
/* One fresh anonymous bootstrap on this installation identity. The caller uses
 * the normal authenticated TLS transport and passes its completed response.
 * Does not authenticate an account, persist data or import an old session. */
int qq_identity_session_request(struct qq_identity *,struct qq_request *);
int qq_identity_session_accept(struct qq_identity *,const struct qq_response *);
/* Bind one validated service-returned QIMEI36 into an initially empty field.
 * An explicitly empty service value is preserved, never replaced by q16. */
int qq_identity_bind_qimei(struct qq_identity *,const char *);
void qq_identity_clear(struct qq_identity *);
#endif
