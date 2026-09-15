/*
 * Copyright © 2021 Collabora Ltd.
 *
 * Derived from tu_device.c which is:
 * Copyright © 2016 Red Hat.
 * Copyright © 2016 Bas Nieuwenhuizen
 * Copyright © 2015 Intel Corporation
 *
 * SPDX-License-Identifier: MIT
 */

#include "genxml/gen_macros.h"

#include "decode.h"

#include "kmod/kbase_kmod.h"

#include "panvk_cmd_buffer.h"
#include "panvk_device.h"
#include "panvk_entrypoints.h"
#include "panvk_event.h"
#include "panvk_image.h"
#include "panvk_image_view.h"
#include "panvk_instance.h"
#include "panvk_physical_device.h"
#include "panvk_priv_bo.h"
#include "panvk_queue.h"

#include "vk_framebuffer.h"
#include "vk_sync.h"

/* kbase job atoms don't support GPU-side pre_dep chaining the way DRM
 * syncobjs do (kbase_kmod_job_submit() always leaves pre_dep unset), so
 * ordering between the vertex/tiler job and the fragment job within one
 * batch is enforced with a CPU-side wait here. Ordering against *other*
 * queue submissions is instead handled lazily: we never block here, we
 * just record the atom numbers and hand them to panvk_kbase_sync_set_pending()
 * so a future vk_sync_wait() on queue->sync (or a signal semaphore) does
 * the actual blocking, off the submission's critical path. */
static uint64_t
panvk_queue_submit_batch(struct panvk_gpu_queue *queue,
                         struct panvk_cmd_buffer *cmdbuf,
                         struct panvk_batch *batch, struct pan_kmod_bo **bos,
                         unsigned nr_bos, uint64_t *out_frag_atom)
{
   struct panvk_device *dev = to_panvk_device(queue->vk.base.device);
   struct panvk_physical_device *phys_dev =
      to_panvk_physical_device(dev->vk.physical);
   uint64_t vtc_atom = 0, frag_atom = 0;
   fprintf(stderr, "[TRACE] submit_batch: vtc_jc.first_job=%lu frag_jc.first_job=%lu\n", (unsigned long)batch->vtc_jc.first_job, (unsigned long)batch->frag_jc.first_job); fflush(stderr);

   /* Reset the batch if it's already been issued */
   if (batch->issued) {
      util_dynarray_foreach(&batch->jobs, void *, job)
         memset((*job), 0, 4 * 4);

      /* Reset the tiler before re-issuing the batch */
      if (batch->tiler.ctx_descs.cpu) {
         memcpy(batch->tiler.heap_desc.cpu, &batch->tiler.heap_templ,
                sizeof(batch->tiler.heap_templ));

         struct mali_tiler_context_packed *ctxs = batch->tiler.ctx_descs.cpu;

         for (uint32_t i = 0; i < batch->fb.layer_count; i++)
            memcpy(&ctxs[i], &batch->tiler.ctx_templ, sizeof(*ctxs));
      }

      /* We don't keep track of BO <-> job relationship, so let's just flush the
       * whole desc pool for now. */
      panvk_pool_flush_maps(&cmdbuf->desc_pool);
   }

   /* Flush pending synchronization requests before submitting the job, to
    * make sure things are GPU-visible. */
   pan_kmod_flush_bo_map_syncs(dev->kmod.dev);

   if (batch->vtc_jc.first_job) {
      vtc_atom = kbase_kmod_job_submit(
         dev->kmod.dev, batch->vtc_jc.first_job, BASE_JD_REQ_ONLY_COMPUTE,
         bos, nr_bos, NULL, 0);
      assert(vtc_atom);

      if (PANVK_DEBUG(TRACE) || PANVK_DEBUG(SYNC)) {
         ASSERTED bool done =
            kbase_kmod_wait_atom(dev->kmod.dev, vtc_atom, -1);
         assert(done);
            vtc_atom = 0; /* already waited+consumed above; don't wait again in wait_one() */

         /* If we want to read the descriptors back, we need to invalidate the
          * whole desc pool, otherwise we might end up with stale data. */
         panvk_pool_invalidate_maps(&cmdbuf->desc_pool);
         pan_kmod_flush_bo_map_syncs(dev->kmod.dev);
      }

      if (PANVK_DEBUG(TRACE)) {
         pandecode_jc(dev->debug.decode_ctx, batch->vtc_jc.first_job,
                      phys_dev->kmod.dev->props.gpu_id);
      }

      if (PANVK_DEBUG(DUMP))
         pandecode_dump_mappings(dev->debug.decode_ctx);

      if (PANVK_DEBUG(SYNC))
         pandecode_abort_on_fault(dev->debug.decode_ctx, batch->vtc_jc.first_job,
                                  phys_dev->kmod.dev->props.gpu_id);
   }

   if (batch->frag_jc.first_job) {
      /* The fragment job depends on the vertex/tiler job. kbase atoms can't
       * express that dependency for us, so block on the CPU here before
       * submitting the fragment job. */
      if (vtc_atom) {
         ASSERTED bool done = kbase_kmod_wait_atom(dev->kmod.dev, vtc_atom, -1);
         assert(done);
      }

      frag_atom = kbase_kmod_job_submit(dev->kmod.dev,
                                        batch->frag_jc.first_job,
                                        BASE_JD_REQ_FS, bos, nr_bos, NULL, 0);
      assert(frag_atom);

      if (PANVK_DEBUG(TRACE) || PANVK_DEBUG(SYNC)) {
         ASSERTED bool done =
            kbase_kmod_wait_atom(dev->kmod.dev, frag_atom, -1);
         assert(done);
            frag_atom = 0; /* already waited+consumed above; don't wait again in wait_one() */

         panvk_pool_invalidate_maps(&cmdbuf->desc_pool);
         pan_kmod_flush_bo_map_syncs(dev->kmod.dev);
      }

      if (PANVK_DEBUG(TRACE))
         pandecode_jc(dev->debug.decode_ctx, batch->frag_jc.first_job,
                      phys_dev->kmod.dev->props.gpu_id);

      if (PANVK_DEBUG(DUMP))
         pandecode_dump_mappings(dev->debug.decode_ctx);

      if (PANVK_DEBUG(SYNC))
         pandecode_abort_on_fault(dev->debug.decode_ctx, batch->frag_jc.first_job,
                                  phys_dev->kmod.dev->props.gpu_id);
   }

   if (PANVK_DEBUG(TRACE))
      pandecode_next_frame(dev->debug.decode_ctx);

   batch->issued = true;

   *out_frag_atom = frag_atom;
   return frag_atom ? frag_atom : vtc_atom;
}

