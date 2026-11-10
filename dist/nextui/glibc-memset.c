// SPDX-License-Identifier: BSD-3-Clause
#include <stddef.h>

// Zig's bundled fallback clears memory one byte at a time. Use the tuned
// AArch64 implementation supplied by the handheld's C library.
extern void *shmdp_glibc_memset(void *, int, size_t);
__asm__(".symver shmdp_glibc_memset,memset@GLIBC_2.17");

void *memset(void *dest, int value, size_t length)
{
    return shmdp_glibc_memset(dest, value, length);
}
