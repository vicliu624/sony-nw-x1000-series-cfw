#ifndef HB_QQMUSIC_QMC_H
#define HB_QQMUSIC_QMC_H
#include <stddef.h>
#include <stdint.h>
struct qq_qmc_key {unsigned char key[2048],box[2048];unsigned length;uint32_t hash;};
/* MIT adaptation; see THIRD_PARTY.md. Key/context memory only, no logging.
 * EncV1, EncV2 and raw GetEVkey base64; output erased on failure. */
int qq_qmc_derive(struct qq_qmc_key *,const char *ekey,size_t bytes);
/* Explicit raw-key entry for algorithm tests and already-derived key callers. */
int qq_qmc_init(struct qq_qmc_key *,const unsigned char *,size_t);
/* XOR in place, random access, max64KiB per call and 256MiB file range.
 * Input must exclude musicex footer. No format/authenticity guarantee here. */
int qq_qmc_apply(const struct qq_qmc_key *,unsigned char *,size_t,uint64_t offset);
void qq_qmc_clear(struct qq_qmc_key *);
/* Native payload bound from final16 bytes, no source mutation. musicex footer
 * size must be >=16 and <total; other/absent markers aren't decoded as keys. */
int qq_qmc_payload_length(uint64_t total,const unsigned char tail[16],uint64_t *audio_bytes,int *has_musicex);
#endif
