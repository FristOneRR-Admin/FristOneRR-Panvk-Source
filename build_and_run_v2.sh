#!/data/data/com.termux/files/usr/bin/bash
# Builds and runs the patched dual-sphere + RAM/CPU HUD test.
# Run this from ~/mesa (or wherever panvk_sphere_real.c / patch_sphere.py live).
set -e
cd "$(dirname "$0")"

if ! command -v glslangValidator >/dev/null 2>&1; then
    echo "glslangValidator not found. Run: pkg install glslang"
    exit 1
fi

echo "== 1. Patching source =="
python3 patch_sphere.py panvk_sphere_real.c panvk_sphere_real_v2.c

echo
echo "== 2. Compiling shaders (unchanged, same push-constant layout) =="
glslangValidator -V sphere.vert -o sphere.vert.spv
glslangValidator -V sphere.frag -o sphere.frag.spv

echo
echo "== 3. Compiling patched binary =="
gcc -O2 -o panvk_sphere_real_v2 panvk_sphere_real_v2.c \
    $(pkg-config --cflags --libs xcb) -lvulkan -lm

echo
echo "Build OK: ./panvk_sphere_real_v2"
echo
echo "Run with:"
echo "  export DISPLAY=:0"
echo "  export PAN_I_WANT_A_BROKEN_VULKAN_DRIVER=1"
echo "  export VK_ICD_FILENAMES=\$HOME/mesa/panfrost_final_icd.json"
echo "  export LD_LIBRARY_PATH=/system/lib64:\$HOME/android-libs:\$LD_LIBRARY_PATH"
echo "  ./panvk_sphere_real_v2"
