# kbase panvk: Minecraft/zink device-lost resolution

Symptom: Minecraft 1.20.4 through zink entered the world and rendered, but
after some minutes of play the device was lost.  Two distinct failure
signatures were involved and are both resolved:

1. `CSF group 0/1/2 fatal error: status 0x??7002c0 (exception 0xc0)` with a
   sideband address far outside every mapped GPU VA range (e.g.
   `0x80ff3f7fe7c0`, `0xa6953f480400` on a 39-bit-VA device).
2. `CSF group 0 tiler heap OOM notification` followed by subqueue timeouts,
   with the kernel logging
   `Invalid Heap statistics provided by firmware: vt_start X, vt_end Y, frag_end Z`
   and `Queue group to be terminated, couldn't handle the OoM event`.

Benchmarks (vkcube, vkmark, glmark2/zink) never reproduced either signature;
sustained gameplay reproduced one of them within minutes.  Live tiler-heap
state was captured through `/sys/kernel/debug/mali0/ctx/*/tiler_heaps`
(match our heaps by `max_chunks`; every process has a heap context at the
same standard VA), and kernel-side evidence through `/dev/kmsg`, which is
readable from the container even though `dmesg` is not.

## Failure 1: dangling heap context on renewal (wild-pointer 0xc0)

The tiler-heap renewal workaround (see kbase-triangle-hang-analysis.md)
destroyed the old heap context immediately after draining the queue.  But
each graphics CS re-arms `HEAP_SET` only in its *next* ring-buffer entry:
between `TILER_HEAP_TERM` and that next entry, the firmware still holds the
old heap context.  kbase frees the old heap's chunks at TERM time and the
custom-VA allocator reuses their address slots — under Minecraft's
allocation churn, within milliseconds.  When the firmware then walked the
old context (CSG suspend/resume under Android-side slot competition, or
heap-state writeback at the `HEAP_SET` switch) it interpreted foreign data
as a chunk list and issued a read at a garbage address, which the MMU
reported as a context-wide translation fault, killing all three groups.

The pre-crash log made this visible: renewal `first chunk` addresses, stable
for minutes, started jumping (`0x6000002000`, `0x6001202000`, `0x6002002000`
…) as other allocations claimed freed chunk VAs, and the fatal always
followed a renewal immediately.

Fix: retire the old context instead of destroying it.  The retired context
is destroyed at a later renewal only once both graphics subqueues'
emitted-job counters have passed the values recorded at retirement (their
ring entries re-issue `HEAP_SET`, and the pre-renewal drain proves they
completed).  Queue teardown also terminates the CS groups before destroying
heap contexts.

## Failure 2: heap statistics validation on the OOM path

With the wild-pointer fix in place, sustained play died on tiler-heap OOM
instead — at ~50 of 200 chunks, with gigabytes of memory available, so
neither the chunk cap nor memory pressure (nor hugepage fragmentation,
despite order-9 free lists being empty on a long-running Android system —
that was a red herring).  `/dev/kmsg` had the real reason: the kernel
validates the heap statistics the firmware attaches to every chunk-grow
request and terminates the group with `-EINVAL` when they are inconsistent.

Both possible statistics shapes produced by the fork's design fail that
validation:

- Cross-CSG accounting: `VERTEX_TILER_STARTED/COMPLETED` execute on the VT
  group's CS while `FRAGMENT_COMPLETED` executes on the fragment group's CS,
  and heap renewal resets generations underneath both (heap context slots
  ping-pong between two addresses).  The counters observed at the kill were
  `vt_start 308, vt_end 307, frag_end 813` — `frag_end > vt_end` is
  rejected.  (This also finally explains why firmware chunk recycling never
  worked across CSGs: the started/completed pairing the firmware needs is
  split across two command streams.)
- Suppressing all heap operations yields `vt_start 0, vt_end 0, frag_end 0`,
  which the same validation also rejects: a tiler OOM with zero render
  passes in flight is treated as a firmware error.

Fix: on kbase, emit **only** `VERTEX_TILER_STARTED` (one instruction per
render pass, in the VT stream) and suppress `VERTEX_TILER_COMPLETED`,
`FRAGMENT_COMPLETED`, `FINISH_FRAGMENT`, and the tiler-OOM incremental-
rendering handler registration.  The statistics then always validate
(`0 <= 0 <= N`, `nr_in_flight = N >= 1`), the kernel grows the heap
normally, and firmware chunk recycling stays disarmed, which is correct
because wholesale heap renewal is the recycling mechanism on kbase.  The
renewal interval default is 8 graphics submissions (worst observed growth
per window ~100 MiB); `PANVK_KBASE_HEAP_RENEW_INTERVAL` overrides it, 0
disables renewal.

Supporting changes: 1 MiB heap chunks (avoids the kernel's hugepage-backed
chunk path; the GPU MMU provides virtual contiguity from order-0 pages) with
max_chunks scaled to 400 to keep the byte budget, and
`BASE_QUEUE_GROUP_PRIORITY_HIGH` for our CS groups to reduce CSG rotation
(fewer suspend/resume transitions and less exposure of off-slot heaps to the
Pixel kernel's heap-reclaim shrinker).

Validated on-device: extended Minecraft 1.20.4 play including a
large-biome stress area, plus vkcube/vkmark/glmark2-zink regression runs,
with no faults, no OOM group terminations, and no hangs.
