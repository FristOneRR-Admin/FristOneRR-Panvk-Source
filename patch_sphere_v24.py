#!/usr/bin/env python3
import sys

def apply(src, old, new, label):
    count = src.count(old)
    if count != 1:
        print(f"[FAIL] step '{label}': expected exactly 1 match, found {count}.")
        sys.exit(1)
    print(f"[ok]   {label}")
    return src.replace(old, new, 1)

def main():
    with open("panvk_sphere_real_v3.c", "r") as f:
        src = f.read()

    src = apply(src,
        "    float x = -0.97f;\n"
        "    float y = 0.97f;\n"
        "    float cw = 0.028f;\n"
        "    float ch = 0.055f;\n",
        "    float x = -0.97f;\n"
        "    float y = 0.97f;\n"
        "    float cw = 0.020f;\n"
        "    float ch = 0.040f;\n",
        "shrink HUD font so FPS/GPU/RAM/CPU line fits without clipping")

    src = apply(src,
        "        mat4_translate(view, 0.0f, 0.0f, -5.0f);\n",
        "        mat4_translate(view, 0.0f, 0.0f, -3.0f);\n",
        "adjust camera distance to frame the 50-ball grid")

    src = apply(src,
        "    generate_sphere(0.5f, 64, 64);\n",
        "    generate_sphere(0.15f, 64, 64);\n",
        "shrink sphere radius 0.5 -> 0.15 for a 50-ball grid")

    src = apply(src,
        "        /* ten spheres arranged in a ring facing the camera, same mesh/vertex\n"
        "         * buffer, one draw each with a different translate + color phase. */\n"
        "        const int   numSpheres = 10;\n"
        "        const float ringRadius = 1.5f;   /* tweak to spread the ring in/out */\n"
        "        for (int sIdx = 0; sIdx < numSpheres; sIdx++) {\n"
        "            float ringAngle = (2.0f * (float)M_PI * (float)sIdx) / (float)numSpheres;\n"
        "            float offX = ringRadius * cosf(ringAngle);\n"
        "            float offY = ringRadius * sinf(ringAngle);\n"
        "\n"
        "            float tOff[16], modelOff[16], mvpOff[16];\n"
        "            mat4_translate(tOff, offX, offY, 0.0f);\n"
        "            mat4_mul(modelOff, tOff, model);\n"
        "            mat4_mul(mvpOff, vp, modelOff);\n"
        "\n"
        "            PushConstants pc;\n"
        "            memcpy(pc.mvp, mvpOff, sizeof(mvpOff));\n"
        "            pc.time = colorShift + (float)sIdx * (2.0f * (float)M_PI / (float)numSpheres);\n"
        "\n"
        "            vkCmdPushConstants(commandBuffer, pipelineLayout, VK_SHADER_STAGE_VERTEX_BIT, 0, sizeof(pc), &pc);\n"
        "            vkCmdDraw(commandBuffer, g_vertexCount, 1, 0, 0);\n"
        "        }\n"
        "\n",
        "        const int   numCols  = 10;\n"
        "        const int   numRows  = 5;\n"
        "        const int   numSpheres = numCols * numRows;\n"
        "        const float gridSpacing = 0.4f;\n"
        "        for (int sIdx = 0; sIdx < numSpheres; sIdx++) {\n"
        "            int row = sIdx / numCols;\n"
        "            int col = sIdx % numCols;\n"
        "            float offX = (col - (numCols - 1) / 2.0f) * gridSpacing;\n"
        "            float offY = ((numRows - 1) / 2.0f - row) * gridSpacing;\n"
        "\n"
        "            float tOff[16], modelOff[16], mvpOff[16];\n"
        "            mat4_translate(tOff, offX, offY, 0.0f);\n"
        "            mat4_mul(modelOff, tOff, model);\n"
        "            mat4_mul(mvpOff, vp, modelOff);\n"
        "\n"
        "            PushConstants pc;\n"
        "            memcpy(pc.mvp, mvpOff, sizeof(mvpOff));\n"
        "            pc.time = colorShift + (float)sIdx * (2.0f * (float)M_PI / (float)numSpheres);\n"
        "\n"
        "            vkCmdPushConstants(commandBuffer, pipelineLayout, VK_SHADER_STAGE_VERTEX_BIT, 0, sizeof(pc), &pc);\n"
        "            vkCmdDraw(commandBuffer, g_vertexCount, 1, 0, 0);\n"
        "        }\n"
        "\n",
        "replace 10-ball ring with 50-ball top-to-bottom grid")

    with open("panvk_sphere_real_v4.c", "w") as f:
        f.write(src)
    print(f"\nWrote panvk_sphere_real_v4.c ({len(src)} bytes). All 4 steps applied.")

if __name__ == "__main__":
    main()
