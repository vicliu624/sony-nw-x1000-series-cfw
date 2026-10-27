/* Offline harness startup through the original libc. Not an app entry. */
extern int main(void);
extern int __libc_start_main(int (*)(int,char **,char **),int,char **,void (*)(void),void (*)(void),void (*)(void),void *);
static int run(int argc,char **argv,char **environment){(void)argc;(void)argv;(void)environment;return main();}
void hb_link_start(unsigned *stack){
 __libc_start_main(run,(int)stack[0],(char **)(stack+1),0,0,0,stack);
 for(;;){}
}
