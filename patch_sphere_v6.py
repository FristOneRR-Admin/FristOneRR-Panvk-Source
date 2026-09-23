from pathlib import Path
import re
import sys

src_path = Path("panvk_sphere_real_v5.c")
dst_path = Path("panvk_sphere_real_v6.c")

s = src_path.read_text()

def sub(pattern, repl, name, count=1):
    global s
    s2, n = re.subn(pattern, repl, s, count=count)
    if n != count:
        print(f"[FAIL] {name}: found {n}, expected {count}")
        sys.exit(1)
    s = s2
    print(f"[OK] {name}")

# ------------------------------------------------------------
# V6: 200 spheres / cleaner spacing
# ------------------------------------------------------------

sub(
    r'const\s+float\s+gridSpacing\s*=\s*[0-9.]+f\s*;',
    'const float gridSpacing = 0.205f;',
    'gridSpacing -> 0.205'
)

# ------------------------------------------------------------
# Sphere radius
# ------------------------------------------------------------

sub(
    r'generate_sphere\(\s*[0-9.]+f\s*,\s*64\s*,\s*64\s*\)',
    'generate_sphere(0.10f, 64, 64)',
    'sphere radius -> 0.10'
)

# ------------------------------------------------------------
# Camera
# ------------------------------------------------------------

sub(
    r'mat4_translate\(\s*view\s*,\s*0\.0f\s*,\s*0\.0f\s*,\s*-[0-9.]+f\s*\);',
    'mat4_translate(view, 0.0f, 0.0f, -2.90f);',
    'camera -> -2.90'
)

# ------------------------------------------------------------
# HUD font: larger and easier to read
# ------------------------------------------------------------

sub(
    r'float\s+cw\s*=\s*[0-9.]+f\s*;',
    'float cw = 0.024f;',
    'HUD cw -> 0.024'
)

sub(
    r'float\s+ch\s*=\s*[0-9.]+f\s*;',
    'float ch = 0.048f;',
    'HUD ch -> 0.048'
)

# ------------------------------------------------------------
# HUD bar
# ------------------------------------------------------------

sub(
    r'hud_emit_quad\(v,\s*&n,\s*-1\.0f,\s*1\.0f,\s*1\.0f,\s*[0-9.]+f,',
    'hud_emit_quad(v, &n, -1.0f, 1.0f, 1.0f, 0.78f,',
    'HUD bar'
)

# ------------------------------------------------------------
# HUD line positions
# ------------------------------------------------------------

sub(
    r'float\s+x\s*=\s*-0\.97f;\s*\n\s*float\s+y\s*=\s*0\.97f;',
    'float x = -0.97f;\n    float y = 0.965f;',
    'HUD line 1 position'
)

sub(
    r'x\s*=\s*-0\.97f;\s*\n\s*y\s*=\s*0\.90f;',
    'x = -0.97f;\n    y = 0.885f;',
    'HUD line 2 position'
)

# ------------------------------------------------------------
# Update initial placeholder to match V6 HUD
# ------------------------------------------------------------

sub(
    r'snprintf\(l2,\s*sizeof\(l2\),\s*"FPS --\.- FRAME --\.--MS GPU --%% CPU --\.-%% RAM ----MB"\);',
    'snprintf(l2, sizeof(l2), "FPS --.- FRAME --.--MS GPU --%% CPU --.-%% RAM ----MB");',
    'HUD placeholder'
)

dst_path.write_text(s)

print()
print("=" * 64)
print("[SUCCESS] panvk_sphere_real_v6.c")
print("=" * 64)
print(f"size: {len(s)} bytes")
print()
print("200 spheres : 20 x 10")
print("radius      : 0.10")
print("spacing     : 0.205")
print("camera      : -2.90")
print("HUD         : 0.024 x 0.048")
print("HUD         : FPS / FRAME / GPU / CPU / RAM")
