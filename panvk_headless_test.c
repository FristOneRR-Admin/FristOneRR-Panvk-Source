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

    VkDeviceCreateInfo dci = {
    .sType = VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO,
    .pNext = NULL,
    .flags = 0,
    .queueCreateInfoCount = 1,
    .pQueueCreateInfos = &qci,
    .enabledLayerCount = 0,
    .ppEnabledLayerNames = NULL,
    .enabledExtensionCount = 0,
    .ppEnabledExtensionNames = NULL,
    .pEnabledFeatures = NULL
   };  
  
    VkDevice device;
    fputs("BEFORE vkCreateDevice", stdout);
    putchar(10);
    fflush(stdout);
    if (!check(vkCreateDevice(devices[0], &dci, 0, &device),
               "vkCreateDevice failed")) return 1;

    fputs("vkCreateDevice: OK", stdout);
    fflush(stdout);
    putchar(10);

    VkQueue queue;
    vkGetDeviceQueue(device, 0, 0, &queue);
    VkCommandPoolCreateInfo pci = {0};
    pci.sType = VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO;
    pci.queueFamilyIndex = 0;
    VkCommandPool pool;
    if (!check(vkCreateCommandPool(device, &pci, 0, &pool), "vkCreateCommandPool failed")) return 1;
    VkCommandBufferAllocateInfo cai = {0};
    cai.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO;
    cai.commandPool = pool;
    cai.level = VK_COMMAND_BUFFER_LEVEL_PRIMARY;
    cai.commandBufferCount = 1;
    VkCommandBuffer cmd;
    if (!check(vkAllocateCommandBuffers(device, &cai, &cmd), "vkAllocateCommandBuffers failed")) return 1;
    VkCommandBufferBeginInfo bi = {0};
    bi.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO;
    bi.flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;
    if (!check(vkBeginCommandBuffer(cmd, &bi), "vkBeginCommandBuffer failed")) return 1;
    if (!check(vkEndCommandBuffer(cmd), "vkEndCommandBuffer failed")) return 1;
    VkSubmitInfo si = {0};
    si.sType = VK_STRUCTURE_TYPE_SUBMIT_INFO;
    si.commandBufferCount = 1;
    si.pCommandBuffers = &cmd;
    fputs("BEFORE vkQueueSubmit\n", stdout);
    fflush(stdout);
    if (!check(vkQueueSubmit(queue, 1, &si, VK_NULL_HANDLE), "vkQueueSubmit failed")) return 1;
    fputs("vkQueueSubmit: OK\n", stdout);
    vkDeviceWaitIdle(device);
    vkFreeCommandBuffers(device, pool, 1, &cmd);
    vkDestroyCommandPool(device, pool, 0);
    vkDeviceWaitIdle(device);
    vkDestroyDevice(device, 0);
    vkDestroyInstance(instance, 0);
    free(queues);
    free(devices);
    return 0;
}
