#ifndef HB_QQMUSIC_FILE_IMPORT_H
#define HB_QQMUSIC_FILE_IMPORT_H
#include "qqmusic_import.h"
#include "qqmusic_source.h"
#include "qqmusic_output.h"
/* Existing READY source and initialized EMPTY output in the same verified
 * exclusive workspace. Conversion config provides metadata/key/stop/budget;
 * its source/destination callbacks must be empty and are bound here. Success
 * leaves only a READY temporary MP3, never a published music-library file.
 * Failure preserves source and aborts only the newly acquired output. */
int qq_file_import(struct qq_volume *,const struct qq_storage_plan *,const struct qq_stage_file *,
 const struct qq_import_conversion *,const char *identity64,const char *nonce16,
 struct qq_output_file *,struct qq_import_report *);
#endif
