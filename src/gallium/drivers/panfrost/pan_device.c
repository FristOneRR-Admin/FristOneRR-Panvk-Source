/*
 * Copyright (C) 2019 Collabora, Ltd.
 * SPDX-License-Identifier: MIT
 */

#include <xf86drm.h>

#include "drm-uapi/panfrost_drm.h"
#include "util/hash_table.h"
#include "util/macros.h"
#include "util/u_math.h"
#include "util/u_thread.h"
#include "pan_bo.h"
#include "pan_device.h"
#include "pan_encoder.h"
#include "pan_samples.h"
#include "pan_util.h"
#include "wrap.h"

#ifdef HAVE_PAN_KMOD_KBASE
#include <fcntl.h>
#include <stdlib.h>
#include "kmod/pan_kmod.h"

/* Command submission on kbase (CSF queue groups / JM job atoms) is not
 * implemented yet: a GL context would fail or crash at creation time since
 * the submission paths hardcode the panthor/panfrost DRM uAPIs.  Until that
 * lands, refuse to expose a Gallium device on kbase so GL loaders cleanly
 * fall back — Vulkan device enumeration through panvk is unaffected. */
static bool
panfrost_gl_on_kbase_allowed(void)
{
   const char *env = getenv("PAN_EXPERIMENTAL_KBASE_GL");
   if (env && env[0] == '1' && env[1] == '\0')
      return true;

   mesa_logw("panfrost: found a kbase GPU, but OpenGL on kbase requires "
             "command submission support that is not implemented yet; not "
             "exposing a Gallium device (Vulkan enumeration via panvk still "
             "works). Set PAN_EXPERIMENTAL_KBASE_GL=1 to bypass.");
   return false;
}
#endif

/* DRM_PANFROST_PARAM_TEXTURE_FEATURES0 will return a bitmask of supported
 * compressed formats, so we offer a helper to test if a format is supported */

bool
panfrost_supports_compressed_format(struct panfrost_device *dev,
                                    unsigned texfeat_bit)
{
   assert(texfeat_bit < 32);
   return dev->compressed_formats & BITFIELD_BIT(texfeat_bit);
}

