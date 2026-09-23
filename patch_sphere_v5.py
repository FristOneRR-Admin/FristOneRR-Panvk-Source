#!/usr/bin/env python3
from pathlib import Path

src = Path("panvk_sphere_real_v4.c").read_text()

# 1) 200 spheres
src = src.replace(
    "const int   numCols = 10;\n"
    "        const int   numRows = 5;\n",
    "const int   numCols = 20;\n"
    "        const int   numRows = 10;\n",
    1
)

# 2) Keep 200 balls comfortably inside the screen
src = src.replace(
    "const float gridSpacing = 0.40f;",
    "const float gridSpacing = 0.18f;",
    1
)

# 3) Camera farther back for 20x10 grid
src = src.replace(
    "mat4_translate(view, 0.0f, 0.0f, -3.0f);",
    "mat4_translate(view, 0.0f, 0.0f, -2.15f);",
    1
)

# 4) Larger HUD characters
src = src.replace(
    "float cw = 0.020f;\n"
    "    float ch = 0.040f;",
    "float cw = 0.016f;\n"
    "    float ch = 0.032f;",
    1
)

Path("panvk_sphere_real_v5.c").write_text(src)

print("[OK] spheres : 200 (20 x 10)")
print("[OK] spacing : 0.18")
print("[OK] camera  : -2.15")
print("[OK] HUD     : adjusted for more information")
print("[OK] output  : panvk_sphere_real_v5.c")
