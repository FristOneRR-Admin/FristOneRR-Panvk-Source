/*
 * panvk_sphere_real.c — rotating geosphere through PanVK + XCB.
 *
 * Window is fixed 1280x720 and centered on the X screen.
 * On-screen HUD shows GPU name, FPS, frame time, and GPU load.
 * Shader files are loaded from the executable directory, not cwd.
 *
 * BUILD:
 *   glslangValidator -V sphere.vert -o sphere.vert.spv
 *   glslangValidator -V sphere.frag -o sphere.frag.spv
 *   gcc -O2 -o panvk_sphere_real panvk_sphere_real.c \
 *       $(pkg-config --cflags --libs xcb) -lvulkan -lm
 */

#define _GNU_SOURCE
#define VK_USE_PLATFORM_XCB_KHR
#include <vulkan/vulkan.h>
#include <xcb/xcb.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stddef.h>
#include <stdint.h>
#include <math.h>
#include <time.h>
#include <unistd.h>
#include <limits.h>
#include <errno.h>
#include <dirent.h>
#include <sys/stat.h>

#define WIDTH 1280
#define HEIGHT 720
#define HUD_MAX_VERTS 8192

#define VK_CHECK(x) do { \
    VkResult _err = (x); \
    if (_err != VK_SUCCESS) { \
        fprintf(stderr, "[vulkan error %d] %s:%d: %s\n", _err, __FILE__, __LINE__, #x); \
        exit(1); \
    } \
} while (0)

typedef struct {
    float pos[3];
    float normal[3];
    float factor;
} Vertex;

static Vertex   *g_vertices = NULL;
static uint32_t  g_vertexCount = 0;
static char      g_exedir[PATH_MAX];

static void exe_dir(char *out, size_t n) {
    char buf[PATH_MAX];
    ssize_t len = readlink("/proc/self/exe", buf, sizeof(buf) - 1);
    if (len <= 0) {
        if (!getcwd(out, n)) strncpy(out, ".", n);
        return;
    }
    buf[len] = 0;
    char *slash = strrchr(buf, '/');
    if (slash) *slash = 0;
    snprintf(out, n, "%s", buf);
}

static int open_shader_path(const char *name, char *out, size_t n) {
    const char *cands[4];
    char a[PATH_MAX], b[PATH_MAX], c[PATH_MAX];
    snprintf(a, sizeof(a), "%s/%s", g_exedir, name);
    snprintf(b, sizeof(b), "./%s", name);
    snprintf(c, sizeof(c), "%s/panvk_sphere_real/%s", getenv("HOME") ? getenv("HOME") : "", name);
    cands[0] = a; cands[1] = b; cands[2] = c; cands[3] = name;
    for (int i = 0; i < 4; i++) {
        struct stat st;
        if (stat(cands[i], &st) == 0 && st.st_size > 0) {
            snprintf(out, n, "%s", cands[i]);
            return 0;
        }
    }
    return -1;
}

static void generate_sphere(float radius, int lats, int longs) {
    uint32_t count = (uint32_t)(lats + 1) * (uint32_t)(longs + 1) * 6u;
    g_vertices = malloc(sizeof(Vertex) * count);
    uint32_t idx = 0;

    for (int i = 0; i <= lats; i++) {
        double lat0 = M_PI * (-0.5 + (double)(i - 1) / lats);
        double z0 = radius * sin(lat0), zr0 = radius * cos(lat0);
        double lat1 = M_PI * (-0.5 + (double)i / lats);
        double z1 = radius * sin(lat1), zr1 = radius * cos(lat1);

        for (int j = 0; j <= longs; j++) {
            double lng0 = 2.0 * M_PI * (double)(j - 1) / longs;
            double x0 = cos(lng0), y0 = sin(lng0);
            double lng1 = 2.0 * M_PI * (double)j / longs;
            double x1 = cos(lng1), y1 = sin(lng1);

            double pts[6][3] = {
                { x0 * zr0, y0 * zr0, z0 },
                { x1 * zr0, y1 * zr0, z0 },
                { x1 * zr1, y1 * zr1, z1 },
                { x0 * zr0, y0 * zr0, z0 },
                { x1 * zr1, y1 * zr1, z1 },
                { x0 * zr1, y0 * zr1, z1 },
            };

            for (int k = 0; k < 6; k++) {
                float px = (float)pts[k][0], py = (float)pts[k][1], pz = (float)pts[k][2];
                float len = sqrtf(px * px + py * py + pz * pz);
                if (len < 1e-6f) len = 1.0f;
                g_vertices[idx].pos[0] = px;
                g_vertices[idx].pos[1] = py;
                g_vertices[idx].pos[2] = pz;
                g_vertices[idx].normal[0] = px / len;
                g_vertices[idx].normal[1] = py / len;
                g_vertices[idx].normal[2] = pz / len;
                g_vertices[idx].factor = (float)idx / (float)count;
                idx++;
            }
        }
    }
    g_vertexCount = count;
}

static void mat4_identity(float m[16]) {
    memset(m, 0, sizeof(float) * 16);
    m[0] = m[5] = m[10] = m[15] = 1.0f;
}

static void mat4_mul(float r[16], const float a[16], const float b[16]) {
    float t[16];
    for (int c = 0; c < 4; c++)
        for (int row = 0; row < 4; row++) {
            float sum = 0.0f;
            for (int k = 0; k < 4; k++) sum += a[k * 4 + row] * b[c * 4 + k];
            t[c * 4 + row] = sum;
        }
    memcpy(r, t, sizeof(t));
}

static void mat4_translate(float m[16], float x, float y, float z) {
    mat4_identity(m);
    m[12] = x; m[13] = y; m[14] = z;
}

static void mat4_rotate(float m[16], float angle_deg, float x, float y, float z) {
    float len = sqrtf(x * x + y * y + z * z);
    if (len < 1e-8f) { mat4_identity(m); return; }
    x /= len; y /= len; z /= len;
    float rad = angle_deg * (float)M_PI / 180.0f;
    float c = cosf(rad), s = sinf(rad), t = 1.0f - c;
    mat4_identity(m);
    m[0]  = t * x * x + c;      m[1]  = t * x * y + s * z;  m[2]  = t * x * z - s * y;
    m[4]  = t * x * y - s * z;  m[5]  = t * y * y + c;      m[6]  = t * y * z + s * x;
    m[8]  = t * x * z + s * y;  m[9]  = t * y * z - s * x;  m[10] = t * z * z + c;
}

static void mat4_perspective_vk(float m[16], float fovy_rad, float aspect, float znear, float zfar) {
    float f = 1.0f / tanf(fovy_rad / 2.0f);
    memset(m, 0, sizeof(float) * 16);
    m[0]  = f / aspect;
    m[5]  = -f;
    m[10] = zfar / (znear - zfar);
    m[11] = -1.0f;
    m[14] = (zfar * znear) / (znear - zfar);
}

typedef struct {
    float mvp[16];
    float time;
} PushConstants;

