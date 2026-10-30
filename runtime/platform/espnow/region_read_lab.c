/* Read-only diagnostic of the exact RF-init pipe/exec/parser path. */
#include "xnow_rf_init.c"
int main(void){
    char text[128];unsigned bytes=0,region=0;
    char *arguments[]={"/usr/local/bin/nvp","zr","11","1",0};
    int result=run(arguments,text,sizeof(text),&bytes);
    printf("nvp_native_pipe_result=%d bytes=%u\n",result,bytes);
    if(!result){printf("nvp_zone11_hex=");for(unsigned i=0;i<bytes;i++)printf("%02x",(unsigned char)text[i]);puts("");}
    int parsed=result?-1:xnow_region_from_nvp(text,bytes,&region);
    printf("nvp_native_parser_result=%d region=%u\n",parsed,region);
    return result||parsed?69:0;
}