/* kbase has no kernel wait primitive for VkEvent (see panvk_event.h), so
 * events are tracked as a plain host-side flag and waited on with a
 * simple spin. */
static void
panvk_wait_event_ops(struct panvk_batch *batch)
{
   util_dynarray_foreach(&batch->event_ops, struct panvk_cmd_event_op, op) {
      if (op->type != PANVK_EVENT_OP_WAIT)
         continue;

      while (!op->event->signaled)
         usleep(100);
   }
}

static void
panvk_apply_event_ops(struct panvk_batch *batch)
{
   util_dynarray_foreach(&batch->event_ops, struct panvk_cmd_event_op, op) {
      switch (op->type) {
      case PANVK_EVENT_OP_SET:
         op->event->signaled = true;
         break;
      case PANVK_EVENT_OP_RESET:
         op->event->signaled = false;
         break;
      case PANVK_EVENT_OP_WAIT:
         /* Handled before submission in panvk_wait_event_ops(). */
         break;
      default:
         UNREACHABLE("bad panvk_cmd_event_op type\n");
      }
   }
}

/* wait_func passed to panvk_kbase_sync_set_pending(): blocks on whichever
 * kbase atom numbers are non-zero in targets[]. */
static VkResult
panvk_jm_kbase_wait_atoms(void *data, const uint64_t targets[PANVK_KBASE_SYNC_TARGET_COUNT],
                          uint64_t abs_timeout_ns)
{
   struct pan_kmod_dev *kmod_dev = data;

   int64_t timeout_ns;
   if (abs_timeout_ns == UINT64_MAX) {
      timeout_ns = -1;
   } else {
      struct timespec now;
      clock_gettime(CLOCK_MONOTONIC_RAW, &now);
      int64_t now_ns = (int64_t)now.tv_sec * 1000000000ll + now.tv_nsec;
      timeout_ns = (int64_t)abs_timeout_ns - now_ns;
      if (timeout_ns < 0)
         timeout_ns = 0;
   }

   for (unsigned i = 0; i < PANVK_KBASE_SYNC_TARGET_COUNT; i++) {
      if (!targets[i])
         continue;
      if (!kbase_kmod_wait_atom(kmod_dev, targets[i], timeout_ns))
         return timeout_ns == 0 ? VK_TIMEOUT : VK_ERROR_DEVICE_LOST;
   }

   return VK_SUCCESS;
}

