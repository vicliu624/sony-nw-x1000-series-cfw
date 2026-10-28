#include "../../runtime/native/app_catalog.h"
#include <stdio.h>
static struct hb_catalog catalog;
int main(int argc, char **argv) {
  volatile int stop = 0;
  if (argc != 2 || hb_catalog_scan(&catalog, argv[1], &stop) ||
      catalog.count != 1 || catalog.rejected ||
      !hb_catalog_verify(catalog.apps, &stop))
    return 1;
  puts(
      "Unregistered SDK package discovered and verified by the native catalog");
  return 0;
}
