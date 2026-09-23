#!/usr/bin/env python3
import os, sys, time
from ctypes import *

os.environ["PAN_I_WANT_A_BROKEN_VULKAN_DRIVER"] = "1"

VK_STRUCTURE_TYPE_APPLICATION_INFO = 0
VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO = 1
VK_STRUCTURE_TYPE_XCB_SURFACE_CREATE_INFO_KHR = 1000009000
VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO = 3
VK_STRUCTURE_TYPE_SWAPCHAIN_CREATE_INFO_KHR = 1000001000
VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO = 10
VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO = 29
VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO = 30
VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO = 31
VK_STRUCTURE_TYPE_SUBMIT_INFO = 4
VK_STRUCTURE_TYPE_PRESENT_INFO_KHR = 1000001001
VK_STRUCTURE_TYPE_SEMAPHORE_CREATE_INFO = 5
VK_STRUCTURE_TYPE_FENCE_CREATE_INFO = 6
VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER = 7

VK_API_VERSION_1_0 = (1 << 22)
VK_QUEUE_GRAPHICS_BIT = 1
VK_IMAGE_USAGE_TRANSFER_DST_BIT = 4
VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT = 16
VK_SHARING_MODE_EXCLUSIVE = 0
VK_COMPOSITE_ALPHA_OPAQUE_BIT_KHR = 16
VK_PRESENT_MODE_FIFO_KHR = 0
VK_FENCE_CREATE_SIGNALED_BIT = 1
VK_IMAGE_VIEW_TYPE_2D = 1
VK_IMAGE_ASPECT_COLOR_BIT = 1
VK_IMAGE_LAYOUT_UNDEFINED = 0
VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL = 6
VK_IMAGE_LAYOUT_PRESENT_SRC_KHR = 1000001002
VK_ACCESS_TRANSFER_WRITE_BIT = 4096
VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT = 1
VK_PIPELINE_STAGE_TRANSFER_BIT = 4096
VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT = 4096
VK_SUCCESS = 0
VK_SUBOPTIMAL_KHR = 1000001003
VK_NULL_HANDLE = 0

VkInstance = c_void_p
VkPhysicalDevice = c_void_p
VkDevice = c_void_p
VkQueue = c_void_p
VkSurfaceKHR = c_uint64
VkSwapchainKHR = c_uint64
VkImage = c_uint64
VkImageView = c_uint64
VkCommandPool = c_uint64
VkCommandBuffer = c_void_p
VkSemaphore = c_uint64
VkFence = c_uint64

class VkApplicationInfo(Structure):
    _fields_ = [("sType", c_uint32), ("pNext", c_void_p), ("pApplicationName", c_char_p), ("applicationVersion", c_uint32), ("pEngineName", c_char_p), ("engineVersion", c_uint32), ("apiVersion", c_uint32)]