/* 5x7 bitmap font, ASCII 32..90. Each row is a 5-bit mask in the low bits. */
static const uint8_t FONT5x7[59][7] = {
    {0,0,0,0,0,0,0}, /* space */
    {4,4,4,4,0,4,0}, /* ! */
    {10,10,0,0,0,0,0},
    {10,31,10,31,10,0,0},
    {4,14,20,14,5,14,4},
    {18,19,4,8,16,19,2},
    {8,20,8,21,18,13,0},
    {4,4,0,0,0,0,0},
    {2,4,4,4,4,4,2},
    {8,4,4,4,4,4,8},
    {0,10,4,31,4,10,0},
    {0,4,4,31,4,4,0},
    {0,0,0,0,4,4,8},
    {0,0,0,31,0,0,0},
    {0,0,0,0,0,4,0},
    {1,2,4,8,16,0,0},
    {14,17,19,21,25,17,14}, /* 0 */
    {4,12,4,4,4,4,14},
    {14,17,1,6,8,16,31},
    {14,17,1,6,1,17,14},
    {2,6,10,18,31,2,2},
    {31,16,30,1,1,17,14},
    {6,8,16,30,17,17,14},
    {31,1,2,4,8,8,8},
    {14,17,17,14,17,17,14},
    {14,17,17,15,1,2,12},
    {0,4,0,0,4,0,0},
    {0,4,0,0,4,4,8},
    {2,4,8,16,8,4,2},
    {0,0,31,0,31,0,0},
    {8,4,2,1,2,4,8},
    {14,17,1,2,4,0,4},
    {14,17,19,21,19,16,14},
    {14,17,17,31,17,17,17}, /* A */
    {30,17,17,30,17,17,30},
    {14,17,16,16,16,17,14},
    {30,17,17,17,17,17,30},
    {31,16,16,30,16,16,31},
    {31,16,16,30,16,16,16},
    {14,17,16,23,17,17,15},
    {17,17,17,31,17,17,17},
    {14,4,4,4,4,4,14},
    {1,1,1,1,1,17,14},
    {17,18,20,24,20,18,17},
    {16,16,16,16,16,16,31},
    {17,27,21,21,17,17,17},
    {17,25,21,19,17,17,17},
    {14,17,17,17,17,17,14},
    {30,17,17,30,16,16,16},
    {14,17,17,17,21,18,13},
    {30,17,17,30,20,18,17},
    {14,17,16,14,1,17,14},
    {31,4,4,4,4,4,4},
    {17,17,17,17,17,17,14},
    {17,17,17,17,17,10,4},
    {17,17,17,21,21,21,10},
    {17,17,10,4,10,17,17},
    {17,17,10,4,4,4,4},
    {31,1,2,4,8,16,31},
};

static int font_index(char ch) {
    if (ch >= 'a' && ch <= 'z') ch = (char)(ch - 'a' + 'A');
    if (ch < 32 || ch > 90) return 0;
    return ch - 32;
}

static xcb_connection_t       *connection;
static xcb_screen_t           *screen;
static xcb_window_t            window;
static xcb_intern_atom_reply_t *atom_wm_delete_window;

static void set_size_hints(int x, int y) {
    /* ICCCM WM_NORMAL_HINTS as 18 CARD32s */
    int32_t hints[18];
    memset(hints, 0, sizeof(hints));
    hints[0] = 4 | 8 | 16 | 32 | 256 | 512; /* PPosition|PSize|PMinSize|PMaxSize|PBaseSize|PWinGravity */
    hints[1] = x; hints[2] = y;
    hints[3] = WIDTH; hints[4] = HEIGHT;
    hints[5] = WIDTH; hints[6] = HEIGHT;
    hints[7] = WIDTH; hints[8] = HEIGHT;
    hints[13] = WIDTH; hints[14] = HEIGHT;
    hints[15] = 5; /* CenterGravity */
    xcb_change_property(connection, XCB_PROP_MODE_REPLACE, window,
                        XCB_ATOM_WM_NORMAL_HINTS, XCB_ATOM_WM_SIZE_HINTS, 32, 18, hints);
}

static void init_xcb_window(void) {
    connection = xcb_connect(NULL, NULL);
    if (xcb_connection_has_error(connection)) {
        fprintf(stderr, "xcb_connect failed (is DISPLAY set / is termux-x11 running?)\n");
        exit(1);
    }
    const xcb_setup_t *setup = xcb_get_setup(connection);
    xcb_screen_iterator_t iter = xcb_setup_roots_iterator(setup);
    screen = iter.data;

    int x = (int)screen->width_in_pixels > WIDTH ? ((int)screen->width_in_pixels - WIDTH) / 2 : 0;
    int y = (int)screen->height_in_pixels > HEIGHT ? ((int)screen->height_in_pixels - HEIGHT) / 2 : 0;

    window = xcb_generate_id(connection);
    uint32_t value_mask = XCB_CW_BACK_PIXEL | XCB_CW_EVENT_MASK;
    uint32_t value_list[2] = {
        screen->black_pixel,
        XCB_EVENT_MASK_KEY_PRESS | XCB_EVENT_MASK_STRUCTURE_NOTIFY
    };

    xcb_create_window(connection, XCB_COPY_FROM_PARENT, window, screen->root,
                       (int16_t)x, (int16_t)y, WIDTH, HEIGHT, 0,
                       XCB_WINDOW_CLASS_INPUT_OUTPUT, screen->root_visual,
                       value_mask, value_list);

    set_size_hints(x, y);

    xcb_intern_atom_cookie_t proto_cookie = xcb_intern_atom(connection, 1, 12, "WM_PROTOCOLS");
    xcb_intern_atom_reply_t *proto_reply = xcb_intern_atom_reply(connection, proto_cookie, 0);
    xcb_intern_atom_cookie_t del_cookie = xcb_intern_atom(connection, 0, 16, "WM_DELETE_WINDOW");
    atom_wm_delete_window = xcb_intern_atom_reply(connection, del_cookie, 0);
    if (proto_reply && atom_wm_delete_window)
        xcb_change_property(connection, XCB_PROP_MODE_REPLACE, window,
                             proto_reply->atom, 4, 32, 1, &atom_wm_delete_window->atom);
    free(proto_reply);

    const char *title = "PanVK 1280x720";
    xcb_change_property(connection, XCB_PROP_MODE_REPLACE, window,
                         XCB_ATOM_WM_NAME, XCB_ATOM_STRING, 8, strlen(title), title);

    xcb_map_window(connection, window);
    uint32_t cfg[3] = { (uint32_t)x, (uint32_t)y, 0 };
    xcb_configure_window(connection, window,
                         XCB_CONFIG_WINDOW_X | XCB_CONFIG_WINDOW_Y, cfg);
    uint32_t wh[2] = { WIDTH, HEIGHT };
    xcb_configure_window(connection, window,
                         XCB_CONFIG_WINDOW_WIDTH | XCB_CONFIG_WINDOW_HEIGHT, wh);
    xcb_flush(connection);
    printf("X11 window %dx%d at %d,%d on screen %dx%d\n",
           WIDTH, HEIGHT, x, y, screen->width_in_pixels, screen->height_in_pixels);
}

static void set_window_title(const char *title) {
    xcb_change_property(connection, XCB_PROP_MODE_REPLACE, window,
                         XCB_ATOM_WM_NAME, XCB_ATOM_STRING, 8, strlen(title), title);
    xcb_flush(connection);
}

