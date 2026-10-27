/* Deterministic, offline ClientHello fixture. Never a production TLS setup. */
#include "bearssl.h"
#include <unistd.h>
static br_ssl_client_context client;
static br_x509_minimal_context verifier;
static unsigned char io_buffer[BR_SSL_BUFSIZE_BIDI];
int main(void){
 unsigned char seed[48];for(unsigned i=0;i<sizeof seed;i++)seed[i]=(unsigned char)i;
 /* No trust anchors: no peer certificate could be accepted by this fixture. */
 br_ssl_client_init_full(&client,&verifier,0,0);
 br_ssl_engine_set_versions(&client.eng,BR_TLS12,BR_TLS12);
 br_ssl_engine_set_buffer(&client.eng,io_buffer,sizeof io_buffer,1);
 br_ssl_engine_inject_entropy(&client.eng,seed,sizeof seed);
 if(!br_ssl_client_reset(&client,"offline.invalid",0))return 1;
 size_t n=0;unsigned char *record=br_ssl_engine_sendrec_buf(&client.eng,&n);
 if(!record||n<11||record[0]!=22||record[5]!=1||record[9]!=3||record[10]!=3)return 2;
 static const char result[]="external-memory-clienthello: version 0x0303; fixture entropy; no peer\n";
 return write(1,result,sizeof result-1)==(long)(sizeof result-1)?0:3;
}
