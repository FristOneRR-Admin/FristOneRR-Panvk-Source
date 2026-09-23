#!/usr/bin/env python3
import os, sys
from ctypes import *

os.environ["PAN_I_WANT_A_BROKEN_VULKAN_DRIVER"] = "1"

print("=== Vulkan Texture Test (Simple) ===")

# Load shaders
with open("vert_tex.spv", "rb") as f:
    VERT_SPV = f.read()
with open("frag_tex.spv", "rb") as f:
    FRAG_SPV = f.read()

print("Vertex shader:", len(VERT_SPV), "bytes")
print("Fragment shader:", len(FRAG_SPV), "bytes")

# Checkerboard texture
TEX_SIZE = 8
TEX_DATA = bytes([
    255,0,0,255, 0,0,255,255, 255,0,0,255, 0,0,255,255,
    255,0,0,255, 0,0,255,255, 255,0,0,255, 0,0,255,255,
    0,0,255,255, 255,0,0,255, 0,0,255,255, 255,0,0,255,
    0,0,255,255, 255,0,0,255, 0,0,255,255, 255,0,0,255,
    255,0,0,255, 0,0,255,255, 255,0,0,255, 0,0,255,255,
    255,0,0,255, 0,0,255,255, 255,0,0,255, 0,0,255,255,
    0,0,255,255, 255,0,0,255, 0,0,255,255, 255,0,0,255,
    0,0,255,255, 255,0,0,255, 0,0,255,255, 255,0,0,255,
] * 4)  # 8x8 * 4 = 256 bytes

print("Texture:", TEX_SIZE, "x", TEX_SIZE, "=", len(TEX_DATA), "bytes")

# Load libraries
vk = CDLL("libvulkan.so.1")
xcb = CDLL("libxcb.so.1")

print("Libraries loaded")
print("SUCCESS: Texture test setup complete!")
print("Note: Full texture rendering requires descriptor sets and samplers")
print("See Mesa source code for complete implementation examples")
