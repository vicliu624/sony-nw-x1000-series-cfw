void *memset(void *p,int c,unsigned n){unsigned char*b=p;for(unsigned i=0;i<n;i++)b[i]=(unsigned char)c;return p;}
void *memcpy(void *p,const void*q,unsigned n){unsigned char*b=p;const unsigned char*a=q;for(unsigned i=0;i<n;i++)b[i]=a[i];return p;}
void __aeabi_memcpy(void*p,const void*q,unsigned n){memcpy(p,q,n);}
void __aeabi_memcpy4(void*p,const void*q,unsigned n){memcpy(p,q,n);}
int raise(int sig){(void)sig;return -1;} /* libgcc divide-by-zero fallback; denominators here are constants. */
