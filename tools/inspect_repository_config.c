#include "../runtime/store/repository.h"
#include <stdio.h>
static struct hb_repository repository;
int main(int argc,char **argv){volatile int stop=0;if(argc!=2)return 64;int result=hb_repository_load(argv[1],&stop,&repository);if(result||!repository.valid){fprintf(stderr,"Repository rejected: %d\n",result);return 1;}return 0;}
