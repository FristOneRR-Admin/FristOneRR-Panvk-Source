/*
 * Copyright (C) 2022 Collabora Ltd.
 * SPDX-License-Identifier: MIT
 */

/* Bottom-up local scheduler to reduce register pressure */

#include "util/dag.h"
#include "compiler.h"

struct sched_ctx {
   /* Dependency graph */
   struct dag *dag;

   /* Live set */
   BITSET_WORD *live;

   /* Whether a latency tie-break changed the otherwise pressure-only order. */
   bool latency_tiebreak_used;
};

struct sched_node {
   struct dag_node dag;

   /* Instruction this node represents */
   bi_instr *instr;
};

static void
add_dep(struct sched_node *a, struct sched_node *b)
{
   if (a && b)
      dag_add_edge(&a->dag, &b->dag, 0);
}

static struct dag *
create_dag(bi_context *ctx, bi_block *block, void *memctx)
{
   struct dag *dag = dag_create(ctx);

   struct sched_node **last_write =
      calloc(ctx->ssa_alloc, sizeof(struct sched_node *));
   struct sched_node *coverage = NULL;
   struct sched_node *preload = NULL;

   /* Last memory load, to serialize stores against */
   struct sched_node *memory_load = NULL;

   /* Last memory store, to serialize loads and stores against */
   struct sched_node *memory_store = NULL;

   bi_foreach_instr_in_block(block, I) {
      /* Leave branches at the end */
      if (I->op == BI_OPCODE_JUMP || bi_get_opcode_props(I)->branch)
         break;

      assert(I->branch_target == NULL);

      struct sched_node *node = rzalloc(memctx, struct sched_node);
      node->instr = I;
      dag_init_node(dag, &node->dag);

      /* Reads depend on writes, no other hazards in SSA */
      bi_foreach_ssa_src(I, s)
         add_dep(node, last_write[I->src[s].value]);

      bi_foreach_dest(I, d)
         last_write[I->dest[d].value] = node;

      add_dep(node, preload);

      switch (bi_get_opcode_props(I)->message) {
      case BIFROST_MESSAGE_LOAD:
         /* Regular memory loads needs to be serialized against
          * other memory access. However, UBO memory is read-only
          * so it can be moved around freely.
          */
         if (I->seg != BI_SEG_UBO) {
            add_dep(node, memory_store);
            /* Chain loads together so a store cannot be scheduled
             * between two loads to the same address. Without alias
             * analysis we conservatively serialize all loads.
             */
            add_dep(node, memory_load);
            memory_load = node;
         }

         break;

      case BIFROST_MESSAGE_ATTRIBUTE:
         /* Regular attribute loads can be reordered, but
          * writeable attributes can't be. Our one use of
          * writeable attributes are images.
          */
         if ((I->op == BI_OPCODE_LD_TEX) || (I->op == BI_OPCODE_LD_TEX_IMM) ||
             (I->op == BI_OPCODE_LD_ATTR_TEX)) {
            add_dep(node, memory_store);
            add_dep(node, memory_load);
            memory_load = node;
         }

         break;

      case BIFROST_MESSAGE_STORE:
         assert(I->seg != BI_SEG_UBO);
         add_dep(node, memory_load);
         add_dep(node, memory_store);
         memory_store = node;
         break;

      case BIFROST_MESSAGE_ATOMIC:
      case BIFROST_MESSAGE_BARRIER:
         add_dep(node, memory_load);
         add_dep(node, memory_store);
         memory_load = node;
         memory_store = node;
         break;

      case BIFROST_MESSAGE_BLEND:
      case BIFROST_MESSAGE_Z_STENCIL:
      case BIFROST_MESSAGE_TILE:
         add_dep(node, coverage);
         coverage = node;
         break;

      case BIFROST_MESSAGE_ATEST:
         /* ATEST signals the end of shader side effects */
         add_dep(node, memory_store);
         memory_store = node;

         /* ATEST also updates coverage */
         add_dep(node, coverage);
         coverage = node;
         break;
      default:
         break;
      }

      if (I->op == BI_OPCODE_DISCARD_F32) {
         /* Serialize against ATEST */
         add_dep(node, coverage);
         coverage = node;
      }
      if (I->op == BI_OPCODE_DISCARD_F32 ||
          bi_is_scheduling_barrier(I)) {
         /* Serialize against memory operations and barriers.
          *
          * TODO: This is *not* quite sufficient in the case of a scheduling
          * barrier. We need to serialize against *all* operations with
          * side-effects in that case.
          */
         add_dep(node, memory_load);
         add_dep(node, memory_store);
         memory_load = node;
         memory_store = node;
      }
      if ((I->op == BI_OPCODE_PHI) ||
          (I->op == BI_OPCODE_MOV_I32 &&
           I->src[0].type == BI_INDEX_REGISTER)) {
         preload = node;
      }
   }

   free(last_write);

   return dag;
}

/*
 * Calculate the change in register pressure from scheduling a given
 * instruction. Equivalently, calculate the difference in the number of live
 * registers before and after the instruction, given the live set after the
 * instruction. This calculation follows immediately from the dataflow
 * definition of liveness:
 *
 *      live_in = (live_out - KILL) + GEN
 */
static signed
calculate_pressure_delta(bi_instr *I, BITSET_WORD *live)
{
   signed delta = 0;

   /* Destinations must be unique */
   bi_foreach_dest(I, d) {
      if (BITSET_TEST(live, I->dest[d].value))
         delta -= bi_count_write_registers(I, d);
   }

   bi_foreach_ssa_src(I, src) {
      /* Filter duplicates */
      bool dupe = false;

      for (unsigned i = 0; i < src; ++i) {
         if (bi_is_equiv(I->src[i], I->src[src])) {
            dupe = true;
            break;
         }
      }

      if (!dupe && !BITSET_TEST(live, I->src[src].value))
         delta += bi_count_read_registers(I, src);
   }

   return delta;
}

