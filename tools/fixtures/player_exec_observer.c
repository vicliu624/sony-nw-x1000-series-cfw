/* Statically linked host observer for an ARM-wrapper execve ABI test. */
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
int main(int argc,char **argv){
 printf("%ld\n%s\n%s\n%s\n%s\n",(long)getpid(),argv[0],argc>1?argv[1]:"",getenv("XW_TEST_KEEP")?getenv("XW_TEST_KEEP"):"",getenv("LD_PRELOAD")?getenv("LD_PRELOAD"):"");return 0;
}
