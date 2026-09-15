# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this fork is

A fork of Mesa (upstream: https://gitlab.freedesktop.org/mesa/mesa) whose purpose is to add a
**kbase backend** to Panfrost/PanVK — i.e. run Mesa's Mali drivers on top of Arm's proprietary
`kbase` kernel driver (`/dev/mali*`, r32p0–r44p0) instead of the upstream `panfrost`/`panthor`
DRM drivers. The target device is the Google Pixel 7 (Mali-G710, Valhall/CSF, arch ≥ 10).
All custom work sits on top of upstream commit `e24dc5bd1e7`; everything after that commit is
fork-specific.

## Build

Mesa uses Meson. The canonical fork build configuration is in
`.github/workflows/pixel7-kbase-debug.yml` (CI cross-check: aarch64 debug build on Debian 13).
The key non-default option is:

```sh
meson setup build \
  -Dgallium-drivers=panfrost \
  -Dvulkan-drivers=panfrost \
  -Dpanfrost-kmds=kbase,panthor \
  -Dplatforms=wayland -Dglx=disabled
meson compile -C build
```

- `-Dpanfrost-kmds` (defined in `meson.options`) selects which kernel-driver backends are
  compiled in: any of `panfrost`, `panthor`, `kbase`. Each enabled KMD defines
  `HAVE_PAN_KMOD_<NAME>`; all kbase-specific code must stay behind `#if defined(HAVE_PAN_KMOD_KBASE)`
  so builds without it stay clean. At least one KMD must be enabled.
- Run a single test: `meson test -C build <test-name>`; list tests with `meson test -C build --list`.
  CI builds with `-Dbuild-tests=false`, so enable tests locally if needed.
- GitHub Actions builds on every push and uploads the Mesa install tree as an artifact
  (`mesa-pixel7-kbase-debug-aarch64.zip`).

## Architecture of the kbase support

### The pan_kmod abstraction (`src/panfrost/lib/kmod/`)

All Panfrost userspace (both the Gallium driver and PanVK) talks to the kernel through the
`pan_kmod` vtable (`pan_kmod.h` / `pan_kmod_backend.h`). Backends: `panfrost_kmod.c`,
`panthor_kmod.c`, and the fork-added **`kbase_kmod.c`**. `pan_kmod.c` dispatches by driver
name; `pan_kmod_dev_create()` uses `drmGetVersion()`, which fails on a kbase fd — callers that
may hold a kbase fd fall back to `pan_kmod_dev_create_with_driver(fd, flags, "kbase", ...)`.

kbase is fundamentally different from the DRM backends (see the header comment in
`kbase_kmod.c` — read it before touching that file):

- The fd is **not a DRM fd**. The handshake is VERSION_CHECK → SET_FLAGS → mmap of the
  tracking page; **all other ioctls return -EPERM before that**. The two kbase flavours use
  different VERSION_CHECK ioctl numbers: CSF (arch ≥ 10, uAPI 1.x) is nr **52**, JM
  (arch ≤ 9, uAPI 11.x) is nr **0** — probe CSF first, then JM.
- No GEM handles — `kbase_kmod_dev` mints its own u32 handles for the shared `handle_to_bo`
  sparse array.
- **SAME_VA memory model**: for 64-bit clients the kernel forces SAME_VA on non-executable
  allocations. `MEM_ALLOC` returns a *cookie*, and mmap()-ing the fd at that cookie creates
  the mapping with **CPU VA == GPU VA**. The backend mmaps every BO at allocation time and
  keeps the mapping until `bo_free` (munmap of a SAME_VA region destroys the GPU mapping —
  free-on-close). The optional `bo_mmap`/`bo_munmap` ops in `pan_kmod_ops` exist for this;
  callers must use `pan_kmod_bo_munmap()`, never raw `os_munmap()`, on BO mappings.
- GPU-executable BOs come from the EXEC_VA zone (`MEM_EXEC_INIT` at device open) and return
  a real GPU VA that doubles as the mmap offset.
- `drmPrimeFDToHandle()` doesn't work → `pan_kmod_bo_import()` fails gracefully. dma-buf
  import / WSI is future work. `PAN_KMOD_VM_OP_MODE_ASYNC` and explicit-VA `vm_bind` are
  unsupported.
- ioctl UAPI lives in `include/drm-uapi/mali_kbase_ioctl.h`, assembled from the real Arm
  kbase uAPI headers (values cross-checked against panfork and shipping kernel sources —
  do not invent values; verify against `drivers/gpu/arm/bifrost` in a vendor kernel tree).
  GPU properties come from a key/size-encoded props blob that `kbase_kmod.c` parses.
- **GL on kbase is gated off** in `pan_device.c` (no submission support yet); bypass with
  `PAN_EXPERIMENTAL_KBASE_GL=1`. Vulkan (panvk) enumeration works without the gate.

### Device discovery (three entry paths, all enumerate `/dev/mali0`..`/dev/mali7`)

`PAN_KBASE_MAX_NODES` (= 8) in `pan_kmod.h` is the single shared constant for node enumeration.

1. **PanVK**: `panvk_instance.c` enumerates DRM devices first, then kbase nodes;
   `panvk_physical_device_init_kbase()` (`panvk_physical_device.c`) opens the node. A failed
   open returns `VK_ERROR_INCOMPATIBLE_DRIVER` and enumeration continues (probe permission
   errors are expected and logged quietly).
2. **Gallium/pipe-loader**: `pipe_loader_drm.c` has `pipe_loader_kbase_probe()` using a
   dedicated `kbase_driver_descriptor`; wired through `drm_helper.h` and the panfrost winsys
   (`panfrost_open_device_kbase()` in `pan_device.c`).
3. **Fd-based fallback**: when DRM version detection fails on an fd handed to the panfrost
   Gallium driver, it retries with the kbase backend.

### Command submission on kbase (CSF, synchronous model)

panvk submits work on kbase through userspace-owned CS ring buffers
(`csf/panvk_vX_gpu_queue.c`, kbase branches guarded by `HAVE_PAN_KMOD_KBASE` +
`gpu_queue_uses_kbase()`): one queue group per Vulkan queue with one 64K ring per panvk
subqueue, bound via `CS_QUEUE_REGISTER/BIND`, USER_IO pages mmapped from the bind cookie.
Every submission emits the same ring sequence the panthor kernel uses (FLUSH_CACHE2 gated on
LATEST_FLUSH → CALL → SYNC_ADD64 on a per-subqueue seqno cell, deferred on all scoreboard
slots), clobbering only the 4 FW-unpreserved registers, then publishes CS_INSERT and kicks.
All touched subqueues must be kicked before waiting on any (their streams cross-synchronize).
CSF-generic panvk code must use `panvk_get_csif_props()` / `panvk_get_flush_id()`
(`panvk_device.h`) — never the `panthor_kmod_*` variants directly.

**Tiler heap on kbase** (see `docs/kbase-minecraft-fault-analysis.md`): each Vulkan queue owns
a kbase tiler heap (1 MiB chunks, max 400) that is renewed wholesale (create new + retire old
ctx) every `KBASE_TILER_HEAP_RENEW_INTERVAL` (8) graphics submissions after draining;
`PANVK_KBASE_HEAP_RENEW_INTERVAL` overrides, 0 disables. The retired ctx is destroyed only at
a later renewal once both graphics subqueues re-armed HEAP_SET (destroying it immediately gave
firmware a dangling chunk list -> wild-pointer 0xc0 faults). On kbase the command streams emit
only VERTEX_TILER_STARTED — no VERTEX_TILER_COMPLETED / FRAGMENT_COMPLETED / FINISH_FRAGMENT,
and no tiler-OOM IR handler (`cmdbuf_skips_gpu_heap_ops()` in `csf/panvk_vX_cmd_draw.c`): the
kernel validates heap statistics on every chunk-grow request and kills the group when
`frag_end > vt_end` (cross-CSG counter mixing) **or** when nothing is in flight (all-zero
counters), so started-only is the only shape that always validates.

**Synchronization is synchronous**: submissions are CPU-waited by polling seqno cells,
semaphore waits/signals resolve on the CPU (`kbase_cpu_sync_type` spin-wait syncs in
`panvk_physical_device.c`). Async submission (kbase fences/KCPU queues), sparse binding
(BIND queue family is a stub), dma-buf import/WSI, and `bo_wait` remain future work.

## Conventions

- Follow upstream Mesa style (`.editorconfig`, `.clang-format`); 3-space indent in C.
- Commit messages use upstream Mesa prefixes: `panvk:`, `panfrost:`, `kbase:`, `kbase_kmod:`,
  `pipe-loader:` etc.
- Do not break the non-kbase build: changes shared with upstream code paths (pipe-loader,
  pan_kmod core, panvk) must compile with `-Dpanfrost-kmds=panfrost,panthor` alone.