int
panfrost_open_device(void *memctx, int fd, struct panfrost_device *dev)
{
   dev->memctx = memctx;

   dev->kmod.dev = pan_kmod_dev_create(fd, PAN_KMOD_DEV_FLAG_OWNS_FD, NULL);

#ifdef HAVE_PAN_KMOD_KBASE
   /* If the DRM detection failed (e.g. the fd is a /dev/mali* kbase fd
    * rather than a DRM render node), retry with the kbase backend. */
   if (!dev->kmod.dev) {
      dev->kmod.dev = pan_kmod_dev_create_with_driver(
         fd, PAN_KMOD_DEV_FLAG_OWNS_FD, "kbase", NULL, NULL);

      if (dev->kmod.dev && !panfrost_gl_on_kbase_allowed()) {
         /* Destroying the device closes the fd (OWNS_FD). */
         pan_kmod_dev_destroy(dev->kmod.dev);
         dev->kmod.dev = NULL;
         return -1;
      }
   }
#endif

   if (!dev->kmod.dev) {
      close(fd);
      return -1;
   }

   dev->arch = pan_arch(dev->kmod.dev->props.gpu_id);
   dev->model = pan_get_model(dev->kmod.dev->props.gpu_id,
                              dev->kmod.dev->props.gpu_variant);

   /* If we don't recognize the model, bail early */
   if (!dev->model)
      goto err_free_kmod_dev;

   /* 48bit address space max, with the lower 32MB reserved. We clamp
    * things so it matches kmod VA range limitations.
    */
   uint64_t user_va_start =
      pan_clamp_to_usable_va_range(dev->kmod.dev, PAN_VA_USER_START);
   uint64_t user_va_end =
      pan_clamp_to_usable_va_range(dev->kmod.dev, PAN_VA_USER_END);

   dev->kmod.vm = pan_kmod_vm_create(
      dev->kmod.dev, PAN_KMOD_VM_FLAG_AUTO_VA | PAN_KMOD_VM_FLAG_TRACK_ACTIVITY,
      user_va_start, user_va_end - user_va_start);
   if (!dev->kmod.vm)
      goto err_free_kmod_dev;

   dev->core_count = pan_query_core_count(&dev->kmod.dev->props);
   dev->core_id_range = pan_query_core_id_range(&dev->kmod.dev->props);
   dev->thread_tls_alloc = pan_query_thread_tls_alloc(&dev->kmod.dev->props);
   dev->optimal_tib_size = pan_query_optimal_tib_size(dev->arch, dev->model);
   dev->optimal_z_tib_size =
      pan_query_optimal_z_tib_size(dev->arch, dev->model);
   dev->compressed_formats =
      pan_query_compressed_formats(&dev->kmod.dev->props);
   dev->tiler_features = pan_query_tiler_features(&dev->kmod.dev->props);
   dev->has_afbc = pan_query_afbc(&dev->kmod.dev->props);
   dev->has_afrc = pan_query_afrc(&dev->kmod.dev->props);
   dev->formats = pan_format_table(dev->arch);
   dev->blendable_formats = pan_blendable_format_table(dev->arch);

   util_sparse_array_init(&dev->bo_map, sizeof(struct panfrost_bo), 512);

   pthread_mutex_init(&dev->bo_cache.lock, NULL);
   list_inithead(&dev->bo_cache.lru);

   for (unsigned i = 0; i < ARRAY_SIZE(dev->bo_cache.buckets); ++i)
      list_inithead(&dev->bo_cache.buckets[i]);

   /* Initialize pandecode before we start allocating */
   if (dev->debug & (PAN_DBG_TRACE | PAN_DBG_SYNC)) {
      dev->decode_ctx = pandecode_create_context(!(dev->debug & PAN_DBG_TRACE));
      pandecode_set_disassemble(dev->decode_ctx, pan_disassemble);
   }

   /* Tiler heap is internally required by the tiler, which can only be
    * active for a single job chain at once, so a single heap can be
    * shared across batches/contextes.
    *
    * Heap management is completely different on CSF HW, don't allocate the
    * heap BO in that case.
    */

   if (dev->arch < 10) {
      dev->tiler_heap = panfrost_bo_create(
         dev, 128 * 1024 * 1024, PAN_BO_INVISIBLE | PAN_BO_GROWABLE, "Tiler heap");
      if (!dev->tiler_heap)
         goto err_free_kmod_dev;
   }

   pthread_mutex_init(&dev->submit_lock, NULL);

   /* Done once on init */
   dev->sample_positions = panfrost_bo_create(
      dev, pan_sample_positions_buffer_size(), 0, "Sample positions");
   if (!dev->sample_positions)
      goto err_free_kmod_dev;

   pan_upload_sample_positions(dev->sample_positions->ptr.cpu);
   return 0;

err_free_kmod_dev:
   if (dev->decode_ctx)
      pandecode_destroy_context(dev->decode_ctx);

   panfrost_bo_unreference(dev->tiler_heap);
   panfrost_bo_unreference(dev->sample_positions);

   if (dev->kmod.vm)
      pan_kmod_vm_destroy(dev->kmod.vm);

   pan_kmod_dev_destroy(dev->kmod.dev);
   dev->kmod.dev = NULL;
   return -1;
}

void
panfrost_close_device(struct panfrost_device *dev)
{
   /* If we don't recognize the model, the rest of the device won't exist,
    * we will have early-exited the device open.
    */
   if (dev->model) {
      pthread_mutex_destroy(&dev->submit_lock);
      panfrost_bo_unreference(dev->tiler_heap);
      panfrost_bo_unreference(dev->sample_positions);
      panfrost_bo_cache_evict_all(dev);
      pthread_mutex_destroy(&dev->bo_cache.lock);
      util_sparse_array_finish(&dev->bo_map);
   }

   if (dev->kmod.vm)
      pan_kmod_vm_destroy(dev->kmod.vm);

   if (dev->kmod.dev)
      pan_kmod_dev_destroy(dev->kmod.dev);
}

#ifdef HAVE_PAN_KMOD_KBASE
/**
 * panfrost_open_device_kbase - open a Panfrost device via the Mali kbase driver.
 *
 * Opens @path (e.g. "/dev/mali0"), creates a kbase kmod device, and
 * initialises @dev identically to panfrost_open_device().  The caller is
 * responsible for calling panfrost_close_device() when finished.
 *
 * Returns 0 on success, -1 on failure.
 */
int
panfrost_open_device_kbase(void *memctx, const char *path,
                           struct panfrost_device *dev)
{
   int fd = open(path, O_RDWR | O_CLOEXEC);
   if (fd < 0) {
      mesa_loge("panfrost: failed to open %s: %s", path, strerror(errno));
      return -1;
   }

