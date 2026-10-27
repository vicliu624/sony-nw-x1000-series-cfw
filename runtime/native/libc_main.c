/* Ordinary libc entry; no synthetic startup stack or Sony binary addresses. */
extern int hb_main(int argc, char **argv, char **environment);
int main(int argc, char **argv, char **environment) {
    return hb_main(argc,argv,environment);
}