static int poll_events(void) {
    xcb_generic_event_t *event;
    while ((event = xcb_poll_for_event(connection))) {
        uint8_t type = event->response_type & ~0x80;
        if (type == XCB_CLIENT_MESSAGE) {
            xcb_client_message_event_t *cm = (xcb_client_message_event_t *)event;
            if (atom_wm_delete_window && cm->data.data32[0] == atom_wm_delete_window->atom) {
                free(event); return 0;
            }
        } else if (type == XCB_KEY_PRESS) {
            xcb_key_press_event_t *kp = (xcb_key_press_event_t *)event;
            if (kp->detail == 9) { free(event); return 0; }
        }
        free(event);
    }
    return 1;
}

static uint32_t find_memory_type(VkPhysicalDeviceMemoryProperties memProps,
                                  uint32_t typeBits, VkMemoryPropertyFlags props) {
    for (uint32_t i = 0; i < memProps.memoryTypeCount; i++) {
        if ((typeBits & (1u << i)) &&
            (memProps.memoryTypes[i].propertyFlags & props) == props)
            return i;
    }
    fprintf(stderr, "No suitable memory type found\n");
    exit(1);
}

static char *read_file(const char *path, size_t *outSize) {
    FILE *f = fopen(path, "rb");
    if (!f) {
        fprintf(stderr, "Failed to open %s\n", path);
        exit(1);
    }
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    char *buf = malloc((size_t)sz);
    if (fread(buf, 1, (size_t)sz, f) != (size_t)sz) { fprintf(stderr, "short read on %s\n", path); exit(1); }
    fclose(f);
    *outSize = (size_t)sz;
    return buf;
}

static VkShaderModule create_shader_module(VkDevice device, const char *name) {
    char path[PATH_MAX];
    if (open_shader_path(name, path, sizeof(path)) != 0) {
        fprintf(stderr, "Cannot find %s next to the binary or in cwd\n", name);
        exit(1);
    }
    printf("Using shader %s\n", path);
    size_t sz;
    char *code = read_file(path, &sz);
    VkShaderModuleCreateInfo smci = { .sType = VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO };
    smci.codeSize = sz;
    smci.pCode = (const uint32_t *)code;
    VkShaderModule mod;
    VK_CHECK(vkCreateShaderModule(device, &smci, NULL, &mod));
    free(code);
    return mod;
}

static double now_seconds(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec / 1e9;
}

/* ---------------- lightweight self resource stats (Linux /proc) ---------------- */

static long get_ram_kb(void) {
    FILE *f = fopen("/proc/self/status", "r");
    if (!f) return -1;
    char line[256];
    long kb = -1;
    while (fgets(line, sizeof(line), f)) {
        if (strncmp(line, "VmRSS:", 6) == 0) {
            sscanf(line + 6, "%ld", &kb);
            break;
        }
    }
    fclose(f);
    return kb;
}

/* percentage of one core, averaged since the previous call */
static double get_cpu_percent(void) {
    static unsigned long long lastTotal = 0;
    static double lastWall = 0.0;

    FILE *f = fopen("/proc/self/stat", "r");
    if (!f) return -1.0;
    char buf[512];
    if (!fgets(buf, sizeof(buf), f)) { fclose(f); return -1.0; }
    fclose(f);

    /* comm field (arg 2) is in parens and may itself contain spaces/parens,
     * so skip past the LAST ')' before tokenizing the fixed-format fields. */
    char *p = strrchr(buf, ')');
    if (!p) return -1.0;
    p += 2; /* skip ") " -> now at field 3 (state) */

    unsigned long long utime = 0, stime = 0;
    int fieldNum = 3;
    char *tok = strtok(p, " ");
    while (tok) {
        if (fieldNum == 14) utime = strtoull(tok, NULL, 10);
        if (fieldNum == 15) { stime = strtoull(tok, NULL, 10); break; }
        tok = strtok(NULL, " ");
        fieldNum++;
    }

    unsigned long long total = utime + stime;
    double wall = now_seconds();
    long clkTck = sysconf(_SC_CLK_TCK);

    double pct = -1.0;
    if (lastWall > 0.0 && clkTck > 0) {
        double dCpu = (double)(total - lastTotal) / (double)clkTck;
        double dWall = wall - lastWall;
        if (dWall > 0.0) pct = 100.0 * dCpu / dWall;
    }
    lastTotal = total;
    lastWall = wall;
    return pct;
}

static int read_int_file(const char *path, int *out) {
    FILE *f = fopen(path, "r");
    if (!f) return 0;
    char buf[128];
    if (!fgets(buf, sizeof(buf), f)) { fclose(f); return 0; }
    fclose(f);
    char *end = NULL;
    long v = strtol(buf, &end, 10);
    if (end == buf) return 0;
    *out = (int)v;
    return 1;
}

static int read_gpu_load_sysfs(void) {
    static const char *paths[] = {
        "/sys/kernel/ged/hal/gpu_loading",
        "/sys/module/ged/parameters/gpu_loading",
        "/sys/class/misc/mali0/device/utilization",
        "/sys/devices/platform/13040000.mali/utilization",
        "/sys/kernel/gpu/gpu_busy",
        "/sys/class/kgsl/kgsl-3d0/gpu_busy_percentage",
        "/proc/mali/utilization",
        NULL
    };
    for (int i = 0; paths[i]; i++) {
        int v = -1;
        if (read_int_file(paths[i], &v) && v >= 0 && v <= 100)
            return v;
    }
    return -1;
}

static void hud_emit_quad(Vertex *v, uint32_t *n, float x0, float y0, float x1, float y1,
                          float r, float g, float b) {
    if (*n + 6 > HUD_MAX_VERTS) return;
    float pts[6][2] = {{x0,y0},{x1,y0},{x1,y1},{x0,y0},{x1,y1},{x0,y1}};
    for (int i = 0; i < 6; i++) {
        v[*n].pos[0] = pts[i][0];
        v[*n].pos[1] = -pts[i][1];
        v[*n].pos[2] = 0.0f;
        v[*n].normal[0] = r;
        v[*n].normal[1] = g;
        v[*n].normal[2] = b;
        v[*n].factor = -1.0f;
        (*n)++;
    }
}

static void hud_emit_char(Vertex *v, uint32_t *n, float origin_x, float origin_y,
                          float cw, float ch, char c, float r, float g, float b) {
    int idx = font_index(c);
    float px = cw / 5.0f;
    float py = ch / 7.0f;
    for (int row = 0; row < 7; row++) {
        uint8_t bits = FONT5x7[idx][row];
        for (int col = 0; col < 5; col++) {
            if (bits & (1u << (4 - col))) {
                float x0 = origin_x + col * px;
                float y0 = origin_y - row * py;
                hud_emit_quad(v, n, x0, y0, x0 + px * 0.85f, y0 - py * 0.85f, r, g, b);
            }
        }
    }
}