class VkInstanceCreateInfo(Structure):
    _fields_ = [("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32), ("pApplicationInfo", c_void_p), ("enabledLayerCount", c_uint32), ("ppEnabledLayerNames", POINTER(c_char_p)), ("enabledExtensionCount", c_uint32), ("ppEnabledExtensionNames", POINTER(c_char_p))]

class VkXcbSurfaceCreateInfoKHR(Structure):
    _fields_ = [("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32), ("connection", c_void_p), ("window", c_uint32)]

class VkQueueFamilyProperties(Structure):
    _fields_ = [("queueFlags", c_uint32), ("queueCount", c_uint32), ("timestampValidBits", c_uint32), ("minImageTransferGranularity", c_uint32 * 3)]

class VkDeviceQueueCreateInfo(Structure):
    _fields_ = [("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32), ("queueFamilyIndex", c_uint32), ("queueCount", c_uint32), ("pQueuePriorities", POINTER(c_float))]

class VkDeviceCreateInfo(Structure):
    _fields_ = [("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32), ("queueCreateInfoCount", c_uint32), ("pQueueCreateInfos", c_void_p), ("enabledLayerCount", c_uint32), ("ppEnabledLayerNames", POINTER(c_char_p)), ("enabledExtensionCount", c_uint32), ("ppEnabledExtensionNames", POINTER(c_char_p)), ("pEnabledFeatures", c_void_p)]

class VkSurfaceCapabilitiesKHR(Structure):
    _fields_ = [("minImageCount", c_uint32), ("maxImageCount", c_uint32), ("currentExtent", c_uint32 * 2), ("minImageExtent", c_uint32 * 2), ("maxImageExtent", c_uint32 * 2), ("maxImageArrayLayers", c_uint32), ("supportedTransforms", c_uint32), ("currentTransform", c_uint32), ("supportedCompositeAlpha", c_uint32), ("supportedUsageFlags", c_uint32)]

class VkSurfaceFormatKHR(Structure):
    _fields_ = [("format", c_uint32), ("colorSpace", c_uint32)]

class VkSwapchainCreateInfoKHR(Structure):
    _fields_ = [("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32), ("surface", VkSurfaceKHR), ("minImageCount", c_uint32), ("imageFormat", c_uint32), ("imageColorSpace", c_uint32), ("imageExtent", c_uint32 * 2), ("imageArrayLayers", c_uint32), ("imageUsage", c_uint32), ("imageSharingMode", c_uint32), ("queueFamilyIndexCount", c_uint32), ("pQueueFamilyIndices", c_void_p), ("preTransform", c_uint32), ("compositeAlpha", c_uint32), ("presentMode", c_uint32), ("clipped", c_bool), ("oldSwapchain", VkSwapchainKHR)]

class VkImageViewCreateInfo(Structure):
    _fields_ = [("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32), ("image", VkImage), ("viewType", c_uint32), ("format", c_uint32), ("components", c_uint32 * 4), ("subresourceRange", c_uint32 * 5)]

class VkCommandPoolCreateInfo(Structure):
    _fields_ = [("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32), ("queueFamilyIndex", c_uint32)]

class VkCommandBufferAllocateInfo(Structure):
    _fields_ = [("sType", c_uint32), ("pNext", c_void_p), ("commandPool", VkCommandPool), ("level", c_uint32), ("commandBufferCount", c_uint32)]

class VkCommandBufferBeginInfo(Structure):
    _fields_ = [("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32), ("pInheritanceInfo", c_void_p)]

class VkSubmitInfo(Structure):
    _fields_ = [("sType", c_uint32), ("pNext", c_void_p), ("waitSemaphoreCount", c_uint32), ("pWaitSemaphores", c_void_p), ("pWaitDstStageMask", c_void_p), ("commandBufferCount", c_uint32), ("pCommandBuffers", c_void_p), ("signalSemaphoreCount", c_uint32), ("pSignalSemaphores", c_void_p)]

class VkPresentInfoKHR(Structure):
    _fields_ = [("sType", c_uint32), ("pNext", c_void_p), ("waitSemaphoreCount", c_uint32), ("pWaitSemaphores", c_void_p), ("swapchainCount", c_uint32), ("pSwapchains", c_void_p), ("pImageIndices", c_void_p), ("pResults", c_void_p)]

class VkSemaphoreCreateInfo(Structure):
    _fields_ = [("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32)]

class VkFenceCreateInfo(Structure):
    _fields_ = [("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32)]

class VkImageSubresourceRange(Structure):
    _fields_ = [("aspectMask", c_uint32), ("baseMipLevel", c_uint32), ("levelCount", c_uint32), ("baseArrayLayer", c_uint32), ("layerCount", c_uint32)]

class VkImageMemoryBarrier(Structure):
    _fields_ = [("sType", c_uint32), ("pNext", c_void_p), ("srcAccessMask", c_uint32), ("dstAccessMask", c_uint32), ("oldLayout", c_uint32), ("newLayout", c_uint32), ("srcQueueFamilyIndex", c_uint32), ("dstQueueFamilyIndex", c_uint32), ("image", VkImage), ("subresourceRange", VkImageSubresourceRange)]

class VkClearColorValue(Structure):
    _fields_ = [("float32", c_float * 4)]

print("Loading...")
vk = CDLL("libvulkan.so.1")
xcb = CDLL("libxcb.so.1")
print("OK")

xcb_connect = xcb.xcb_connect
xcb_connect.argtypes = [c_char_p, POINTER(c_int)]
xcb_connect.restype = c_void_p
xcb_get_setup = xcb.xcb_get_setup
xcb_get_setup.argtypes = [c_void_p]
xcb_get_setup.restype = c_void_p
xcb_setup_roots_iterator = xcb.xcb_setup_roots_iterator
xcb_setup_roots_iterator.argtypes = [c_void_p]
xcb_setup_roots_iterator.restype = c_void_p
xcb_generate_id = xcb.xcb_generate_id
xcb_generate_id.argtypes = [c_void_p]
xcb_generate_id.restype = c_uint32
xcb_create_window = xcb.xcb_create_window
xcb_create_window.argtypes = [c_void_p, c_uint8, c_uint32, c_uint32, c_int16, c_int16, c_uint16, c_uint16, c_uint16, c_uint16, c_uint32, c_uint32, c_void_p]
xcb_map_window = xcb.xcb_map_window
xcb_map_window.argtypes = [c_void_p, c_uint32]
xcb_flush = xcb.xcb_flush
xcb_flush.argtypes = [c_void_p]
xcb_flush.restype = c_int
xcb_destroy_window = xcb.xcb_destroy_window
xcb_destroy_window.argtypes = [c_void_p, c_uint32]
xcb_disconnect = xcb.xcb_disconnect
xcb_disconnect.argtypes = [c_void_p]

vkCreateInstance = vk.vkCreateInstance
vkCreateInstance.argtypes = [POINTER(VkInstanceCreateInfo), c_void_p, POINTER(VkInstance)]
vkEnumeratePhysicalDevices = vk.vkEnumeratePhysicalDevices
vkEnumeratePhysicalDevices.argtypes = [VkInstance, POINTER(c_uint32), POINTER(VkPhysicalDevice)]
vkGetPhysicalDeviceQueueFamilyProperties = vk.vkGetPhysicalDeviceQueueFamilyProperties
vkGetPhysicalDeviceQueueFamilyProperties.argtypes = [VkPhysicalDevice, POINTER(c_uint32), POINTER(VkQueueFamilyProperties)]
vkGetPhysicalDeviceSurfaceSupportKHR = vk.vkGetPhysicalDeviceSurfaceSupportKHR
vkGetPhysicalDeviceSurfaceSupportKHR.argtypes = [VkPhysicalDevice, c_uint32, VkSurfaceKHR, POINTER(c_uint32)]
vkCreateDevice = vk.vkCreateDevice
vkCreateDevice.argtypes = [VkPhysicalDevice, POINTER(VkDeviceCreateInfo), c_void_p, POINTER(VkDevice)]
vkGetDeviceQueue = vk.vkGetDeviceQueue
vkGetDeviceQueue.argtypes = [VkDevice, c_uint32, c_uint32, POINTER(VkQueue)]
vkGetPhysicalDeviceSurfaceCapabilitiesKHR = vk.vkGetPhysicalDeviceSurfaceCapabilitiesKHR
vkGetPhysicalDeviceSurfaceCapabilitiesKHR.argtypes = [VkPhysicalDevice, VkSurfaceKHR, POINTER(VkSurfaceCapabilitiesKHR)]
vkGetPhysicalDeviceSurfaceFormatsKHR = vk.vkGetPhysicalDeviceSurfaceFormatsKHR
vkGetPhysicalDeviceSurfaceFormatsKHR.argtypes = [VkPhysicalDevice, VkSurfaceKHR, POINTER(c_uint32), POINTER(VkSurfaceFormatKHR)]
vkCreateSwapchainKHR = vk.vkCreateSwapchainKHR
vkCreateSwapchainKHR.argtypes = [VkDevice, POINTER(VkSwapchainCreateInfoKHR), c_void_p, POINTER(VkSwapchainKHR)]
vkGetSwapchainImagesKHR = vk.vkGetSwapchainImagesKHR
vkGetSwapchainImagesKHR.argtypes = [VkDevice, VkSwapchainKHR, POINTER(c_uint32), POINTER(VkImage)]
vkCreateImageView = vk.vkCreateImageView
vkCreateImageView.argtypes = [VkDevice, POINTER(VkImageViewCreateInfo), c_void_p, POINTER(VkImageView)]
vkCreateCommandPool = vk.vkCreateCommandPool
vkCreateCommandPool.argtypes = [VkDevice, POINTER(VkCommandPoolCreateInfo), c_void_p, POINTER(VkCommandPool)]
vkAllocateCommandBuffers = vk.vkAllocateCommandBuffers
vkAllocateCommandBuffers.argtypes = [VkDevice, POINTER(VkCommandBufferAllocateInfo), POINTER(VkCommandBuffer)]
vkBeginCommandBuffer = vk.vkBeginCommandBuffer
vkBeginCommandBuffer.argtypes = [VkCommandBuffer, POINTER(VkCommandBufferBeginInfo)]
vkEndCommandBuffer = vk.vkEndCommandBuffer
vkEndCommandBuffer.argtypes = [VkCommandBuffer]
vkCmdClearColorImage = vk.vkCmdClearColorImage
vkCmdClearColorImage.argtypes = [VkCommandBuffer, VkImage, c_uint32, POINTER(VkClearColorValue), c_uint32, POINTER(VkImageSubresourceRange)]
vkCmdPipelineBarrier = vk.vkCmdPipelineBarrier
vkCmdPipelineBarrier.argtypes = [VkCommandBuffer, c_uint32, c_uint32, c_uint32, c_uint32, c_void_p, c_uint32, c_void_p, c_uint32, POINTER(VkImageMemoryBarrier)]
vkCreateSemaphore = vk.vkCreateSemaphore
vkCreateSemaphore.argtypes = [VkDevice, POINTER(VkSemaphoreCreateInfo), c_void_p, POINTER(VkSemaphore)]
vkCreateFence = vk.vkCreateFence
vkCreateFence.argtypes = [VkDevice, POINTER(VkFenceCreateInfo), c_void_p, POINTER(VkFence)]
vkWaitForFences = vk.vkWaitForFences
vkWaitForFences.argtypes = [VkDevice, c_uint32, POINTER(VkFence), c_bool, c_uint64]
vkResetFences = vk.vkResetFences
vkResetFences.argtypes = [VkDevice, c_uint32, POINTER(VkFence)]
vkAcquireNextImageKHR = vk.vkAcquireNextImageKHR
vkAcquireNextImageKHR.argtypes = [VkDevice, VkSwapchainKHR, c_uint64, VkSemaphore, VkFence, POINTER(c_uint32)]
vkQueueSubmit = vk.vkQueueSubmit
vkQueueSubmit.argtypes = [VkQueue, c_uint32, POINTER(VkSubmitInfo), VkFence]
vkQueuePresentKHR = vk.vkQueuePresentKHR
vkQueuePresentKHR.argtypes = [VkQueue, POINTER(VkPresentInfoKHR)]
vkDestroyImageView = vk.vkDestroyImageView
vkDestroyImageView.argtypes = [VkDevice, VkImageView, c_void_p]
vkDestroySwapchainKHR = vk.vkDestroySwapchainKHR
vkDestroySwapchainKHR.argtypes = [VkDevice, VkSwapchainKHR, c_void_p]
vkDestroyCommandPool = vk.vkDestroyCommandPool
vkDestroyCommandPool.argtypes = [VkDevice, VkCommandPool, c_void_p]
vkDestroySemaphore = vk.vkDestroySemaphore
vkDestroySemaphore.argtypes = [VkDevice, VkSemaphore, c_void_p]
vkDestroyFence = vk.vkDestroyFence
vkDestroyFence.argtypes = [VkDevice, VkFence, c_void_p]
vkDestroyDevice = vk.vkDestroyDevice
vkDestroyDevice.argtypes = [VkDevice, c_void_p]
vkDeviceWaitIdle = vk.vkDeviceWaitIdle
vkDeviceWaitIdle.argtypes = [VkDevice]
vkDestroySurfaceKHR = vk.vkDestroySurfaceKHR
vkDestroySurfaceKHR.argtypes = [VkInstance, VkSurfaceKHR, c_void_p]
vkDestroyInstance = vk.vkDestroyInstance
vkDestroyInstance.argtypes = [VkInstance, c_void_p]
vkCreateXcbSurfaceKHR = vk.vkCreateXcbSurfaceKHR
vkCreateXcbSurfaceKHR.argtypes = [VkInstance, POINTER(VkXcbSurfaceCreateInfoKHR), c_void_p, POINTER(VkSurfaceKHR)]

def vk_check(r, m):
    if r != 0 and r != 1000001003:
        print("ERR:", m, r)
        sys.exit(1)

print("=== Clear Color Test ===")
conn = xcb_connect(None, None)
screen_ptr = xcb_setup_roots_iterator(xcb_get_setup(conn))
Screen = type("Screen", (Structure,), {"_fields_": [("root", c_uint32), ("default_colormap", c_uint32), ("white_pixel", c_uint32), ("black_pixel", c_uint32), ("current_input_masks", c_uint32), ("width_in_pixels", c_uint16), ("height_in_pixels", c_uint16), ("width_in_millimeters", c_uint16), ("height_in_millimeters", c_uint16), ("min_installed_maps", c_uint16), ("max_installed_maps", c_uint16), ("root_visual", c_uint32), ("backing_stores", c_uint8), ("save_unders", c_uint8), ("root_depth", c_uint8), ("allowed_depths_len", c_uint8)]})
screen = cast(screen_ptr, POINTER(Screen)).contents
window = xcb_generate_id(conn)
values = (c_uint32 * 1)(screen.white_pixel)
xcb_create_window(conn, 0, window, screen.root, 100, 100, 640, 480, 0, 0, screen.root_visual, 2, values)
xcb_map_window(conn, window)
xcb_flush(conn)
print("Window:", window)

app_info = VkApplicationInfo()
app_info.sType = 0
app_info.pApplicationName = b"Test"
app_info.apiVersion = (1 << 22)
exts = (c_char_p * 2)()
exts[0] = "VK_KHR_surface".encode()
exts[1] = "VK_KHR_xcb_surface".encode()
inst_info = VkInstanceCreateInfo()
inst_info.sType = 1
inst_info.pApplicationInfo = cast(byref(app_info), c_void_p).value
inst_info.enabledExtensionCount = 2
inst_info.ppEnabledExtensionNames = exts
instance = VkInstance()
vk_check(vkCreateInstance(byref(inst_info), None, byref(instance)), "inst")

surface_info = VkXcbSurfaceCreateInfoKHR()
surface_info.sType = 1000009000
surface_info.connection = conn
surface_info.window = window
surface = VkSurfaceKHR()
vk_check(vkCreateXcbSurfaceKHR(instance, byref(surface_info), None, byref(surface)), "surf")

device_count = c_uint32()
vkEnumeratePhysicalDevices(instance, byref(device_count), None)
phys_dev = VkPhysicalDevice()
vkEnumeratePhysicalDevices(instance, byref(device_count), byref(phys_dev))

queue_family_count = c_uint32()
vkGetPhysicalDeviceQueueFamilyProperties(phys_dev, byref(queue_family_count), None)
queue_families = (VkQueueFamilyProperties * queue_family_count.value)()
vkGetPhysicalDeviceQueueFamilyProperties(phys_dev, byref(queue_family_count), queue_families)
queue_family_index = 0
for i in range(queue_family_count.value):
    present_support = c_uint32()
    vkGetPhysicalDeviceSurfaceSupportKHR(phys_dev, i, surface, byref(present_support))
    if (queue_families[i].queueFlags & 1) and present_support.value:
        queue_family_index = i
        break

queue_priority = (c_float * 1)(1.0)
queue_info = VkDeviceQueueCreateInfo()
queue_info.sType = 3
queue_info.queueFamilyIndex = queue_family_index
queue_info.queueCount = 1
queue_info.pQueuePriorities = queue_priority
dev_exts = (c_char_p * 1)()
dev_exts[0] = "VK_KHR_swapchain".encode()
dev_info = VkDeviceCreateInfo()
dev_info.sType = 3
dev_info.queueCreateInfoCount = 1
dev_info.pQueueCreateInfos = cast(byref(queue_info), c_void_p).value
dev_info.enabledExtensionCount = 1
dev_info.ppEnabledExtensionNames = dev_exts
device = VkDevice()
vk_check(vkCreateDevice(phys_dev, byref(dev_info), None, byref(device)), "dev")
queue = VkQueue()
vkGetDeviceQueue(device, queue_family_index, 0, byref(queue))

caps = VkSurfaceCapabilitiesKHR()
vkGetPhysicalDeviceSurfaceCapabilitiesKHR(phys_dev, surface, byref(caps))
format_count = c_uint32()
vkGetPhysicalDeviceSurfaceFormatsKHR(phys_dev, surface, byref(format_count), None)
formats = (VkSurfaceFormatKHR * format_count.value)()
vkGetPhysicalDeviceSurfaceFormatsKHR(phys_dev, surface, byref(format_count), formats)

swap_info = VkSwapchainCreateInfoKHR()
swap_info.sType = 1000001000
swap_info.surface = surface
swap_info.minImageCount = caps.minImageCount + 1
swap_info.imageFormat = formats[0].format
swap_info.imageColorSpace = formats[0].colorSpace
swap_info.imageExtent[0] = caps.currentExtent[0]
swap_info.imageExtent[1] = caps.currentExtent[1]
swap_info.imageArrayLayers = 1
swap_info.imageUsage = 4 | 16
swap_info.imageSharingMode = 0
swap_info.preTransform = caps.currentTransform
swap_info.compositeAlpha = 16
swap_info.presentMode = 0
swap_info.clipped = True
swapchain = VkSwapchainKHR()
vk_check(vkCreateSwapchainKHR(device, byref(swap_info), None, byref(swapchain)), "swap")

image_count = c_uint32()
vkGetSwapchainImagesKHR(device, swapchain, byref(image_count), None)
images = (VkImage * image_count.value)()
vkGetSwapchainImagesKHR(device, swapchain, byref(image_count), images)

image_views = (VkImageView * image_count.value)()
for i in range(image_count.value):
    view_info = VkImageViewCreateInfo()
    view_info.sType = 10
    view_info.image = images[i]
    view_info.viewType = 1
    view_info.format = formats[0].format
    view_info.subresourceRange[0] = 1
    view_info.subresourceRange[1] = 0
    view_info.subresourceRange[2] = 1
    view_info.subresourceRange[3] = 0
    view_info.subresourceRange[4] = 1
    vk_check(vkCreateImageView(device, byref(view_info), None, byref(image_views[i])), "view")

cmd_pool_info = VkCommandPoolCreateInfo()
cmd_pool_info.sType = 29
cmd_pool_info.queueFamilyIndex = queue_family_index
cmd_pool = VkCommandPool()
vk_check(vkCreateCommandPool(device, byref(cmd_pool_info), None, byref(cmd_pool)), "pool")

cmd_buf_alloc = VkCommandBufferAllocateInfo()
cmd_buf_alloc.sType = 30
cmd_buf_alloc.commandPool = cmd_pool
cmd_buf_alloc.level = 0
cmd_buf_alloc.commandBufferCount = image_count.value
cmd_buffers = (VkCommandBuffer * image_count.value)()
vk_check(vkAllocateCommandBuffers(device, byref(cmd_buf_alloc), cmd_buffers), "cmd")

sem_info = VkSemaphoreCreateInfo()
sem_info.sType = 5
image_available = VkSemaphore()
render_finished = VkSemaphore()
vk_check(vkCreateSemaphore(device, byref(sem_info), None, byref(image_available)), "sem")
vk_check(vkCreateSemaphore(device, byref(sem_info), None, byref(render_finished)), "sem")

fences = (VkFence * image_count.value)()
fence_info = VkFenceCreateInfo()
fence_info.sType = 6
fence_info.flags = 1
for i in range(image_count.value):
    vk_check(vkCreateFence(device, byref(fence_info), None, byref(fences[i])), "fence")

colors = [(1.0, 0.0, 0.0, "RED"), (0.0, 1.0, 0.0, "GREEN"), (0.0, 0.0, 1.0, "BLUE"), (1.0, 1.0, 0.0, "YELLOW"), (0.0, 1.0, 1.0, "CYAN"), (1.0, 0.0, 1.0, "MAGENTA"), (1.0, 1.0, 1.0, "WHITE")]
print("=== Colors ===")
for ci, (r, g, b, nm) in enumerate(colors):
    vkWaitForFences(device, 1, byref(fences[0]), True, 0xFFFFFFFFFFFFFFFF)
    vkResetFences(device, 1, byref(fences[0]))
    image_index = c_uint32()
    res = vkAcquireNextImageKHR(device, swapchain, 0xFFFFFFFFFFFFFFFF, image_available, 0, byref(image_index))
    if res != 0 and res != 1000001003:
        print("ERR acq", res)
        break
    print(ci, nm)
    cmd_begin = VkCommandBufferBeginInfo()
    cmd_begin.sType = 31
    vk_check(vkBeginCommandBuffer(cmd_buffers[image_index.value], byref(cmd_begin)), "begin")
    barrier = VkImageMemoryBarrier()
    barrier.sType = 7
    barrier.srcAccessMask = 0
    barrier.dstAccessMask = 4096
    barrier.oldLayout = 0
    barrier.newLayout = 6
    barrier.srcQueueFamilyIndex = 0xFFFFFFFF
    barrier.dstQueueFamilyIndex = 0xFFFFFFFF
    barrier.image = images[image_index.value]
    barrier.subresourceRange.aspectMask = 1
    barrier.subresourceRange.baseMipLevel = 0
    barrier.subresourceRange.levelCount = 1
    barrier.subresourceRange.baseArrayLayer = 0
    barrier.subresourceRange.layerCount = 1
    vkCmdPipelineBarrier(cmd_buffers[image_index.value], 1, 4096, 0, 0, None, 0, None, 1, byref(barrier))
    clear_color = VkClearColorValue()
    clear_color.float32[0] = r
    clear_color.float32[1] = g
    clear_color.float32[2] = b
    clear_color.float32[3] = 1.0
    range_struct = VkImageSubresourceRange()
    range_struct.aspectMask = 1
    range_struct.baseMipLevel = 0
    range_struct.levelCount = 1
    range_struct.baseArrayLayer = 0
    range_struct.layerCount = 1
    vkCmdClearColorImage(cmd_buffers[image_index.value], images[image_index.value], 6, byref(clear_color), 1, byref(range_struct))
    barrier.srcAccessMask = 4096
    barrier.dstAccessMask = 0
    barrier.oldLayout = 6
    barrier.newLayout = 1000001002
    vkCmdPipelineBarrier(cmd_buffers[image_index.value], 4096, 4096, 0, 0, None, 0, None, 1, byref(barrier))
    vk_check(vkEndCommandBuffer(cmd_buffers[image_index.value]), "end")
    submit_info = VkSubmitInfo()
    submit_info.sType = 4
    submit_info.waitSemaphoreCount = 1
    submit_info.pWaitSemaphores = cast(byref(image_available), c_void_p).value
    wait_stage = c_uint32(4096)
    submit_info.pWaitDstStageMask = cast(byref(wait_stage), c_void_p).value
    submit_info.commandBufferCount = 1
    submit_info.pCommandBuffers = cast(byref(cmd_buffers[image_index.value]), c_void_p).value
    submit_info.signalSemaphoreCount = 1
    submit_info.pSignalSemaphores = cast(byref(render_finished), c_void_p).value
    vk_check(vkQueueSubmit(queue, 1, byref(submit_info), fences[image_index.value]), "sub")
    present_info = VkPresentInfoKHR()
    present_info.sType = 1000001001
    present_info.swapchainCount = 1
    present_info.pSwapchains = cast(byref(swapchain), c_void_p).value
    present_info.pImageIndices = cast(byref(image_index), c_void_p).value
    res = vkQueuePresentKHR(queue, byref(present_info))
    if res != 0 and res != 1000001003:
        print("ERR pres", res)
        break
    time.sleep(1.0)

print("=== Done ===")
vkDeviceWaitIdle(device)
for i in range(image_count.value):
    vkDestroyImageView(device, image_views[i], None)
vkDestroySwapchainKHR(device, swapchain, None)
vkDestroyCommandPool(device, cmd_pool, None)
vkDestroySemaphore(device, image_available, None)
vkDestroySemaphore(device, render_finished, None)
for i in range(image_count.value):
    vkDestroyFence(device, fences[i], None)
vkDestroyDevice(device, None)
vkDestroySurfaceKHR(instance, surface, None)
vkDestroyInstance(instance, None)
xcb_destroy_window(conn, window)
xcb_disconnect(conn)
print("Exit")