VkResult
panvk_per_arch(gpu_queue_submit)(struct vk_queue *vk_queue, struct vk_queue_submit *submit)
{
   struct panvk_gpu_queue *queue = container_of(vk_queue, struct panvk_gpu_queue, vk);
   struct panvk_device *dev = to_panvk_device(queue->vk.base.device);

   uint64_t targets[PANVK_KBASE_SYNC_TARGET_COUNT] = {0};
   unsigned ntargets = 0;

   for (uint32_t j = 0; j < submit->command_buffer_count; ++j) {
      struct panvk_cmd_buffer *cmdbuf =
         container_of(submit->command_buffers[j], struct panvk_cmd_buffer, vk);

      list_for_each_entry(struct panvk_batch, batch, &cmdbuf->batches, node) {
         /* FIXME: should be done at the batch level */
         unsigned nr_bos = panvk_pool_num_bos(&cmdbuf->desc_pool) +
                           panvk_pool_num_bos(&cmdbuf->varying_pool) +
                           panvk_pool_num_bos(&cmdbuf->tls_pool) +
                           batch->fb.bo_count + (batch->blit.src ? 1 : 0) +
                           (batch->blit.dst ? 1 : 0) +
                           (batch->vtc_jc.first_tiler ? 1 : 0) + 1;
         unsigned bo_idx = 0;
         struct pan_kmod_bo *bos[nr_bos];

         panvk_pool_get_bos(&cmdbuf->desc_pool, &bos[bo_idx]);
         bo_idx += panvk_pool_num_bos(&cmdbuf->desc_pool);

         panvk_pool_get_bos(&cmdbuf->varying_pool, &bos[bo_idx]);
         bo_idx += panvk_pool_num_bos(&cmdbuf->varying_pool);

         panvk_pool_get_bos(&cmdbuf->tls_pool, &bos[bo_idx]);
         bo_idx += panvk_pool_num_bos(&cmdbuf->tls_pool);

         for (unsigned i = 0; i < batch->fb.bo_count; i++)
            bos[bo_idx++] = batch->fb.bos[i];

         if (batch->blit.src)
            bos[bo_idx++] = batch->blit.src;

         if (batch->blit.dst)
            bos[bo_idx++] = batch->blit.dst;

         if (batch->vtc_jc.first_tiler)
            bos[bo_idx++] = dev->tiler_heap->bo;

         bos[bo_idx++] = dev->sample_positions->bo;
         assert(bo_idx == nr_bos);

         /* Merge identical BO entries. */
         for (unsigned x = 0; x < nr_bos; x++) {
            for (unsigned y = x + 1; y < nr_bos;) {
               if (bos[x] == bos[y])
                  bos[y] = bos[--nr_bos];
               else
                  y++;
            }
         }

         panvk_wait_event_ops(batch);

         uint64_t frag_atom = 0;
         uint64_t last_atom =
            panvk_queue_submit_batch(queue, cmdbuf, batch, bos, nr_bos,
                                     &frag_atom);

         if (last_atom) {
            if (ntargets < PANVK_KBASE_SYNC_TARGET_COUNT) {
               targets[ntargets++] = last_atom;
            } else {
               /* targets[] is full (more than PANVK_KBASE_SYNC_TARGET_COUNT
                * batches in this submit) -- instead of silently dropping
                * this atom (the old bug: a dropped frag_atom means nobody
                * ever waits for that fragment job), wait for it
                * synchronously right here, same trick already used for
                * vtc_atom above. */
               ASSERTED bool done =
                  kbase_kmod_wait_atom(dev->kmod.dev, last_atom, -1);
               assert(done);
            }
         }

         panvk_apply_event_ops(batch);
      }
   }


   panvk_kbase_sync_set_pending(queue->sync, dev->kmod.dev,
                                panvk_jm_kbase_wait_atoms, targets);

   for (unsigned i = 0; i < submit->signal_count; i++) {
      panvk_kbase_sync_set_pending(submit->signals[i].sync, dev->kmod.dev,
                                   panvk_jm_kbase_wait_atoms, targets);
   }

   return VK_SUCCESS;
}