static uint32_t build_hud(Vertex *v, const char *line1, const char *line2) {
    uint32_t n = 0;
    /* top bar background */
    hud_emit_quad(v, &n, -1.0f, 1.0f, 1.0f, 0.82f, 0.02f, 0.03f, 0.05f);
    float x = -0.97f;
    float y = 0.97f;
    float cw = 0.028f;
    float ch = 0.055f;
    for (const char *p = line1; *p; p++) {
        hud_emit_char(v, &n, x, y, cw, ch, *p, 0.95f, 0.95f, 0.85f);
        x += cw * 1.15f;
    }
    x = -0.97f;
    y = 0.90f;
    for (const char *p = line2; *p; p++) {
        hud_emit_char(v, &n, x, y, cw, ch, *p, 0.55f, 0.95f, 0.70f);
        x += cw * 1.15f;
    }
    return n;
}

int main(void) {
    exe_dir(g_exedir, sizeof(g_exedir));
    generate_sphere(0.15f, 64, 64);
    printf("Generated sphere: %u vertices\n", g_vertexCount);
    printf("exe dir: %s\n", g_exedir);

    init_xcb_window();

    VkApplicationInfo appInfo = { .sType = VK_STRUCTURE_TYPE_APPLICATION_INFO };
    appInfo.pApplicationName = "panvk_sphere_real";
    appInfo.apiVersion = VK_API_VERSION_1_1;

    const char *instExt[] = { VK_KHR_SURFACE_EXTENSION_NAME, VK_KHR_XCB_SURFACE_EXTENSION_NAME };
    VkInstanceCreateInfo ici = { .sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO };
    ici.pApplicationInfo = &appInfo;
    ici.enabledExtensionCount = 2;
    ici.ppEnabledExtensionNames = instExt;

    VkInstance instance;
    VK_CHECK(vkCreateInstance(&ici, NULL, &instance));

    VkXcbSurfaceCreateInfoKHR surfCI = { .sType = VK_STRUCTURE_TYPE_XCB_SURFACE_CREATE_INFO_KHR };
    surfCI.connection = connection;
    surfCI.window = window;
    VkSurfaceKHR surface;
    VK_CHECK(vkCreateXcbSurfaceKHR(instance, &surfCI, NULL, &surface));

    uint32_t gpuCount = 0;
    vkEnumeratePhysicalDevices(instance, &gpuCount, NULL);
    if (gpuCount == 0) { fprintf(stderr, "No Vulkan-capable devices found\n"); exit(1); }
    VkPhysicalDevice *gpus = malloc(sizeof(VkPhysicalDevice) * gpuCount);
    vkEnumeratePhysicalDevices(instance, &gpuCount, gpus);
    VkPhysicalDevice gpu = gpus[0];
    free(gpus);

    VkPhysicalDeviceProperties props;
    vkGetPhysicalDeviceProperties(gpu, &props);
    char gpuLine[256];
    snprintf(gpuLine, sizeof(gpuLine), "%s  VK %u.%u.%u", props.deviceName,
             VK_VERSION_MAJOR(props.apiVersion), VK_VERSION_MINOR(props.apiVersion),
             VK_VERSION_PATCH(props.apiVersion));
    printf("Physical device: %s\n", gpuLine);

    uint32_t qCount = 0;
    vkGetPhysicalDeviceQueueFamilyProperties(gpu, &qCount, NULL);
    VkQueueFamilyProperties *qprops = malloc(sizeof(*qprops) * qCount);
    vkGetPhysicalDeviceQueueFamilyProperties(gpu, &qCount, qprops);
    int queueFamily = -1;
    for (uint32_t i = 0; i < qCount; i++) {
        VkBool32 presentSupport = VK_FALSE;
        vkGetPhysicalDeviceSurfaceSupportKHR(gpu, i, surface, &presentSupport);
        if ((qprops[i].queueFlags & VK_QUEUE_GRAPHICS_BIT) && presentSupport) { queueFamily = (int)i; break; }
    }
    free(qprops);
    if (queueFamily < 0) { fprintf(stderr, "No queue family supports graphics+present\n"); exit(1); }

    float qPriority = 1.0f;
    VkDeviceQueueCreateInfo qci = { .sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO };
    qci.queueFamilyIndex = (uint32_t)queueFamily;
    qci.queueCount = 1;
    qci.pQueuePriorities = &qPriority;

    const char *devExt[] = { VK_KHR_SWAPCHAIN_EXTENSION_NAME };
    VkDeviceCreateInfo dci = { .sType = VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO };
    dci.queueCreateInfoCount = 1;
    dci.pQueueCreateInfos = &qci;
    dci.enabledExtensionCount = 1;
    dci.ppEnabledExtensionNames = devExt;

    VkDevice device;
    VK_CHECK(vkCreateDevice(gpu, &dci, NULL, &device));

    VkQueue queue;
    vkGetDeviceQueue(device, (uint32_t)queueFamily, 0, &queue);

    VkSurfaceCapabilitiesKHR caps;
    vkGetPhysicalDeviceSurfaceCapabilitiesKHR(gpu, surface, &caps);

    uint32_t fmtCount = 0;
    vkGetPhysicalDeviceSurfaceFormatsKHR(gpu, surface, &fmtCount, NULL);
    VkSurfaceFormatKHR *fmts = malloc(sizeof(*fmts) * (fmtCount ? fmtCount : 1));
    if (fmtCount) vkGetPhysicalDeviceSurfaceFormatsKHR(gpu, surface, &fmtCount, fmts);
    VkSurfaceFormatKHR chosenFmt = fmtCount ? fmts[0] : (VkSurfaceFormatKHR){ VK_FORMAT_B8G8R8A8_UNORM, VK_COLOR_SPACE_SRGB_NONLINEAR_KHR };
    for (uint32_t i = 0; i < fmtCount; i++)
        if (fmts[i].format == VK_FORMAT_B8G8R8A8_UNORM &&
            fmts[i].colorSpace == VK_COLOR_SPACE_SRGB_NONLINEAR_KHR) { chosenFmt = fmts[i]; break; }
    free(fmts);

    VkExtent2D extent;
    if (caps.currentExtent.width != 0xFFFFFFFFu && caps.currentExtent.width != 0)
        extent = caps.currentExtent;
    else {
        extent.width = WIDTH;
        extent.height = HEIGHT;
    }
    if (extent.width < caps.minImageExtent.width) extent.width = caps.minImageExtent.width;
    if (extent.height < caps.minImageExtent.height) extent.height = caps.minImageExtent.height;
    if (caps.maxImageExtent.width && extent.width > caps.maxImageExtent.width) extent.width = caps.maxImageExtent.width;
    if (caps.maxImageExtent.height && extent.height > caps.maxImageExtent.height) extent.height = caps.maxImageExtent.height;
    printf("Swapchain extent %ux%u\n", extent.width, extent.height);

    uint32_t imgCount = caps.minImageCount + 1;
    if (caps.maxImageCount > 0 && imgCount > caps.maxImageCount) imgCount = caps.maxImageCount;

    uint32_t pmCount = 0;
    vkGetPhysicalDeviceSurfacePresentModesKHR(gpu, surface, &pmCount, NULL);
    VkPresentModeKHR *pms = pmCount ? malloc(sizeof(*pms) * pmCount) : NULL;
    if (pmCount) vkGetPhysicalDeviceSurfacePresentModesKHR(gpu, surface, &pmCount, pms);
    VkPresentModeKHR presentMode = VK_PRESENT_MODE_FIFO_KHR;
    if (pms) {
        int haveImmediate = 0, haveMailbox = 0;
        for (uint32_t i = 0; i < pmCount; i++) {
            if (pms[i] == VK_PRESENT_MODE_IMMEDIATE_KHR) haveImmediate = 1;
            if (pms[i] == VK_PRESENT_MODE_MAILBOX_KHR) haveMailbox = 1;
        }
        if (haveImmediate) presentMode = VK_PRESENT_MODE_IMMEDIATE_KHR;
        else if (haveMailbox) presentMode = VK_PRESENT_MODE_MAILBOX_KHR;
        free(pms);
    }
    printf("Present mode: %s\n",
           presentMode == VK_PRESENT_MODE_IMMEDIATE_KHR ? "IMMEDIATE (uncapped)" :
           presentMode == VK_PRESENT_MODE_MAILBOX_KHR ? "MAILBOX (uncapped)" :
           "FIFO (vsync-capped)");

    VkSwapchainCreateInfoKHR sci = { .sType = VK_STRUCTURE_TYPE_SWAPCHAIN_CREATE_INFO_KHR };
    sci.surface = surface;
    sci.minImageCount = imgCount;
    sci.imageFormat = chosenFmt.format;
    sci.imageColorSpace = chosenFmt.colorSpace;
    sci.imageExtent = extent;
    sci.imageArrayLayers = 1;
    sci.imageUsage = VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT;
    sci.imageSharingMode = VK_SHARING_MODE_EXCLUSIVE;
    sci.preTransform = caps.currentTransform;
    sci.compositeAlpha = VK_COMPOSITE_ALPHA_OPAQUE_BIT_KHR;
    sci.presentMode = presentMode;
    sci.clipped = VK_TRUE;

    VkSwapchainKHR swapchain;
    VK_CHECK(vkCreateSwapchainKHR(device, &sci, NULL, &swapchain));

    uint32_t scImageCount = 0;
    vkGetSwapchainImagesKHR(device, swapchain, &scImageCount, NULL);
    VkImage *scImages = malloc(sizeof(VkImage) * scImageCount);
    vkGetSwapchainImagesKHR(device, swapchain, &scImageCount, scImages);

    VkImageView *scImageViews = malloc(sizeof(VkImageView) * scImageCount);
    for (uint32_t i = 0; i < scImageCount; i++) {
        VkImageViewCreateInfo ivci = { .sType = VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO };
        ivci.image = scImages[i];
        ivci.viewType = VK_IMAGE_VIEW_TYPE_2D;
        ivci.format = chosenFmt.format;
        ivci.components.r = ivci.components.g = ivci.components.b = ivci.components.a = VK_COMPONENT_SWIZZLE_IDENTITY;
        ivci.subresourceRange.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
        ivci.subresourceRange.levelCount = 1;
        ivci.subresourceRange.layerCount = 1;
        VK_CHECK(vkCreateImageView(device, &ivci, NULL, &scImageViews[i]));
    }

    VkFormat depthFormat = VK_FORMAT_D32_SFLOAT;
    VkImageCreateInfo dici = { .sType = VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO };
    dici.imageType = VK_IMAGE_TYPE_2D;
    dici.format = depthFormat;
    dici.extent.width = extent.width; dici.extent.height = extent.height; dici.extent.depth = 1;
    dici.mipLevels = 1; dici.arrayLayers = 1;
    dici.samples = VK_SAMPLE_COUNT_1_BIT;
    dici.tiling = VK_IMAGE_TILING_OPTIMAL;
    dici.usage = VK_IMAGE_USAGE_DEPTH_STENCIL_ATTACHMENT_BIT;
    dici.sharingMode = VK_SHARING_MODE_EXCLUSIVE;
    dici.initialLayout = VK_IMAGE_LAYOUT_UNDEFINED;

    VkImage depthImage;
    VK_CHECK(vkCreateImage(device, &dici, NULL, &depthImage));

    VkPhysicalDeviceMemoryProperties memProps;
    vkGetPhysicalDeviceMemoryProperties(gpu, &memProps);

    VkMemoryRequirements dReq;
    vkGetImageMemoryRequirements(device, depthImage, &dReq);
    VkMemoryAllocateInfo dmai = { .sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO };
    dmai.allocationSize = dReq.size;
    dmai.memoryTypeIndex = find_memory_type(memProps, dReq.memoryTypeBits, VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT);
    VkDeviceMemory depthMemory;
    VK_CHECK(vkAllocateMemory(device, &dmai, NULL, &depthMemory));
    VK_CHECK(vkBindImageMemory(device, depthImage, depthMemory, 0));

    VkImageViewCreateInfo divci = { .sType = VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO };
    divci.image = depthImage;
    divci.viewType = VK_IMAGE_VIEW_TYPE_2D;
    divci.format = depthFormat;
    divci.subresourceRange.aspectMask = VK_IMAGE_ASPECT_DEPTH_BIT;
    divci.subresourceRange.levelCount = 1;
    divci.subresourceRange.layerCount = 1;
    VkImageView depthImageView;
    VK_CHECK(vkCreateImageView(device, &divci, NULL, &depthImageView));

    VkAttachmentDescription attachments[2] = { {0}, {0} };
    attachments[0].format = chosenFmt.format;
    attachments[0].samples = VK_SAMPLE_COUNT_1_BIT;
    attachments[0].loadOp = VK_ATTACHMENT_LOAD_OP_CLEAR;
    attachments[0].storeOp = VK_ATTACHMENT_STORE_OP_STORE;
    attachments[0].stencilLoadOp = VK_ATTACHMENT_LOAD_OP_DONT_CARE;
    attachments[0].stencilStoreOp = VK_ATTACHMENT_STORE_OP_DONT_CARE;
    attachments[0].initialLayout = VK_IMAGE_LAYOUT_UNDEFINED;
    attachments[0].finalLayout = VK_IMAGE_LAYOUT_PRESENT_SRC_KHR;

    attachments[1].format = depthFormat;
    attachments[1].samples = VK_SAMPLE_COUNT_1_BIT;
    attachments[1].loadOp = VK_ATTACHMENT_LOAD_OP_CLEAR;
    attachments[1].storeOp = VK_ATTACHMENT_STORE_OP_DONT_CARE;
    attachments[1].stencilLoadOp = VK_ATTACHMENT_LOAD_OP_DONT_CARE;
    attachments[1].stencilStoreOp = VK_ATTACHMENT_STORE_OP_DONT_CARE;
    attachments[1].initialLayout = VK_IMAGE_LAYOUT_UNDEFINED;
    attachments[1].finalLayout = VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL;

    VkAttachmentReference colorRef = { 0, VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL };
    VkAttachmentReference depthRef = { 1, VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL };

    VkSubpassDescription subpass = { 0 };
    subpass.pipelineBindPoint = VK_PIPELINE_BIND_POINT_GRAPHICS;
    subpass.colorAttachmentCount = 1;
    subpass.pColorAttachments = &colorRef;
    subpass.pDepthStencilAttachment = &depthRef;

    VkSubpassDependency dep = { 0 };
    dep.srcSubpass = VK_SUBPASS_EXTERNAL;
    dep.dstSubpass = 0;
    dep.srcStageMask = VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT | VK_PIPELINE_STAGE_EARLY_FRAGMENT_TESTS_BIT;
    dep.dstStageMask = VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT | VK_PIPELINE_STAGE_EARLY_FRAGMENT_TESTS_BIT;
    dep.dstAccessMask = VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT | VK_ACCESS_DEPTH_STENCIL_ATTACHMENT_WRITE_BIT;

    VkRenderPassCreateInfo rpci = { .sType = VK_STRUCTURE_TYPE_RENDER_PASS_CREATE_INFO };
    rpci.attachmentCount = 2;
    rpci.pAttachments = attachments;
    rpci.subpassCount = 1;
    rpci.pSubpasses = &subpass;
    rpci.dependencyCount = 1;
    rpci.pDependencies = &dep;

    VkRenderPass renderPass;
    VK_CHECK(vkCreateRenderPass(device, &rpci, NULL, &renderPass));

    VkFramebuffer *framebuffers = malloc(sizeof(VkFramebuffer) * scImageCount);
    for (uint32_t i = 0; i < scImageCount; i++) {
        VkImageView atts[2] = { scImageViews[i], depthImageView };
        VkFramebufferCreateInfo fci = { .sType = VK_STRUCTURE_TYPE_FRAMEBUFFER_CREATE_INFO };
        fci.renderPass = renderPass;
        fci.attachmentCount = 2;
        fci.pAttachments = atts;
        fci.width = extent.width;
        fci.height = extent.height;
        fci.layers = 1;
        VK_CHECK(vkCreateFramebuffer(device, &fci, NULL, &framebuffers[i]));
    }

    VkPushConstantRange pcRange = { .stageFlags = VK_SHADER_STAGE_VERTEX_BIT, .offset = 0, .size = sizeof(PushConstants) };
    VkPipelineLayoutCreateInfo plci = { .sType = VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO };
    plci.pushConstantRangeCount = 1;
    plci.pPushConstantRanges = &pcRange;
    VkPipelineLayout pipelineLayout;
    VK_CHECK(vkCreatePipelineLayout(device, &plci, NULL, &pipelineLayout));

    VkShaderModule vertModule = create_shader_module(device, "sphere.vert.spv");
    VkShaderModule fragModule = create_shader_module(device, "sphere.frag.spv");

    VkPipelineShaderStageCreateInfo stages[2] = { {0}, {0} };
    stages[0].sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO;
    stages[0].stage = VK_SHADER_STAGE_VERTEX_BIT;
    stages[0].module = vertModule;
    stages[0].pName = "main";
    stages[1].sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO;
    stages[1].stage = VK_SHADER_STAGE_FRAGMENT_BIT;
    stages[1].module = fragModule;
    stages[1].pName = "main";

    VkVertexInputBindingDescription binding = { 0, sizeof(Vertex), VK_VERTEX_INPUT_RATE_VERTEX };
    VkVertexInputAttributeDescription attrs[3];
    attrs[0] = (VkVertexInputAttributeDescription){ 0, 0, VK_FORMAT_R32G32B32_SFLOAT, offsetof(Vertex, pos) };
    attrs[1] = (VkVertexInputAttributeDescription){ 1, 0, VK_FORMAT_R32G32B32_SFLOAT, offsetof(Vertex, normal) };
    attrs[2] = (VkVertexInputAttributeDescription){ 2, 0, VK_FORMAT_R32_SFLOAT, offsetof(Vertex, factor) };

    VkPipelineVertexInputStateCreateInfo vi = { .sType = VK_STRUCTURE_TYPE_PIPELINE_VERTEX_INPUT_STATE_CREATE_INFO };
    vi.vertexBindingDescriptionCount = 1;
    vi.pVertexBindingDescriptions = &binding;
    vi.vertexAttributeDescriptionCount = 3;
    vi.pVertexAttributeDescriptions = attrs;

    VkPipelineInputAssemblyStateCreateInfo ia = { .sType = VK_STRUCTURE_TYPE_PIPELINE_INPUT_ASSEMBLY_STATE_CREATE_INFO };
    ia.topology = VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST;

    VkViewport viewport = { 0, 0, (float)extent.width, (float)extent.height, 0.0f, 1.0f };
    VkRect2D scissor = { { 0, 0 }, extent };
    VkPipelineViewportStateCreateInfo vpstate = { .sType = VK_STRUCTURE_TYPE_PIPELINE_VIEWPORT_STATE_CREATE_INFO };
    vpstate.viewportCount = 1; vpstate.pViewports = &viewport;
    vpstate.scissorCount = 1; vpstate.pScissors = &scissor;

    VkPipelineRasterizationStateCreateInfo rs = { .sType = VK_STRUCTURE_TYPE_PIPELINE_RASTERIZATION_STATE_CREATE_INFO };
    rs.polygonMode = VK_POLYGON_MODE_FILL;
    rs.cullMode = VK_CULL_MODE_NONE;
    rs.frontFace = VK_FRONT_FACE_COUNTER_CLOCKWISE;
    rs.lineWidth = 1.0f;

    VkPipelineMultisampleStateCreateInfo ms = { .sType = VK_STRUCTURE_TYPE_PIPELINE_MULTISAMPLE_STATE_CREATE_INFO };
    ms.rasterizationSamples = VK_SAMPLE_COUNT_1_BIT;

    VkPipelineDepthStencilStateCreateInfo ds = { .sType = VK_STRUCTURE_TYPE_PIPELINE_DEPTH_STENCIL_STATE_CREATE_INFO };
    ds.depthTestEnable = VK_TRUE;
    ds.depthWriteEnable = VK_TRUE;
    ds.depthCompareOp = VK_COMPARE_OP_LESS;

    VkPipelineColorBlendAttachmentState cba = { 0 };
    cba.colorWriteMask = VK_COLOR_COMPONENT_R_BIT | VK_COLOR_COMPONENT_G_BIT | VK_COLOR_COMPONENT_B_BIT | VK_COLOR_COMPONENT_A_BIT;
    VkPipelineColorBlendStateCreateInfo cb = { .sType = VK_STRUCTURE_TYPE_PIPELINE_COLOR_BLEND_STATE_CREATE_INFO };
    cb.attachmentCount = 1;
    cb.pAttachments = &cba;

    VkGraphicsPipelineCreateInfo gpci = { .sType = VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO };
    gpci.stageCount = 2;
    gpci.pStages = stages;
    gpci.pVertexInputState = &vi;
    gpci.pInputAssemblyState = &ia;
    gpci.pViewportState = &vpstate;
    gpci.pRasterizationState = &rs;
    gpci.pMultisampleState = &ms;
    gpci.pDepthStencilState = &ds;
    gpci.pColorBlendState = &cb;
    gpci.layout = pipelineLayout;
    gpci.renderPass = renderPass;
    gpci.subpass = 0;

    VkPipeline pipeline;
    VK_CHECK(vkCreateGraphicsPipelines(device, VK_NULL_HANDLE, 1, &gpci, NULL, &pipeline));

    /* HUD pipeline: same shaders, depth off so text stays on top */
    ds.depthTestEnable = VK_FALSE;
    ds.depthWriteEnable = VK_FALSE;
    VkPipeline hudPipeline;
    VK_CHECK(vkCreateGraphicsPipelines(device, VK_NULL_HANDLE, 1, &gpci, NULL, &hudPipeline));

    vkDestroyShaderModule(device, vertModule, NULL);
    vkDestroyShaderModule(device, fragModule, NULL);

    VkDeviceSize vbSize = sizeof(Vertex) * g_vertexCount;
    VkBufferCreateInfo bci = { .sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO };
    bci.size = vbSize;
    bci.usage = VK_BUFFER_USAGE_VERTEX_BUFFER_BIT;
    bci.sharingMode = VK_SHARING_MODE_EXCLUSIVE;
    VkBuffer vertexBuffer;
    VK_CHECK(vkCreateBuffer(device, &bci, NULL, &vertexBuffer));

    VkMemoryRequirements vbReq;
    vkGetBufferMemoryRequirements(device, vertexBuffer, &vbReq);
    VkMemoryAllocateInfo vmai = { .sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO };
    vmai.allocationSize = vbReq.size;
    vmai.memoryTypeIndex = find_memory_type(memProps, vbReq.memoryTypeBits,
                                             VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT);
    VkDeviceMemory vertexBufferMemory;
    VK_CHECK(vkAllocateMemory(device, &vmai, NULL, &vertexBufferMemory));
    VK_CHECK(vkBindBufferMemory(device, vertexBuffer, vertexBufferMemory, 0));

    void *mapped;
    VK_CHECK(vkMapMemory(device, vertexBufferMemory, 0, vbSize, 0, &mapped));
    memcpy(mapped, g_vertices, vbSize);
    vkUnmapMemory(device, vertexBufferMemory);

    Vertex *hudCpu = calloc(HUD_MAX_VERTS, sizeof(Vertex));
    VkDeviceSize hudSize = sizeof(Vertex) * HUD_MAX_VERTS;
    VkBufferCreateInfo hbci = { .sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO };
    hbci.size = hudSize;
    hbci.usage = VK_BUFFER_USAGE_VERTEX_BUFFER_BIT;
    hbci.sharingMode = VK_SHARING_MODE_EXCLUSIVE;
    VkBuffer hudBuffer;
    VK_CHECK(vkCreateBuffer(device, &hbci, NULL, &hudBuffer));
    VkMemoryRequirements hbReq;
    vkGetBufferMemoryRequirements(device, hudBuffer, &hbReq);
    VkMemoryAllocateInfo hmai = { .sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO };
    hmai.allocationSize = hbReq.size;
    hmai.memoryTypeIndex = find_memory_type(memProps, hbReq.memoryTypeBits,
                                             VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT);
    VkDeviceMemory hudMemory;
    VK_CHECK(vkAllocateMemory(device, &hmai, NULL, &hudMemory));
    VK_CHECK(vkBindBufferMemory(device, hudBuffer, hudMemory, 0));
    void *hudMapped = NULL;
    VK_CHECK(vkMapMemory(device, hudMemory, 0, hudSize, 0, &hudMapped));

    VkCommandPoolCreateInfo cpci = { .sType = VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO };
    cpci.queueFamilyIndex = (uint32_t)queueFamily;
    cpci.flags = VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT;
    VkCommandPool commandPool;
    VK_CHECK(vkCreateCommandPool(device, &cpci, NULL, &commandPool));

    VkCommandBufferAllocateInfo cbai = { .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO };
    cbai.commandPool = commandPool;
    cbai.level = VK_COMMAND_BUFFER_LEVEL_PRIMARY;
    cbai.commandBufferCount = 1;
    VkCommandBuffer commandBuffer;
    VK_CHECK(vkAllocateCommandBuffers(device, &cbai, &commandBuffer));

    VkSemaphoreCreateInfo semci = { .sType = VK_STRUCTURE_TYPE_SEMAPHORE_CREATE_INFO };
    VkSemaphore imageAvailableSem, renderFinishedSem;
    VK_CHECK(vkCreateSemaphore(device, &semci, NULL, &imageAvailableSem));
    VK_CHECK(vkCreateSemaphore(device, &semci, NULL, &renderFinishedSem));

    VkFenceCreateInfo fci2 = { .sType = VK_STRUCTURE_TYPE_FENCE_CREATE_INFO, .flags = VK_FENCE_CREATE_SIGNALED_BIT };
    VkFence inFlightFence;
    VK_CHECK(vkCreateFence(device, &fci2, NULL, &inFlightFence));

    double t0 = now_seconds();
    double lastTitleUpdate = t0;
    int frameCounter = 0;
    float angle = 0.0f, colorShift = 0.0f;
    double lastFrameTime = t0;
    double fps = 0.0, frameMs = 0.0;
    int gpuLoad = -1;
    int gpuLoadSysfs = -1;
    uint32_t hudCount = 0;

    {
        char l1[160], l2[160];
        snprintf(l1, sizeof(l1), "%s", gpuLine);
        snprintf(l2, sizeof(l2), "FPS --.-  FRAME --.--MS  GPU --%%  1280X720");
        hudCount = build_hud(hudCpu, l1, l2);
        memcpy(hudMapped, hudCpu, sizeof(Vertex) * hudCount);
    }

    printf("Entering render loop. Close the window or press ESC to quit.\n");

    int running = 1;
    while (running) {
        running = poll_events();
        if (!running) break;

        VkResult wr = vkWaitForFences(device, 1, &inFlightFence, VK_TRUE, UINT64_MAX);
        if (wr != VK_SUCCESS) break;
        vkResetFences(device, 1, &inFlightFence);

        uint32_t imageIndex;
        VkResult acq = vkAcquireNextImageKHR(device, swapchain, UINT64_MAX, imageAvailableSem, VK_NULL_HANDLE, &imageIndex);
        if (acq == VK_ERROR_OUT_OF_DATE_KHR) {
            vkResetFences(device, 1, &inFlightFence); /* keep signaled path simple: skip frame */
            continue;
        }
        if (acq != VK_SUCCESS && acq != VK_SUBOPTIMAL_KHR) {
            fprintf(stderr, "acquire failed %d\n", acq);
            break;
        }

        double t = now_seconds();
        double dt = t - lastFrameTime;
        lastFrameTime = t;
        if (dt <= 0.0 || dt > 1.0) dt = 1.0 / 60.0;
        angle += 45.0f * (float)dt;
        colorShift += 1.5f * (float)dt;

        float r1[16], r2[16], r3[16], tmp[16], model[16], view[16], proj[16], vp[16], mvp[16];
        mat4_rotate(r1, angle * 0.5f, 1.0f, 0.2f, 0.0f);
        mat4_rotate(r2, angle * 0.8f, 0.0f, 1.0f, 0.3f);
        mat4_rotate(r3, angle * 0.3f, 0.0f, 0.0f, 1.0f);
        mat4_mul(tmp, r1, r2);
        mat4_mul(model, tmp, r3);
        mat4_translate(view, 0.0f, 0.0f, -3.0f);
        mat4_perspective_vk(proj, 45.0f * (float)M_PI / 180.0f,
                            (float)extent.width / (float)extent.height, 0.1f, 50.0f);
        mat4_mul(vp, proj, view);
        mat4_mul(mvp, vp, model);

        vkResetCommandBuffer(commandBuffer, 0);
        VkCommandBufferBeginInfo cbbi = { .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO };
        vkBeginCommandBuffer(commandBuffer, &cbbi);

        VkClearValue clears[2];
        clears[0].color = (VkClearColorValue){{ 0.05f, 0.08f, 0.12f, 1.0f }};
        clears[1].depthStencil = (VkClearDepthStencilValue){ 1.0f, 0 };

        VkRenderPassBeginInfo rpbi = { .sType = VK_STRUCTURE_TYPE_RENDER_PASS_BEGIN_INFO };
        rpbi.renderPass = renderPass;
        rpbi.framebuffer = framebuffers[imageIndex];
        rpbi.renderArea.offset = (VkOffset2D){ 0, 0 };
        rpbi.renderArea.extent = extent;
        rpbi.clearValueCount = 2;
        rpbi.pClearValues = clears;

        vkCmdBeginRenderPass(commandBuffer, &rpbi, VK_SUBPASS_CONTENTS_INLINE);
        vkCmdBindPipeline(commandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS, pipeline);
        VkDeviceSize offsets[1] = { 0 };
        vkCmdBindVertexBuffers(commandBuffer, 0, 1, &vertexBuffer, offsets);

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

            float tOff[16], modelOff[16], mvpOff[16];

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

        if (hudCount > 0) {
            vkCmdBindPipeline(commandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS, hudPipeline);
            vkCmdBindVertexBuffers(commandBuffer, 0, 1, &hudBuffer, offsets);
            vkCmdDraw(commandBuffer, hudCount, 1, 0, 0);
        }
        vkCmdEndRenderPass(commandBuffer);
        vkEndCommandBuffer(commandBuffer);

        VkPipelineStageFlags waitStage = VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT;
        VkSubmitInfo submit = { .sType = VK_STRUCTURE_TYPE_SUBMIT_INFO };
        submit.waitSemaphoreCount = 1;
        submit.pWaitSemaphores = &imageAvailableSem;
        submit.pWaitDstStageMask = &waitStage;
        submit.commandBufferCount = 1;
        submit.pCommandBuffers = &commandBuffer;
        submit.signalSemaphoreCount = 1;
        submit.pSignalSemaphores = &renderFinishedSem;
        if (vkQueueSubmit(queue, 1, &submit, inFlightFence) != VK_SUCCESS)
            break;

        VkPresentInfoKHR present = { .sType = VK_STRUCTURE_TYPE_PRESENT_INFO_KHR };
        present.waitSemaphoreCount = 1;
        present.pWaitSemaphores = &renderFinishedSem;
        present.swapchainCount = 1;
        present.pSwapchains = &swapchain;
        present.pImageIndices = &imageIndex;
        VkResult pres = vkQueuePresentKHR(queue, &present);
        if (pres == VK_ERROR_OUT_OF_DATE_KHR)
            continue;

        frameCounter++;
        double now = now_seconds();
        if (now - lastTitleUpdate >= 0.5) {
            double elapsed = now - lastTitleUpdate;
            fps = frameCounter / elapsed;
            frameMs = (elapsed / frameCounter) * 1000.0;
            gpuLoadSysfs = read_gpu_load_sysfs();
            /* Estimate vs 16.67ms budget when sysfs is missing. FIFO vsync makes this a floor. */
            int est = (int)(frameMs / 16.67 * 100.0 + 0.5);
            if (est < 1) est = 1;
            if (est > 100) est = 100;
            gpuLoad = (gpuLoadSysfs >= 0) ? gpuLoadSysfs : est;

            long ramKb = get_ram_kb();
            double cpuPct = get_cpu_percent();

            char title[512], l1[160], l2[200];
            snprintf(title, sizeof(title),
                     "%s | FPS %.1f | %.2fms | GPU %d%% | %ux%u | RAM %.1fMB | CPU %.1f%%",
                     gpuLine, fps, frameMs, gpuLoad, extent.width, extent.height,
                     ramKb >= 0 ? ramKb / 1024.0 : -1.0, cpuPct >= 0 ? cpuPct : -1.0);
            set_window_title(title);
            printf("%s%s\n", title, gpuLoadSysfs >= 0 ? " (sysfs)" : " (est)");

            snprintf(l1, sizeof(l1), "%s", gpuLine);
            if (gpuLoadSysfs >= 0)
                snprintf(l2, sizeof(l2), "FPS %.1f  FRAME %.2fMS  GPU %d%%  %uX%u  RAM %.1fMB  CPU %.1f%%",
                         fps, frameMs, gpuLoad, extent.width, extent.height,
                         ramKb >= 0 ? ramKb / 1024.0 : -1.0, cpuPct >= 0 ? cpuPct : -1.0);
            else
                snprintf(l2, sizeof(l2), "FPS %.1f  FRAME %.2fMS  GPU ~%d%% EST  %uX%u  RAM %.1fMB  CPU %.1f%%",
                         fps, frameMs, gpuLoad, extent.width, extent.height,
                         ramKb >= 0 ? ramKb / 1024.0 : -1.0, cpuPct >= 0 ? cpuPct : -1.0);
            hudCount = build_hud(hudCpu, l1, l2);
            memcpy(hudMapped, hudCpu, sizeof(Vertex) * hudCount);

            lastTitleUpdate = now;
            frameCounter = 0;
        }
    }

    vkDeviceWaitIdle(device);
    vkDestroyFence(device, inFlightFence, NULL);
    vkDestroySemaphore(device, renderFinishedSem, NULL);
    vkDestroySemaphore(device, imageAvailableSem, NULL);
    vkDestroyCommandPool(device, commandPool, NULL);
    vkUnmapMemory(device, hudMemory);
    vkDestroyBuffer(device, hudBuffer, NULL);
    vkFreeMemory(device, hudMemory, NULL);
    free(hudCpu);
    vkDestroyBuffer(device, vertexBuffer, NULL);
    vkFreeMemory(device, vertexBufferMemory, NULL);
    vkDestroyPipeline(device, hudPipeline, NULL);
    vkDestroyPipeline(device, pipeline, NULL);
    vkDestroyPipelineLayout(device, pipelineLayout, NULL);
    for (uint32_t i = 0; i < scImageCount; i++) vkDestroyFramebuffer(device, framebuffers[i], NULL);
    free(framebuffers);
    vkDestroyRenderPass(device, renderPass, NULL);
    vkDestroyImageView(device, depthImageView, NULL);
    vkDestroyImage(device, depthImage, NULL);
    vkFreeMemory(device, depthMemory, NULL);
    for (uint32_t i = 0; i < scImageCount; i++) vkDestroyImageView(device, scImageViews[i], NULL);
    free(scImageViews);
    free(scImages);
    vkDestroySwapchainKHR(device, swapchain, NULL);
    vkDestroyDevice(device, NULL);
    vkDestroySurfaceKHR(instance, surface, NULL);
    vkDestroyInstance(instance, NULL);

    free(atom_wm_delete_window);
    xcb_destroy_window(connection, window);
    xcb_disconnect(connection);
    free(g_vertices);
    return 0;
}
