#!/usr/bin/env python3
"""
patch_sphere.py

Patches panvk_sphere_real.c -> panvk_sphere_real_v2.c with:
  1. Uncapped FPS (IMMEDIATE present mode if supported, else MAILBOX, else FIFO)
  2. Two spheres instead of one (same mesh/vertex buffer, two draw calls with
     different model-space X offset + phase-shifted lighting)
  3. Higher mesh resolution (30x30 -> 64x64 lat/long subdivisions)
  4. HUD (window title) extended with live RAM (VmRSS) and CPU%% usage,
     read from /proc/self/status and /proc/self/stat (Linux-only, no extra deps)

Usage:
    python3 patch_sphere.py panvk_sphere_real.c panvk_sphere_real_v2.c

Each substitution is matched against an exact, unique substring of the
original file. If mesa's panvk_sphere_real.c source has since changed and a
substring no longer matches, the script stops and reports exactly which step
failed, rather than silently producing a broken file.
"""

import sys


def apply(src: str, old: str, new: str, label: str) -> str:
    count = src.count(old)
    if count != 1:
        print(f"[FAIL] step '{label}': expected exactly 1 match, found {count}.")
        print("       The source file may differ from what this patch expects.")
        sys.exit(1)
    print(f"[ok]   {label}")
    return src.replace(old, new, 1)


