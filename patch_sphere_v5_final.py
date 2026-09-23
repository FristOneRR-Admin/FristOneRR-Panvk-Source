#!/usr/bin/env python3
from pathlib import Path
import sys

src_path = Path("panvk_sphere_real_v4.c")
dst_path = Path("panvk_sphere_real_v5.c")

if not src_path.exists():
    print("[FAIL] panvk_sphere_real_v4.c not found")
    sys.exit(1)

s = src_path.read_text()

def replace_once(old, new, name):
    global s
    n = s.count(old)
    if n != 1:
        print(f"[FAIL] {name}: expected 1 match, found {n}")
        sys.exit(1)
    s = s.replace(old, new, 1)
    print(f"[OK] {name}")

# ------------------------------------------------------------
# 1. HUD font
# ------------------------------------------------------------
replace_once(
"""    float cw = 0.028f;
    float ch = 0.055f;
""",
"""    float cw = 0.018f;
    float ch = 0.036f;
""",
"HUD font resized"
)

# ------------------------------------------------------------
# 2. HUD background: slightly taller
# ------------------------------------------------------------
replace_once(
"""    hud_emit_quad(v, &n, -1.0f, 1.0f, 1.0f, 0.82f, 0.02f, 0.03f, 0.05f);
""",
"""    hud_emit_quad(v, &n, -1.0f, 1.0f, 1.0f, 0.78f,
                   0.02f, 0.03f, 0.05f);
""",
"HUD background enlarged"
)

# ------------------------------------------------------------
# 3. HUD second line position
# ------------------------------------------------------------
replace_once(
"""    x = -0.97f;
    y = 0.90f;
""",
"""    x = -0.97f;
    y = 0.91f;
""",
"HUD line spacing adjusted"
)

# ------------------------------------------------------------
# 4. 200 spheres
# ------------------------------------------------------------
replace_once(
"""        const int   numCols = 20;
        const int   numRows = 10;
        const int   numSpheres = numCols * numRows;
        const float gridSpacing = 0.18f;
""",
"""        const int   numCols = 20;
        const int   numRows = 10;
        const int   numSpheres = numCols * numRows;

        /*
         * 20 x 10 = 200 spheres.
         * Keep the grid centered around X=0 / Y=0.
         * The spacing is deliberately smaller than the sphere diameter
         * to make the graphics workload dense.
         */
        const float gridSpacing = 0.17f;
""",
"200-sphere grid configured"
)

# ------------------------------------------------------------
# 5. Camera
# ------------------------------------------------------------
replace_once(
"""        mat4_translate(view, 0.0f, 0.0f, -2.15f);
""",
"""        /*
         * Camera distance for the 20 x 10 grid.
         * Projection below already uses the real swapchain aspect ratio.
         */
        mat4_translate(view, 0.0f, 0.0f, -2.35f);
""",
"camera adjusted for 200 spheres"
)

# ------------------------------------------------------------
# 6. Initial HUD text
# ------------------------------------------------------------
replace_once(
"""            snprintf(l2, sizeof(l2), "FPS --.-  FRAME --.--MS  GPU --%%  1280X720");
""",
"""            snprintf(l2, sizeof(l2),
                       "FPS --.- FRAME --.--MS GPU --%% CPU --.-%% RAM ----MB");
""",
"HUD CPU/RAM placeholders added"
)

# ------------------------------------------------------------
# 7. Add CPU/RAM variables
# ------------------------------------------------------------
replace_once(
"""    int gpuLoad = -1;
    int gpuLoadSysfs = -1;
    uint32_t hudCount = 0;
""",
"""    int gpuLoad = -1;
    int gpuLoadSysfs = -1;

    double cpuLoad = -1.0;
    long ramKb = -1;

    uint32_t hudCount = 0;
""",
"CPU/RAM HUD variables added"
)

# ------------------------------------------------------------
# 8. Find the per-frame FPS update area.
# Insert CPU/RAM sampling immediately before command buffer reset.
# ------------------------------------------------------------
needle = """        vkResetCommandBuffer(commandBuffer, 0);
"""

if s.count(needle) != 1:
    print(f"[FAIL] render-loop insertion point: found {s.count(needle)}")
    sys.exit(1)

insert = """        /*
         * Per-frame lightweight resource statistics.
         *
         * CPU percentage is this test process' CPU usage, not total
         * system CPU usage. This keeps the metric meaningful for
         * measuring the graphics test itself.
         */
        cpuLoad = get_cpu_percent();
        ramKb = get_ram_kb();

        if (gpuLoadSysfs >= 0)
            gpuLoad = gpuLoadSysfs;

        {
            char l1[160];
            char l2[160];

            snprintf(
                l1, sizeof(l1),
                "%s",
                gpuLine
            );

            if (cpuLoad >= 0.0 && ramKb >= 0) {
                snprintf(
                    l2, sizeof(l2),
                    "FPS %5.1f FRAME %6.2fMS GPU %3d%% CPU %5.1f%% RAM %5.1fMB",
                    fps,
                    frameMs,
                    gpuLoad,
                    cpuLoad,
                    (double)ramKb / 1024.0
                );
            } else if (cpuLoad >= 0.0) {
                snprintf(
                    l2, sizeof(l2),
                    "FPS %5.1f FRAME %6.2fMS GPU %3d%% CPU %5.1f%% RAM ----MB",
                    fps,
                    frameMs,
                    gpuLoad,
                    cpuLoad
                );
            } else {
                snprintf(
                    l2, sizeof(l2),
                    "FPS %5.1f FRAME %6.2fMS GPU %3d%% CPU --.-%% RAM ----MB",
                    fps,
                    frameMs,
                    gpuLoad
                );
            }

            hudCount = build_hud(hudCpu, l1, l2);
            memcpy(
                hudMapped,
                hudCpu,
                sizeof(Vertex) * hudCount
            );
        }

"""

s = s.replace(needle, insert + needle, 1)
print("[OK] per-frame CPU/RAM HUD update added")

# ------------------------------------------------------------
# Write
# ------------------------------------------------------------
dst_path.write_text(s)

print()
print("=" * 64)
print("[SUCCESS] panvk_sphere_real_v5.c")
print("=" * 64)
print(f"size: {len(s)} bytes")
print()
print("200 spheres : 20 x 10")
print("spacing     : 0.17")
print("camera      : -2.35")
print("HUD         : FPS / FRAME / GPU / CPU / RAM")
print()
