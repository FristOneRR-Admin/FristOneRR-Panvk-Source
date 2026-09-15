/*
 * Copyright © 2026 Mesa contributors
 * SPDX-License-Identifier: MIT
 */

#include "genxml/gen_macros.h"

#include "panvk_cmd_alloc.h"
#include "panvk_cmd_buffer.h"
#include "panvk_entrypoints.h"

static bool
ensure_xfb_offsets(struct panvk_cmd_buffer *cmdbuf)
{
   if (cmdbuf->state.gfx.xfb.offsets.gpu)
      return true;

   cmdbuf->state.gfx.xfb.offsets = panvk_cmd_alloc_dev_mem(
      cmdbuf, desc, PANVK_MAX_XFB_BUFFERS * sizeof(uint32_t),
      sizeof(uint64_t));

   return cmdbuf->state.gfx.xfb.offsets.gpu != 0;
}

VKAPI_ATTR void VKAPI_CALL
panvk_per_arch(CmdBindTransformFeedbackBuffers2EXT)(
   VkCommandBuffer commandBuffer, uint32_t firstBinding,
   uint32_t bindingCount,
   const VkBindTransformFeedbackBuffer2InfoEXT *pBindingInfos)
{
   VK_FROM_HANDLE(panvk_cmd_buffer, cmdbuf, commandBuffer);

   assert(firstBinding + bindingCount <= PANVK_MAX_XFB_BUFFERS);

   for (uint32_t i = 0; i < bindingCount; i++) {
      const uint32_t binding = firstBinding + i;
      cmdbuf->state.gfx.xfb.buffers[binding].address =
         pBindingInfos[i].addressRange.address;
      cmdbuf->state.gfx.xfb.buffers[binding].size =
         pBindingInfos[i].addressRange.size;
   }
}

VKAPI_ATTR void VKAPI_CALL
panvk_per_arch(CmdBeginTransformFeedback2EXT)(
   VkCommandBuffer commandBuffer, uint32_t firstCounterRange,
   uint32_t counterRangeCount,
   const VkBindTransformFeedbackBuffer2InfoEXT *pCounterInfos)
{
   VK_FROM_HANDLE(panvk_cmd_buffer, cmdbuf, commandBuffer);

   assert(!cmdbuf->state.gfx.xfb.enabled);
   assert(firstCounterRange + counterRangeCount <= PANVK_MAX_XFB_BUFFERS);

   if (!ensure_xfb_offsets(cmdbuf))
      return;

   struct cs_builder *b =
      panvk_get_cs_builder(cmdbuf, PANVK_SUBQUEUE_COMPUTE);
   struct cs_index src_addr = cs_scratch_reg64(b, 0);
   struct cs_index value = cs_scratch_reg32(b, 2);
   struct cs_index offsets_addr = cs_scratch_reg64(b, 4);

   cs_move64_to(b, offsets_addr, cmdbuf->state.gfx.xfb.offsets.gpu);

   for (uint32_t i = 0; i < PANVK_MAX_XFB_BUFFERS; i++) {
      const int32_t counter = i - firstCounterRange;
      const bool append = counter >= 0 && counter < counterRangeCount &&
                          pCounterInfos &&
                          pCounterInfos[counter].addressRange.address &&
                          pCounterInfos[counter].addressRange.size;

      if (append) {
         cs_move64_to(b, src_addr,
                      pCounterInfos[counter].addressRange.address);
         cs_load32_to(b, value, src_addr, 0);
         cs_flush_loads(b);
      } else {
         cs_move32_to(b, value, 0);
      }

      cs_store32(b, value, offsets_addr, i * sizeof(uint32_t));
   }

   cs_flush_stores(b);
   cmdbuf->state.gfx.xfb.enabled = true;
}

VKAPI_ATTR void VKAPI_CALL
panvk_per_arch(CmdEndTransformFeedback2EXT)(
   VkCommandBuffer commandBuffer, uint32_t firstCounterRange,
   uint32_t counterRangeCount,
   const VkBindTransformFeedbackBuffer2InfoEXT *pCounterInfos)
{
   VK_FROM_HANDLE(panvk_cmd_buffer, cmdbuf, commandBuffer);

   assert(cmdbuf->state.gfx.xfb.enabled);
   assert(firstCounterRange + counterRangeCount <= PANVK_MAX_XFB_BUFFERS);

   struct cs_builder *b =
      panvk_get_cs_builder(cmdbuf, PANVK_SUBQUEUE_COMPUTE);
   struct cs_index offsets_addr = cs_scratch_reg64(b, 0);
   struct cs_index dst_addr = cs_scratch_reg64(b, 2);
   struct cs_index value = cs_scratch_reg32(b, 4);

   cs_move64_to(b, offsets_addr, cmdbuf->state.gfx.xfb.offsets.gpu);

   for (uint32_t i = 0; i < counterRangeCount; i++) {
      if (!pCounterInfos || !pCounterInfos[i].addressRange.address ||
          !pCounterInfos[i].addressRange.size)
         continue;

      const uint32_t counter = firstCounterRange + i;
      cs_load32_to(b, value, offsets_addr,
                   counter * sizeof(uint32_t));
      cs_flush_loads(b);
      cs_move64_to(b, dst_addr, pCounterInfos[i].addressRange.address);
      cs_store32(b, value, dst_addr, 0);
   }

   cs_flush_stores(b);
   cmdbuf->state.gfx.xfb.enabled = false;
}
