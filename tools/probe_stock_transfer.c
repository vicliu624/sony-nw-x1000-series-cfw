/* Offline library initialization only. No URL, socket or transfer operation. */
#include <string.h>
#include <unistd.h>
extern const char *curl_version(void);
extern int curl_global_init(long);
extern void curl_global_cleanup(void);
extern void *curl_easy_init(void);
extern void curl_easy_cleanup(void *);
extern const char *SSLeay_version(int);
extern int SSL_library_init(void);
extern const void *TLSv1_client_method(void);
extern void *SSL_CTX_new(const void *);
extern void SSL_CTX_free(void *);
extern const void *SSLv23_client_method(void);
extern void *SSL_new(void *);
extern void SSL_free(void *);
extern const void *BIO_s_mem(void);
extern void *BIO_new(const void *);
extern int BIO_free(void *);
extern int BIO_read(void *,void *,int);
extern void SSL_set_bio(void *,void *,void *);
extern void SSL_set_connect_state(void *);
extern int SSL_do_handshake(void *);
extern int SSL_get_error(const void *,int);
static int line(const char *text){
 unsigned n=(unsigned)strlen(text);
 return write(1,text,n)==(long)n&&write(1,"\n",1)==1?0:-1;
}
static int hello(void){
 void *context=SSL_CTX_new(SSLv23_client_method());if(!context)return -1;
 void *ssl=SSL_new(context),*input=BIO_new(BIO_s_mem()),*output=BIO_new(BIO_s_mem());
 if(!ssl||!input||!output){if(input)BIO_free(input);if(output)BIO_free(output);if(ssl)SSL_free(ssl);SSL_CTX_free(context);return -1;}
 SSL_set_bio(ssl,input,output);SSL_set_connect_state(ssl);
 int result=SSL_do_handshake(ssl);int reason=SSL_get_error(ssl,result);
 unsigned char data[4096];int n=BIO_read(output,data,sizeof data),ok=0;
 if(result<0&&reason==2&&n>=11){
  if((data[0]&128)&&data[2]==1&&data[3]==3&&data[4]==1)
   ok=!line("memory-clienthello: SSL2-compatible framing; offered version 0x0301");
  else if(data[0]==22&&data[5]==1&&data[9]==3&&data[10]==1)
   ok=!line("memory-clienthello: TLS framing; offered version 0x0301");
 }
 SSL_free(ssl);SSL_CTX_free(context);return ok?0:-1;
}
int main(void){
 if(curl_global_init(3))return 1;
 void *handle=curl_easy_init();if(!handle){curl_global_cleanup();return 2;}
 int result=line(curl_version())||line(SSLeay_version(0));
 if(SSL_library_init()!=1)result=3;
 void *context=SSL_CTX_new(TLSv1_client_method());
 if(!context)result=4;else SSL_CTX_free(context);
 if(hello())result=6;
 curl_easy_cleanup(handle);curl_global_cleanup();
 return result?5:line("stock-transfer-init-ok");
}
