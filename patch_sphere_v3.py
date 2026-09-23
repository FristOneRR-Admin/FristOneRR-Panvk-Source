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
    with open("panvk_sphere_real_v2.c", "r") as f:
        src = f.read()

    src = apply(src,
        "static void hud_emit_quad(Vertex *v, uint32_t *n, float x0, float y0, float x1, float y1,\n"
        "                          float r, float g, float b) {\n"
        "    if (*n + 6 > HUD_MAX_VERTS) return;\n"
        "    float pts[6][2] = {{x0,y0},{x1,y0},{x1,y1},{x0,y0},{x1,y1},{x0,y1}};\n"
        "    for (int i = 0; i < 6; i++) {\n"
        "        v[*n].pos[0] = pts[i][0];\n"
        "        v[*n].pos[1] = pts[i][1];\n"
        "        v[*n].pos[2] = 0.0f;\n"
        "        v[*n].normal[0] = r;\n",
        "static void hud_emit_quad(Vertex *v, uint32_t *n, float x0, float y0, float x1, float y1,\n"
        "                          float r, float g, float b) {\n"
        "    if (*n + 6 > HUD_MAX_VERTS) return;\n"
        "    float pts[6][2] = {{x0,y0},{x1,y0},{x1,y1},{x0,y0},{x1,y1},{x0,y1}};\n"
        "    for (int i = 0; i < 6; i++) {\n"
        "        v[*n].pos[0] = pts[i][0];\n"
        "        v[*n].pos[1] = -pts[i][1];\n"
        "        v[*n].pos[2] = 0.0f;\n"
        "        v[*n].normal[0] = r;\n",
        "fix upside-down HUD (flip Y at vertex emission)")

    src = apply(src,
        "        mat4_translate(view, 0.0f, 0.0f, -2.5f);\n",
        "        mat4_translate(view, 0.0f, 0.0f, -5.0f);\n",
        "move camera back to frame the 10-sphere ring")

    src = apply(src,
        "    generate_sphere(0.8f, 64, 64);\n",
        "    generate_sphere(0.5f, 64, 64);\n",
        "shrink sphere radius 0.8 -> 0.5 for a 10-ball ring")

    src = apply(src,
        "        /* two spheres: same mesh/vertex buffer, two draws with different\n"
        "         * model-space X offsets and a phase-shifted light for visual contrast */\n"
        "        static const float sphereOffsetX[2] = { -1.1f, 1.1f };\n"
        "        for (int sIdx = 0; sIdx < 2; sIdx++) {\n"
        "            float tOff[16], modelOff[16], mvpOff[16];\n"
        "            mat4_translate(tOff, sphereOffsetX[sIdx], 0.0f, 0.0f);\n"
        "            mat4_mul(modelOff, tOff, model);\n"
        "            mat4_mul(mvpOff, vp, modelOff);\n"
        "\n"
        "            PushConstants pc;\n"
        "            memcpy(pc.mvp, mvpOff, sizeof(mvpOff));\n"
        "            pc.time = colorShift + (float)sIdx * 3.14159f;\n"
        "\n"
        "            vkCmdPushConstants(commandBuffer, pipelineLayout, VK_SHADER_STAGE_VERTEX_BIT, 0, sizeof(pc), &pc);\n"
        "            vkCmdDraw(commandBuffer, g_vertexCount, 1, 0, 0);\n"
        "        }\n"
        "\n",
        "        const int   numSpheres = 10;\n"
        "        const float ringRadius = 1.5f;\n"
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
        "replace 2 spheres-in-a-line with 10 spheres in a ring")

    with open("panvk_sphere_real_v3.c", "w") as f:
        f.write(src)
    print(f"\nWrote panvk_sphere_real_v3.c ({len(src)} bytes). All 4 steps applied.")

if __name__ == "__main__":
    main()
