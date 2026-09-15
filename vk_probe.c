#include <stdio.h>
#include <vulkan/vulkan.h>

int main(void)
{
    VkApplicationInfo a = {0};
    a.sType = VK_STRUCTURE_TYPE_APPLICATION_INFO;
    a.pApplicationName = "probe";
    a.apiVersion = VK_API_VERSION_1_0;

    VkInstanceCreateInfo c = {0};
    c.sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO;
    c.pApplicationInfo = &a;

    VkInstance i = 0;
    VkResult r = vkCreateInstance(&c, 0, &i);

    printf("create=%d", r);
    putchar(10);

    if (r != VK_SUCCESS)
        return 1;

    unsigned n = 0;
    r = vkEnumeratePhysicalDevices(i, &n, 0);

    printf("enumerate=%d count=%u", r, n);
    putchar(10);

    vkDestroyInstance(i, 0);
    return 0;
}
