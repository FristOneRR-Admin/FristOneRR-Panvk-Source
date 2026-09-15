#include <stdio.h>
#include <stdlib.h>
#include <vulkan/vulkan.h>

static int check(VkResult r, const char *s)
{
    if (r != VK_SUCCESS) {
        fprintf(stderr, "%s: VkResult=%d", s, r);
        fputc(10, stderr);
        return 0;
    }
    return 1;
}

int main(void)
{
    VkApplicationInfo app = {0};
    app.sType = VK_STRUCTURE_TYPE_APPLICATION_INFO;
    app.pApplicationName = "PanVK headless test";
    app.apiVersion = VK_API_VERSION_1_1;

    VkInstanceCreateInfo ici = {0};
    ici.sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO;
    ici.pApplicationInfo = &app;

    VkInstance instance;
    if (!check(vkCreateInstance(&ici, 0, &instance),
               "vkCreateInstance failed")) return 1;

    unsigned count = 0;
    if (!check(vkEnumeratePhysicalDevices(instance, &count, 0),
               "enumerate count failed")) return 1;

    if (!count) {
        fputs("No Vulkan physical device", stderr);
        fputc(10, stderr);
        vkDestroyInstance(instance, 0);
        return 1;
    }

    VkPhysicalDevice *devices = calloc(count, sizeof(*devices));
    if (!devices) return 1;

    if (!check(vkEnumeratePhysicalDevices(instance, &count, devices),
               "enumerate devices failed")) return 1;

    VkPhysicalDeviceProperties props;
    vkGetPhysicalDeviceProperties(devices[0], &props);
    printf("deviceName: %s", props.deviceName);
    putchar(10);
    printf("apiVersion: %u.%u.%u",
           VK_VERSION_MAJOR(props.apiVersion),
           VK_VERSION_MINOR(props.apiVersion),
           VK_VERSION_PATCH(props.apiVersion));
    putchar(10);

    unsigned qcount = 0;
    vkGetPhysicalDeviceQueueFamilyProperties(devices[0], &qcount, 0);
    VkQueueFamilyProperties *queues = calloc(qcount, sizeof(*queues));

    vkGetPhysicalDeviceQueueFamilyProperties(devices[0], &qcount, queues);
    printf("queueFamilies: %u", qcount);
    putchar(10);

    for (unsigned i = 0; i < qcount; i++) {
        printf("queue[%u]: count=%u flags=0x%x",
               i, queues[i].queueCount, queues[i].queueFlags);
        putchar(10);
    }

    float priority = 1.0f;
    VkDeviceQueueCreateInfo qci = {0};
    qci.sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO;
    qci.queueFamilyIndex = 0;
    qci.queueCount = 1;
    qci.pQueuePriorities = &priority;

    VkDeviceCreateInfo dci = {0};
    dci.sType = VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO;
    dci.queueCreateInfoCount = 1;
    dci.pQueueCreateInfos = &qci;

    VkDevice device;
    fputs("BEFORE vkCreateDevice", stdout);
    putchar(10);
    fflush(stdout);
    if (!check(vkCreateDevice(devices[0], &dci, 0, &device),
               "vkCreateDevice failed")) return 1;

    fputs("vkCreateDevice: OK", stdout);
    fflush(stdout);
    putchar(10);

    vkDeviceWaitIdle(device);
    vkDestroyDevice(device, 0);
    vkDestroyInstance(instance, 0);
    free(queues);
    free(devices);
    return 0;
}
