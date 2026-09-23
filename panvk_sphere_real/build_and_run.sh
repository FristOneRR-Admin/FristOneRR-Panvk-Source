#!/data/data/com.termux/files/usr/bin/bash
set -e
cd "$(dirname "$0")"

if ! command -v glslangValidator >/dev/null 2>&1; then
    echo "glslangValidator not found. Run: pkg install glslang"
    exit 1
fi

glslangValidator -V sphere.vert -o sphere.vert.spv
glslangValidator -V sphere.frag -o sphere.frag.spv

gcc -O2 -o panvk_sphere_real panvk_sphere_real.c \
    $(pkg-config --cflags --libs xcb) -lvulkan -lm

echo "Build OK."
echo
echo "  export DISPLAY=:0"
echo "  export VK_ICD_FILENAMES=\$HOME/mesa/icd/panvk_fixed.json"
echo "  export PAN_I_WANT_A_BROKEN_VULKAN_DRIVER=1"
echo "  ./panvk_sphere_real"
