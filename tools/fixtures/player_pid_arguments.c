#include <stdint.h>
uint32_t captured[5],calls,allow_output;
uint32_t dispatch_result=4321;
int xw_host_pid_dispatch(uint32_t a,uint32_t b,uint32_t caller,uint32_t list,uint32_t third){
 captured[0]=a;captured[1]=b;captured[2]=caller;captured[3]=list;captured[4]=third;calls++;
 if(allow_output&&a==0x613e60u&&b==3u&&third)*(uint32_t *)(uintptr_t)third=0x12345678u;
 return (int)dispatch_result;
}
void _start(void){for(;;){}}
