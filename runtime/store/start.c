/* Startup through the original libc; no modern crt/sysroot runtime is linked. */
extern int main(int,char **,char **);
extern int __libc_start_main(int (*)(int,char **,char **),int,char **,void (*)(void),void (*)(void),void (*)(void),void *);
void hb_store_start(unsigned *stack){
 __libc_start_main(main,(int)stack[0],(char **)(stack+1),0,0,0,stack);
 for(;;){}
}
