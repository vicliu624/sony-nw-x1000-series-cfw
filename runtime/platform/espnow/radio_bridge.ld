/* Candidate reserved fourth block of the stock large TX pool.
 * Requires the matching pool-count and scatter-zero edits in the SAME image.
 * Never load this ELF into the stock four-block image at runtime.
 */
ENTRY(xnow_radio_receive)
SECTIONS {
  . = 0xc000a190;
  .text : { *(.text*) *(.rodata*) }
  .state : { *(.state) }
  ASSERT(. <= 0xc000a8fc, "reserved packet block budget exceeded")
  /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.note*) }
}
