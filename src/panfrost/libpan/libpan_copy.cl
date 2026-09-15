/*
 * Copyright 2026 Google LLC
 * Copyright 2024 Valve Corporation
 * SPDX-License-Identifier: MIT
 */
#include "compiler/libcl/libcl.h"
#include "libpan_copy.h"

#if PAN_ARCH >= 6
KERNEL(32)
panlib_fill(global uint32_t *address, uint32_t value)
{
   address[cl_global_id.x] = value;
}

KERNEL(32)
panlib_fill_uint4(global uint4 *address, uint a, uint b, uint c, uint d)
{
   address[cl_global_id.x] = (uint4)(a, b, c, d);
}

KERNEL(1)
panlib_fill_scalar(global uint32_t *address, uint32_t value)
{
   address[cl_global_id.x] = value;
}

KERNEL(1)
panlib_fill_uint4_scalar(global uint4 *address, uint a, uint b, uint c, uint d)
{
   address[cl_global_id.x] = (uint4)(a, b, c, d);
}

#if PAN_ARCH >= 10
/* The workgroup count is derived from the copy size on the command stream
 * and may be capped, so each thread loops until the whole size is covered.
 */
KERNEL(PANLIB_COPY_MEM_INDIRECT_WG_SIZE)
panlib_copy_mem_indirect(global const uint32_t *cmd)
{
   /* VkCopyMemoryIndirectCommandKHR is only guaranteed to be 4-byte
    * aligned, read it as 32-bit words.
    */
   uintptr_t src = upsample(cmd[1], cmd[0]);
   uintptr_t dst = upsample(cmd[3], cmd[2]);
   uint64_t size = upsample(cmd[5], cmd[4]);

   bool use_16B = size >= PANLIB_COPY_MEM_INDIRECT_CHUNK_SIZE;
   uint32_t chunk = use_16B ? PANLIB_COPY_MEM_INDIRECT_CHUNK_SIZE : 4;
   uint64_t stride = (uint64_t)cl_num_groups.x * PANLIB_COPY_MEM_INDIRECT_WG_SIZE * chunk;

   for (uint64_t off = (uint64_t)cl_global_id.x * chunk; off < size; off += stride) {
      /* Clamp so the last chunk does not run past the end. */
      uint64_t o = min(off, size - chunk);

      if (use_16B) {
         uint4 data = vload4(0, (global uint32_t *)(src + o));
         vstore4(data, 0, (global uint32_t *)(dst + o));
      } else {
         *(global uint32_t *)(dst + o) = *(global uint32_t *)(src + o);
      }
   }
}
#endif
#endif
