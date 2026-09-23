#!/usr/bin/env python3
import sys
from pathlib import Path

SRC = Path("panvk_sphere_real_v3.c")
DST = Path("panvk_sphere_real_v4.c")

def fail(msg):
    print(f"[FAIL] {msg}")
    sys.exit(1)

def replace_once(src, old, new, label):
    count = src.count(old)

    if count == 0:
        print(f"[FAIL] {label}: pattern not found")
        return src, False

    if count != 1:
        print(f"[FAIL] {label}: expected 1 match, found {count}")
        return src, False

    print(f"[OK]   {label}")
    return src.replace(old, new, 1), True


def main():
    if not SRC.exists():
        fail(f"ไม่พบไฟล์ {SRC}")

    src = SRC.read_text()

    print(f"[INFO] input : {SRC}")
    print(f"[INFO] size  : {len(src)} bytes")
    print()

    # ------------------------------------------------------------
    # 1. HUD font
    # ------------------------------------------------------------
    old = """    float x = -0.97f;
    float y = 0.97f;
    float cw = 0.028f;
    float ch = 0.055f;
"""

    new = """    float x = -0.97f;
    float y = 0.97f;
    float cw = 0.020f;
    float ch = 0.040f;
"""

    src, ok = replace_once(
        src, old, new,
        "shrink HUD font"
    )
    if not ok:
        fail("ไม่สามารถ patch HUD font ได้")

    # ------------------------------------------------------------
    # 2. Camera distance
    # ------------------------------------------------------------
    old = "        mat4_translate(view, 0.0f, 0.0f, -5.0f);\n"
    new = "        mat4_translate(view, 0.0f, 0.0f, -3.0f);\n"

    src, ok = replace_once(
        src, old, new,
        "camera distance -5 -> -3"
    )
    if not ok:
        fail("ไม่สามารถ patch camera distance ได้")

    # ------------------------------------------------------------
    # 3. Sphere radius
    # ------------------------------------------------------------
    old = "    generate_sphere(0.5f, 64, 64);\n"
    new = "    generate_sphere(0.15f, 64, 64);\n"

    src, ok = replace_once(
        src, old, new,
        "sphere radius 0.5 -> 0.15"
    )
    if not ok:
        fail("ไม่สามารถ patch sphere radius ได้")

    # ------------------------------------------------------------
    # 4. Replace ring with 10 x 5 grid
    # ------------------------------------------------------------
    old = """        /* ten spheres arranged in a ring facing the camera, same mesh/vertex
         * buffer, one draw each with a different translate + color phase. */
        const int   numSpheres = 10;
        const float ringRadius = 1.5f;   /* tweak to spread the ring in/out */
        for (int sIdx = 0; sIdx < numSpheres; sIdx++) {
            float ringAngle = (2.0f * (float)M_PI * (float)sIdx) / (float)numSpheres;
            float offX = ringRadius * cosf(ringAngle);
            float offY = ringRadius * sinf(ringAngle);

            float tOff[16], modelOff[16], mvpOff[16];
            mat4_translate(tOff, offX, offY, 0.0f);
            mat4_mul(modelOff, tOff, model);
            mat4_mul(mvpOff, vp, modelOff);

            PushConstants pc;
            memcpy(pc.mvp, mvpOff, sizeof(mvpOff));
            pc.time = colorShift + (float)sIdx * (2.0f * (float)M_PI / (float)numSpheres);

            vkCmdPushConstants(commandBuffer, pipelineLayout, VK_SHADER_STAGE_VERTEX_BIT, 0, sizeof(pc), &pc);
            vkCmdDraw(commandBuffer, g_vertexCount, 1, 0, 0);
        }

"""

    new = """        /* 50 spheres arranged as a 10 x 5 grid. */
        const int   numCols = 10;
        const int   numRows = 5;
        const int   numSpheres = numCols * numRows;
        const float gridSpacing = 0.40f;

        for (int sIdx = 0; sIdx < numSpheres; sIdx++) {
            int row = sIdx / numCols;
            int col = sIdx % numCols;

            float offX =
                ((float)col - (float)(numCols - 1) * 0.5f)
                * gridSpacing;

            float offY =
                ((float)(numRows - 1) * 0.5f - (float)row)
                * gridSpacing;

            float tOff[16];
            float modelOff[16];
            float mvpOff[16];

            mat4_translate(tOff, offX, offY, 0.0f);
            mat4_mul(modelOff, tOff, model);
            mat4_mul(mvpOff, vp, modelOff);

            PushConstants pc;
            memcpy(pc.mvp, mvpOff, sizeof(mvpOff));

            pc.time =
                colorShift +
                (float)sIdx *
                (2.0f * (float)M_PI / (float)numSpheres);

            vkCmdPushConstants(
                commandBuffer,
                pipelineLayout,
                VK_SHADER_STAGE_VERTEX_BIT,
                0,
                sizeof(pc),
                &pc
            );

            vkCmdDraw(
                commandBuffer,
                g_vertexCount,
                1,
                0,
                0
            );
        }

"""

    src, ok = replace_once(
        src, old, new,
        "replace 10-ball ring with 50-ball grid"
    )

    if not ok:
        print()
        print("[INFO] ไม่พบ ring block เดิม")
        print("[INFO] กำลังค้นหา numSpheres ที่มีอยู่ใน source...")
        for i, line in enumerate(src.splitlines(), 1):
            if "numSpheres" in line or "ringRadius" in line:
                print(f"  {i}: {line}")

        fail("ไม่สามารถ patch grid ได้")

    # ------------------------------------------------------------
    # Write output
    # ------------------------------------------------------------
    DST.write_text(src)

    print()
    print("=" * 60)
    print("[SUCCESS] panvk_sphere_real_v4.c created")
    print(f"[INFO] output size: {len(src)} bytes")
    print("=" * 60)

    print()
    print("ตรวจสอบ:")
    print("  grep -n 'numCols\\|numRows\\|numSpheres\\|gridSpacing' panvk_sphere_real_v4.c")


if __name__ == "__main__":
    main()