VkResult
panvk_per_arch(create_gpu_queue)(struct panvk_device *device,
                                 const VkDeviceQueueCreateInfo *create_info,
                                 uint32_t queue_idx,
                                 struct vk_queue **out_queue)
{
   struct panvk_physical_device *phys_dev =
      to_panvk_physical_device(device->vk.physical);
   ASSERTED const VkDeviceQueueGlobalPriorityCreateInfoKHR *priority_info =
      vk_find_struct_const(create_info->pNext,
                          DEVICE_QUEUE_GLOBAL_PRIORITY_CREATE_INFO_KHR);
   ASSERTED const VkQueueGlobalPriorityKHR priority =
      priority_info ? priority_info->globalPriority
                    : VK_QUEUE_GLOBAL_PRIORITY_MEDIUM_KHR;

   /* XXX: Panfrost kernel module doesn't support priorities so far */
   assert(priority == VK_QUEUE_GLOBAL_PRIORITY_MEDIUM_KHR);

   struct panvk_gpu_queue *queue = vk_zalloc(&device->vk.alloc, sizeof(*queue), 8,
                                         VK_SYSTEM_ALLOCATION_SCOPE_DEVICE);
   if (!queue)
      return panvk_error(device, VK_ERROR_OUT_OF_HOST_MEMORY);

   VkResult result =
      vk_queue_init(&queue->vk, &device->vk, create_info, queue_idx);
   if (result != VK_SUCCESS)
      goto err_free_queue;

   /* Start signaled: with nothing submitted yet, the queue is trivially idle. */
   result = vk_sync_create(&device->vk, &phys_dev->drm_syncobj_type, 0, 1,
                           &queue->sync);
   if (result != VK_SUCCESS)
      goto err_finish_queue;

   queue->vk.driver_submit = panvk_per_arch(gpu_queue_submit);
   *out_queue = &queue->vk;
   return VK_SUCCESS;

err_finish_queue:
   vk_queue_finish(&queue->vk);

err_free_queue:
   vk_free(&device->vk.alloc, queue);
   return result;
}

void panvk_per_arch(destroy_gpu_queue)(struct vk_queue *vk_queue)
{
   struct panvk_gpu_queue *queue = container_of(vk_queue, struct panvk_gpu_queue, vk);
   struct panvk_device *dev = to_panvk_device(vk_queue->base.device);

   vk_queue_finish(&queue->vk);
   vk_sync_destroy(&dev->vk, queue->sync);
   vk_free(&dev->vk.alloc, queue);
}

VkResult
panvk_per_arch(gpu_queue_check_status)(struct vk_queue *vk_queue)
{
   return VK_SUCCESS;
}

VKAPI_ATTR VkResult VKAPI_CALL
panvk_per_arch(QueueWaitIdle)(VkQueue _queue)
{
   VK_FROM_HANDLE(panvk_gpu_queue, queue, _queue);
   struct panvk_device *dev = to_panvk_device(queue->vk.base.device);

   /* we need to use vk_common_QueueWaitIdle if we ever go threaded */
   assert(queue->vk.submit.mode != VK_QUEUE_SUBMIT_MODE_THREADED);

   if (vk_device_is_lost(&dev->vk)) {
      /* Check printf buffer one more time before exiting */
      u_printf_with_ctx(stdout, &dev->printf.ctx);
      return VK_ERROR_DEVICE_LOST;
   }

   VkResult result = vk_sync_wait(&dev->vk, queue->sync, 0,
                                  VK_SYNC_WAIT_COMPLETE, UINT64_MAX);
   if (result != VK_SUCCESS)
      return VK_ERROR_DEVICE_LOST;

   return VK_SUCCESS;
}