def main():
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} <input.c> <output.c>")
        sys.exit(1)

    in_path, out_path = sys.argv[1], sys.argv[2]
    with open(in_path, "r") as f:
        src = f.read()

    # ---- 1. (no-op: source already includes <unistd.h> right after <time.h>,
    #    which is all sysconf()/_SC_CLK_TCK for the CPU%% calc needs) ----

    # ---- 2. higher mesh resolution ----
    src = apply(
        src,
        "generate_sphere(0.8f, 30, 30);",
        "generate_sphere(0.8f, 64, 64);",
        "bump sphere tessellation 30x30 -> 64x64",
    )

    # ---- 3. uncapped present mode ----
    # NOTE: the actual source already queries present modes into `pms`/`pmCount`
    # a few lines above and picks MAILBOX over FIFO into a `presentMode` local.
    # We extend that same block to also prefer IMMEDIATE (truly uncapped) and
    # print which mode was chosen, rather than re-querying from scratch.
    src = apply(
        src,
        "    VkPresentModeKHR presentMode = VK_PRESENT_MODE_FIFO_KHR;\n"
        "    if (pms) {\n"
        "        for (uint32_t i = 0; i < pmCount; i++)\n"
        "            if (pms[i] == VK_PRESENT_MODE_MAILBOX_KHR) presentMode = VK_PRESENT_MODE_MAILBOX_KHR;\n"
        "        free(pms);\n"
        "    }\n",
        "    VkPresentModeKHR presentMode = VK_PRESENT_MODE_FIFO_KHR;\n"
        "    if (pms) {\n"
        "        int haveImmediate = 0, haveMailbox = 0;\n"
        "        for (uint32_t i = 0; i < pmCount; i++) {\n"
        "            if (pms[i] == VK_PRESENT_MODE_IMMEDIATE_KHR) haveImmediate = 1;\n"
        "            if (pms[i] == VK_PRESENT_MODE_MAILBOX_KHR) haveMailbox = 1;\n"
        "        }\n"
        "        if (haveImmediate) presentMode = VK_PRESENT_MODE_IMMEDIATE_KHR;\n"
        "        else if (haveMailbox) presentMode = VK_PRESENT_MODE_MAILBOX_KHR;\n"
        "        free(pms);\n"
        "    }\n"
        "    printf(\"Present mode: %s\\n\",\n"
        "           presentMode == VK_PRESENT_MODE_IMMEDIATE_KHR ? \"IMMEDIATE (uncapped)\" :\n"
        "           presentMode == VK_PRESENT_MODE_MAILBOX_KHR ? \"MAILBOX (uncapped)\" :\n"
        "           \"FIFO (vsync-capped)\");\n",
        "uncap present mode (IMMEDIATE/MAILBOX/FIFO)",
    )

    # ---- 4. add RAM/CPU sampling helpers, right after now_seconds() ----
    src = apply(
        src,
        "static double now_seconds(void) {\n"
        "    struct timespec ts;\n"
        "    clock_gettime(CLOCK_MONOTONIC, &ts);\n"
        "    return (double)ts.tv_sec + (double)ts.tv_nsec / 1e9;\n"
        "}\n",
        "static double now_seconds(void) {\n"
        "    struct timespec ts;\n"
        "    clock_gettime(CLOCK_MONOTONIC, &ts);\n"
        "    return (double)ts.tv_sec + (double)ts.tv_nsec / 1e9;\n"
        "}\n"
        "\n"
        "/* ---------------- lightweight self resource stats (Linux /proc) ---------------- */\n"
        "\n"
        "static long get_ram_kb(void) {\n"
        "    FILE *f = fopen(\"/proc/self/status\", \"r\");\n"
        "    if (!f) return -1;\n"
        "    char line[256];\n"
        "    long kb = -1;\n"
        "    while (fgets(line, sizeof(line), f)) {\n"
        "        if (strncmp(line, \"VmRSS:\", 6) == 0) {\n"
        "            sscanf(line + 6, \"%ld\", &kb);\n"
        "            break;\n"
        "        }\n"
        "    }\n"
        "    fclose(f);\n"
        "    return kb;\n"
        "}\n"
        "\n"
        "/* percentage of one core, averaged since the previous call */\n"
        "static double get_cpu_percent(void) {\n"
        "    static unsigned long long lastTotal = 0;\n"
        "    static double lastWall = 0.0;\n"
        "\n"
        "    FILE *f = fopen(\"/proc/self/stat\", \"r\");\n"
        "    if (!f) return -1.0;\n"
        "    char buf[512];\n"
        "    if (!fgets(buf, sizeof(buf), f)) { fclose(f); return -1.0; }\n"
        "    fclose(f);\n"
        "\n"
        "    /* comm field (arg 2) is in parens and may itself contain spaces/parens,\n"
        "     * so skip past the LAST ')' before tokenizing the fixed-format fields. */\n"
        "    char *p = strrchr(buf, ')');\n"
        "    if (!p) return -1.0;\n"
        "    p += 2; /* skip \") \" -> now at field 3 (state) */\n"
        "\n"
        "    unsigned long long utime = 0, stime = 0;\n"
        "    int fieldNum = 3;\n"
        "    char *tok = strtok(p, \" \");\n"
        "    while (tok) {\n"
        "        if (fieldNum == 14) utime = strtoull(tok, NULL, 10);\n"
        "        if (fieldNum == 15) { stime = strtoull(tok, NULL, 10); break; }\n"
        "        tok = strtok(NULL, \" \");\n"
        "        fieldNum++;\n"
        "    }\n"
        "\n"
        "    unsigned long long total = utime + stime;\n"
        "    double wall = now_seconds();\n"
        "    long clkTck = sysconf(_SC_CLK_TCK);\n"
        "\n"
        "    double pct = -1.0;\n"
        "    if (lastWall > 0.0 && clkTck > 0) {\n"
        "        double dCpu = (double)(total - lastTotal) / (double)clkTck;\n"
        "        double dWall = wall - lastWall;\n"
        "        if (dWall > 0.0) pct = 100.0 * dCpu / dWall;\n"
        "    }\n"
        "    lastTotal = total;\n"
        "    lastWall = wall;\n"
        "    return pct;\n"
        "}\n",
        "add get_ram_kb()/get_cpu_percent() helpers",
    )

    # ---- 5. two draw calls instead of one, offset in model space ----
    src = apply(
        src,
        '        PushConstants pc;\n        memcpy(pc.mvp, mvp, sizeof(mvp));\n        pc.time = colorShift;\n\n        vkResetCommandBuffer(commandBuffer, 0);\n        VkCommandBufferBeginInfo cbbi = { .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO };\n        vkBeginCommandBuffer(commandBuffer, &cbbi);\n\n        VkClearValue clears[2];\n        clears[0].color = (VkClearColorValue){{ 0.05f, 0.08f, 0.12f, 1.0f }};\n        clears[1].depthStencil = (VkClearDepthStencilValue){ 1.0f, 0 };\n\n        VkRenderPassBeginInfo rpbi = { .sType = VK_STRUCTURE_TYPE_RENDER_PASS_BEGIN_INFO };\n        rpbi.renderPass = renderPass;\n        rpbi.framebuffer = framebuffers[imageIndex];\n        rpbi.renderArea.offset = (VkOffset2D){ 0, 0 };\n        rpbi.renderArea.extent = extent;\n        rpbi.clearValueCount = 2;\n        rpbi.pClearValues = clears;\n\n        vkCmdBeginRenderPass(commandBuffer, &rpbi, VK_SUBPASS_CONTENTS_INLINE);\n        vkCmdBindPipeline(commandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS, pipeline);\n        VkDeviceSize offsets[1] = { 0 };\n        vkCmdBindVertexBuffers(commandBuffer, 0, 1, &vertexBuffer, offsets);\n        vkCmdPushConstants(commandBuffer, pipelineLayout, VK_SHADER_STAGE_VERTEX_BIT, 0, sizeof(pc), &pc);\n        vkCmdDraw(commandBuffer, g_vertexCount, 1, 0, 0);\n\n        if (hudCount > 0) {\n',
        '        vkResetCommandBuffer(commandBuffer, 0);\n        VkCommandBufferBeginInfo cbbi = { .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO };\n        vkBeginCommandBuffer(commandBuffer, &cbbi);\n\n        VkClearValue clears[2];\n        clears[0].color = (VkClearColorValue){{ 0.05f, 0.08f, 0.12f, 1.0f }};\n        clears[1].depthStencil = (VkClearDepthStencilValue){ 1.0f, 0 };\n\n        VkRenderPassBeginInfo rpbi = { .sType = VK_STRUCTURE_TYPE_RENDER_PASS_BEGIN_INFO };\n        rpbi.renderPass = renderPass;\n        rpbi.framebuffer = framebuffers[imageIndex];\n        rpbi.renderArea.offset = (VkOffset2D){ 0, 0 };\n        rpbi.renderArea.extent = extent;\n        rpbi.clearValueCount = 2;\n        rpbi.pClearValues = clears;\n\n        vkCmdBeginRenderPass(commandBuffer, &rpbi, VK_SUBPASS_CONTENTS_INLINE);\n        vkCmdBindPipeline(commandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS, pipeline);\n        VkDeviceSize offsets[1] = { 0 };\n        vkCmdBindVertexBuffers(commandBuffer, 0, 1, &vertexBuffer, offsets);\n\n        /* two spheres: same mesh/vertex buffer, two draws with different\n         * model-space X offsets and a phase-shifted light for visual contrast */\n        static const float sphereOffsetX[2] = { -1.1f, 1.1f };\n        for (int sIdx = 0; sIdx < 2; sIdx++) {\n            float tOff[16], modelOff[16], mvpOff[16];\n            mat4_translate(tOff, sphereOffsetX[sIdx], 0.0f, 0.0f);\n            mat4_mul(modelOff, tOff, model);\n            mat4_mul(mvpOff, vp, modelOff);\n\n            PushConstants pc;\n            memcpy(pc.mvp, mvpOff, sizeof(mvpOff));\n            pc.time = colorShift + (float)sIdx * 3.14159f;\n\n            vkCmdPushConstants(commandBuffer, pipelineLayout, VK_SHADER_STAGE_VERTEX_BIT, 0, sizeof(pc), &pc);\n            vkCmdDraw(commandBuffer, g_vertexCount, 1, 0, 0);\n        }\n\n        if (hudCount > 0) {\n',
        "replace single draw with two offset draws (dual sphere)",
    )

    # ---- 6. HUD: add RAM + CPU%% to the title string and on-screen HUD line ----
    src = apply(
        src,
        '            char title[512], l1[160], l2[160];\n            snprintf(title, sizeof(title),\n                     "%s | FPS %.1f | %.2fms | GPU %d%% | %ux%u",\n                     gpuLine, fps, frameMs, gpuLoad, extent.width, extent.height);\n            set_window_title(title);\n            printf("%s%s\\n", title, gpuLoadSysfs >= 0 ? " (sysfs)" : " (est)");\n\n            snprintf(l1, sizeof(l1), "%s", gpuLine);\n            if (gpuLoadSysfs >= 0)\n                snprintf(l2, sizeof(l2), "FPS %.1f  FRAME %.2fMS  GPU %d%%  %uX%u",\n                         fps, frameMs, gpuLoad, extent.width, extent.height);\n            else\n                snprintf(l2, sizeof(l2), "FPS %.1f  FRAME %.2fMS  GPU ~%d%% EST  %uX%u",\n                         fps, frameMs, gpuLoad, extent.width, extent.height);\n',
        '            long ramKb = get_ram_kb();\n            double cpuPct = get_cpu_percent();\n\n            char title[512], l1[160], l2[200];\n            snprintf(title, sizeof(title),\n                     "%s | FPS %.1f | %.2fms | GPU %d%% | %ux%u | RAM %.1fMB | CPU %.1f%%",\n                     gpuLine, fps, frameMs, gpuLoad, extent.width, extent.height,\n                     ramKb >= 0 ? ramKb / 1024.0 : -1.0, cpuPct >= 0 ? cpuPct : -1.0);\n            set_window_title(title);\n            printf("%s%s\\n", title, gpuLoadSysfs >= 0 ? " (sysfs)" : " (est)");\n\n            snprintf(l1, sizeof(l1), "%s", gpuLine);\n            if (gpuLoadSysfs >= 0)\n                snprintf(l2, sizeof(l2), "FPS %.1f  FRAME %.2fMS  GPU %d%%  %uX%u  RAM %.1fMB  CPU %.1f%%",\n                         fps, frameMs, gpuLoad, extent.width, extent.height,\n                         ramKb >= 0 ? ramKb / 1024.0 : -1.0, cpuPct >= 0 ? cpuPct : -1.0);\n            else\n                snprintf(l2, sizeof(l2), "FPS %.1f  FRAME %.2fMS  GPU ~%d%% EST  %uX%u  RAM %.1fMB  CPU %.1f%%",\n                         fps, frameMs, gpuLoad, extent.width, extent.height,\n                         ramKb >= 0 ? ramKb / 1024.0 : -1.0, cpuPct >= 0 ? cpuPct : -1.0);\n',
        "extend HUD title + on-screen line with RAM + CPU%%",
    )

    with open(out_path, "w") as f:
        f.write(src)
    print(f"\nWrote {out_path} ({len(src)} bytes). All 6 patch steps applied cleanly.")


if __name__ == "__main__":
    main()