   dev->memctx = memctx;

   dev->kmod.dev = pan_kmod_dev_create_with_driver(
      fd, PAN_KMOD_DEV_FLAG_OWNS_FD, "kbase", NULL, NULL);
   if (!dev->kmod.dev) {
      mesa_loge("panfrost: failed to create kbase kmod device for %s", path);
      close(fd);
      return -1;
   }

   if (!panfrost_gl_on_kbase_allowed()) {
      /* Destroying the device closes the fd (OWNS_FD). */
      pan_kmod_dev_destroy(dev->kmod.dev);
      dev->kmod.dev = NULL;
      return -1;
   }

   dev->arch = pan_arch(dev->kmod.dev->props.gpu_id);
   dev->model = pan_get_model(dev->kmod.dev->props.gpu_id,
                              dev->kmod.dev->props.gpu_variant);

   if (!dev->model) {
      mesa_loge("panfrost: unrecognised GPU ID 0x%"PRIx64,
                dev->kmod.dev->props.gpu_id);
      goto err_free_kmod_dev;
   }

   uint64_t user_va_start =
      pan_clamp_to_usable_va_range(dev->kmod.dev, PAN_VA_USER_START);
   uint64_t user_va_end =
      pan_clamp_to_usable_va_range(dev->kmod.dev, PAN_VA_USER_END);

   dev->kmod.vm = pan_kmod_vm_create(
      dev->kmod.dev, PAN_KMOD_VM_FLAG_AUTO_VA | PAN_KMOD_VM_FLAG_TRACK_ACTIVITY,
      user_va_start, user_va_end - user_va_start);
   if (!dev->kmod.vm)
      goto err_free_kmod_dev;

   dev->core_count =
      pan_query_core_count(&dev->kmod.dev->props, &dev->core_id_range);
   dev->thread_tls_alloc = pan_query_thread_tls_alloc(&dev->kmod.dev->props);
   dev->optimal_tib_size = pan_query_optimal_tib_size(dev->arch, dev->model);
   dev->optimal_z_tib_size =
      pan_query_optimal_z_tib_size(dev->arch, dev->model);
   dev->compressed_formats =
      pan_query_compressed_formats(&dev->kmod.dev->props);
   dev->tiler_features = pan_query_tiler_features(&dev->kmod.dev->props);
   dev->has_afbc = pan_query_afbc(&dev->kmod.dev->props);
   dev->has_afrc = pan_query_afrc(&dev->kmod.dev->props);
   dev->formats = pan_format_table(dev->arch);
   dev->blendable_formats = pan_blendable_format_table(dev->arch);

   util_sparse_array_init(&dev->bo_map, sizeof(struct panfrost_bo), 512);

   pthread_mutex_init(&dev->bo_cache.lock, NULL);
   list_inithead(&dev->bo_cache.lru);

   for (unsigned i = 0; i < ARRAY_SIZE(dev->bo_cache.buckets); ++i)
      list_inithead(&dev->bo_cache.buckets[i]);

   if (dev->debug & (PAN_DBG_TRACE | PAN_DBG_SYNC))
      dev->decode_ctx = pandecode_create_context(!(dev->debug & PAN_DBG_TRACE));

   if (dev->arch < 10) {
      dev->tiler_heap = panfrost_bo_create(
         dev, 128 * 1024 * 1024, PAN_BO_INVISIBLE | PAN_BO_GROWABLE,
         "Tiler heap");
      if (!dev->tiler_heap)
         goto err_free_kmod_dev;
   }

   pthread_mutex_init(&dev->submit_lock, NULL);

   dev->sample_positions = panfrost_bo_create(
      dev, pan_sample_positions_buffer_size(), 0, "Sample positions");
   if (!dev->sample_positions)
      goto err_free_kmod_dev;

   pan_upload_sample_positions(dev->sample_positions->ptr.cpu);
   return 0;

err_free_kmod_dev:
   if (dev->decode_ctx)
      pandecode_destroy_context(dev->decode_ctx);

   panfrost_bo_unreference(dev->tiler_heap);
   panfrost_bo_unreference(dev->sample_positions);

   if (dev->kmod.vm)
      pan_kmod_vm_destroy(dev->kmod.vm);

   pan_kmod_dev_destroy(dev->kmod.dev);
   dev->kmod.dev = NULL;
   return -1;
}
#endif /* HAVE_PAN_KMOD_KBASE */
