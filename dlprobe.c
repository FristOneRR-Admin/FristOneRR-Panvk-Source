#include <stdio.h>
#include <dlfcn.h>

int main(void)
{
    void *h = dlopen(
        "/data/data/com.termux/files/home/mesa/build/src/panfrost/vulkan/libvulkan_panfrost.so",
        RTLD_NOW | RTLD_LOCAL);

    if (!h) {
        const char *e = dlerror();
        fputs(e ? e : "unknown dlopen error", stderr);
        fputc(10, stderr);
        return 1;
    }

    puts("dlopen OK");
    dlclose(h);
    return 0;
}