/* Input messages have enough latency that placing independent ALU between the
 * message and its consumer is generally preferable.  This scheduler works
 * bottom-up, so de-prioritizing an input message among equal-pressure ready
 * instructions moves it earlier in the final forward instruction stream.
 *
 * Keep stores, atomics, barriers and framebuffer messages out of this class:
 * they don't produce a value whose latency can be hidden, and moving them
 * earlier only lengthens side-effect lifetimes.
 */
static bool
is_latency_hiding_message(const bi_instr *I)
{
   switch (bi_get_opcode_props(I)->message) {
   case BIFROST_MESSAGE_VARYING:
   case BIFROST_MESSAGE_ATTRIBUTE:
   case BIFROST_MESSAGE_TEX:
   case BIFROST_MESSAGE_VARTEX:
   case BIFROST_MESSAGE_LOAD:
   case BIFROST_MESSAGE_64BIT:
      return true;
   default:
      return false;
   }
}

/*
 * Choose the next instruction, bottom-up. For now we use a simple greedy
 * heuristic: choose the instruction that has the best effect on liveness.
 */
static struct sched_node *
choose_instr(struct sched_ctx *s, signed pressure, signed pressure_limit,
             bool valhall)
{
   int32_t min_delta = INT32_MAX;
   int32_t min_non_message_delta = INT32_MAX;
   struct sched_node *best = NULL;
   struct sched_node *best_non_message = NULL;

   list_for_each_entry(struct sched_node, n, &s->dag->heads, dag.link) {
      int32_t delta = calculate_pressure_delta(n->instr, s->live);
      bool message = is_latency_hiding_message(n->instr);

      if (!message && delta < min_non_message_delta) {
         best_non_message = n;
         min_non_message_delta = delta;
      }

      if (delta < min_delta ||
          (delta == min_delta && best &&
           is_latency_hiding_message(best->instr) &&
           !message)) {
         if (delta == min_delta && best)
            s->latency_tiebreak_used = true;

         best = n;
         min_delta = delta;
      }
   }

   /* Register pressure only affects occupancy when it crosses the block's
    * existing high-water mark.  If the pressure-greedy choice would issue an
    * input message late, use otherwise idle pressure headroom to schedule
    * independent work first.  In the resulting forward schedule the message
    * is hoisted and its consumer chain is pushed away, hiding latency without
    * reducing occupancy.
    *
    * Keep this Valhall-only. Bifrost has a separate clause scheduler with its
    * own message placement constraints after register allocation.
    */
   if (valhall && best && is_latency_hiding_message(best->instr) &&
       best_non_message &&
       pressure + min_non_message_delta <= pressure_limit) {
      best = best_non_message;
      s->latency_tiebreak_used = true;
   }

   return best;
}

static void
pressure_schedule_block(bi_context *ctx, bi_block *block, struct sched_ctx *s)
{
   s->latency_tiebreak_used = false;

   /* off by a constant, that's ok */
   signed pressure = 0;
   signed orig_max_pressure = 0;
   unsigned nr_ins = 0;

   memcpy(s->live, block->ssa_live_out, BITSET_BYTES(ctx->ssa_alloc));

   bi_foreach_instr_in_block_rev(block, I) {
      pressure += calculate_pressure_delta(I, s->live);
      orig_max_pressure = MAX2(pressure, orig_max_pressure);
      bi_liveness_ins_update_ssa(s->live, I);
      nr_ins++;
   }

   memcpy(s->live, block->ssa_live_out, BITSET_BYTES(ctx->ssa_alloc));

   /* off by a constant, that's ok */
   signed max_pressure = 0;
   pressure = 0;

   struct sched_node **schedule = calloc(nr_ins, sizeof(struct sched_node *));
   nr_ins = 0;

   while (!list_is_empty(&s->dag->heads)) {
      struct sched_node *node =
         choose_instr(s, pressure, orig_max_pressure, ctx->arch >= 9);
      pressure += calculate_pressure_delta(node->instr, s->live);
      max_pressure = MAX2(pressure, max_pressure);
      dag_prune_head(s->dag, &node->dag);

      schedule[nr_ins++] = node;
      bi_liveness_ins_update_ssa(s->live, node->instr);
   }

   /* Keep an equal-pressure Valhall schedule only when the latency tie-break
    * actually moved an input message earlier.  Bifrost still has a later
    * clause scheduler, so preserve its pressure-only policy here.
    */
   if (max_pressure > orig_max_pressure ||
       (max_pressure == orig_max_pressure &&
        (ctx->arch < 9 || !s->latency_tiebreak_used))) {
      free(schedule);
      return;
   }

   /* Apply the schedule */
   for (unsigned i = 0; i < nr_ins; ++i) {
      bi_remove_instruction(schedule[i]->instr);
      list_add(&schedule[i]->instr->link, &block->instructions);
   }

   free(schedule);
}

void
bi_pressure_schedule(bi_context *ctx)
{
   bi_compute_liveness_ssa(ctx);
   void *memctx = ralloc_context(ctx);
   BITSET_WORD *live =
      ralloc_array(memctx, BITSET_WORD, BITSET_WORDS(ctx->ssa_alloc));

   bi_foreach_block(ctx, block) {
      struct sched_ctx sctx = {.dag = create_dag(ctx, block, memctx),
                               .live = live};

      pressure_schedule_block(ctx, block, &sctx);
   }

   ralloc_free(memctx);
}
