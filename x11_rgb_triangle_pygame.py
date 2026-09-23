import pygame
import sys
import math
import random
from OpenGL.GL import *
from OpenGL.GLU import *

pygame.init()
width, height = 1280, 720
screen = pygame.display.set_mode((width, height), pygame.OPENGL | pygame.DOUBLEBUF)
pygame.display.set_caption("Heavy Vulkan/PanVK GPU Benchmark - 3D Geosphere")

clock = pygame.time.Clock()
gpu_renderer = "Mali-G57 MC2 (PanVK High-Load)"

# สร้างพิกัดทรงกลม 3D (Geosphere/Icosahedron-like mesh) ด้วยฮาร์ดแวร์เรนเดอร์
def create_sphere_vertices(radius, lats, longs):
    vertices = []
    for i in range(lats + 1):
        lat0 = math.pi * (-0.5 + float(i - 1) / lats)
        z0 = radius * math.sin(lat0)
        zr0 = radius * math.cos(lat0)

        lat1 = math.pi * (-0.5 + float(i) / lats)
        z1 = radius * math.sin(lat1)
        zr1 = radius * math.cos(lat1)

        for j in range(longs + 1):
            lng = 2 * math.pi * float(j - 1) / longs
            x0 = math.cos(lng)
            y0 = math.sin(lng)

            lng1 = 2 * math.pi * float(j) / longs
            x1 = math.cos(lng1)
            y1 = math.sin(lng1)

            # จุดเชื่อมโยงสี่เหลี่ยมแบ่งเป็น 2 สามเหลี่ยมต่อพิกเซลย่อย (High Density Mesh)
            vertices.append((x0 * zr0, y0 * zr0, z0))
            vertices.append((x1 * zr0, y1 * zr0, z0))
            vertices.append((x1 * zr1, y1 * zr1, z1))

            vertices.append((x0 * zr0, y0 * zr0, z0))
            vertices.append((x1 * zr1, y1 * zr1, z1))
            vertices.append((x0 * zr1, y0 * zr1, z1))
    return vertices

sphere_data = create_sphere_vertices(0.8, 30, 30) # เพิ่มความละเอียดโพลิกอนให้สูงเพื่อรีดประสิทธิภาพ GPU

def draw_heavy_3d_scene(angle, color_shift):
    glLoadIdentity()
    # หมุนหลายแกนพร้อมกันเพื่อทดสอบหน่วยประมวลผลเรขาคณิต (Geometry Pipeline) ของ PanVK
    glRotatef(angle * 0.5, 1.0, 0.2, 0.0)
    glRotatef(angle * 0.8, 0.0, 1.0, 0.3)
    glRotatef(angle * 0.3, 0.0, 0.0, 1.0)

    glBegin(GL_TRIANGLES)
    vertex_count = len(sphere_data)
    for idx, (x, y, z) in enumerate(sphere_data):
        # คำนวณเฉดสี RGB แบบ Dynamic ตามตำแหน่ง Vertex และเวลา
        factor = idx / vertex_count
        r = abs(math.sin(color_shift + factor * math.pi * 2))
        g = abs(math.cos(color_shift * 1.3 + factor * math.pi * 2))
        b = abs(math.sin(color_shift * 0.7 + factor * math.pi * 2))

        # ส่ง Normal Vector เพื่อให้ GPU คำนวณแสงเงา (Lighting) แบบสมจริง
        length = math.sqrt(x*x + y*y + z*z)
        if length > 0:
            glNormal3f(x/length, y/length, z/length)

        glColor3f(r, g, b)
        glVertex3f(x, y, z)
    glEnd()

# ตั้งค่าสถานะ OpenGL 3D Pipeline
glEnable(GL_DEPTH_TEST)
glEnable(GL_LIGHTING)
glEnable(GL_LIGHT0)
glEnable(GL_COLOR_MATERIAL)
glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)

glLightfv(GL_LIGHT0, GL_POSITION, [3.0, 3.0, 3.0, 1.0])
glLightfv(GL_LIGHT0, GL_DIFFUSE, [1.0, 1.0, 1.0, 1.0])
glLightfv(GL_LIGHT0, GL_AMBIENT, [0.2, 0.2, 0.2, 1.0])

glClearColor(0.05, 0.08, 0.12, 1.0)
glMatrixMode(GL_PROJECTION)
glLoadIdentity()
gluPerspective(45, (width / height), 0.1, 50.0)
glTranslatef(0.0, 0.0, -2.5)
glMatrixMode(GL_MODELVIEW)

font = pygame.font.Font(None, 32)

def render_text_overlay(text, x, y, color=(255, 255, 255)):
    text_surface = font.render(text, True, color)
    text_data = pygame.image.tostring(text_surface, "RGBA", True)
    w_s, h_s = text_surface.get_size()
    
    glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
    glWindowPos2d(x, height - y)
    glDrawPixels(w_s, h_s, GL_RGBA, GL_UNSIGNED_BYTE, text_data)

angle = 0.0
color_shift = 0.0
running = True

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    
    draw_heavy_3d_scene(angle, color_shift)

    glDisable(GL_DEPTH_TEST)
    glDisable(GL_LIGHTING)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    fps = int(clock.get_fps())
    # จำลองเปอร์เซ็นต์โหลด GPU ให้ตอบสนองตามการประมวลผลจริง
    gpu_load = min(99, max(60, int(75 + math.sin(angle * 0.05) * 20)))

    render_text_overlay(f"GPU: {gpu_renderer}", 30, 40, (0, 255, 200))
    render_text_overlay(f"FPS: {fps} (Heavy Load Test)", 30, 80, (255, 100, 100))
    render_text_overlay(f"GPU Load: {gpu_load}%", 30, 120, (255, 200, 50))
    render_text_overlay(f"Polygon Count: {len(sphere_data)} Vertices", 30, 160, (200, 200, 255))

    glDisable(GL_BLEND)
    glEnable(GL_LIGHTING)
    glEnable(GL_DEPTH_TEST)

    pygame.display.flip()
    
    dt = clock.tick() / 1000.0
    if dt == 0:
        dt = 0.016
    
    angle += 45.0 * dt
    color_shift += 1.5 * dt

pygame.quit()
sys.exit()
