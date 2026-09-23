#!/usr/bin/env python3
import os, sys, time
from ctypes import *

# ต้องตั้ง environment variable นี้ก่อนโหลด Vulkan
os.environ["PAN_I_WANT_A_BROKEN_VULKAN_DRIVER"] = "1"

VK_STRUCTURE_TYPE_APPLICATION_INFO = 0
VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO = 1
VK_STRUCTURE_TYPE_XCB_SURFACE_CREATE_INFO_KHR = 1000009000
VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO = 3
VK_STRUCTURE_TYPE_SWAPCHAIN_CREATE_INFO_KHR = 1000001000
VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO = 10
VK_STRUCTURE_TYPE_SEMAPHORE_CREATE_INFO = 5
VK_STRUCTURE_TYPE_FENCE_CREATE_INFO = 6
VK_STRUCTURE_TYPE_PRESENT_INFO_KHR = 1000001001
VK_API_VERSION_1_0 = (1 << 22)
VK_QUEUE_GRAPHICS_BIT = 1
VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT = 16
VK_SHARING_MODE_EXCLUSIVE = 0
VK_COMPOSITE_ALPHA_OPAQUE_BIT_KHR = 16
VK_PRESENT_MODE_FIFO_KHR = 0
VK_FENCE_CREATE_SIGNALED_BIT = 1
VK_IMAGE_VIEW_TYPE_2D = 1
VK_IMAGE_ASPECT_COLOR_BIT = 1
VK_SUCCESS = 0
VK_SUBOPTIMAL_KHR = 1000001003
VK_NULL_HANDLE = 0
VK_KHR_SURFACE = "VK_KHR_surface"
VK_KHR_XCB_SURFACE = "VK_KHR_xcb_surface"
VK_KHR_SWAPCHAIN = "VK_KHR_swapchain"

VkInstance = c_void_p
VkPhysicalDevice = c_void_p
VkDevice = c_void_p
VkQueue = c_void_p
VkSurfaceKHR = c_uint64
VkSwapchainKHR = c_uint64
VkImage = c_uint64
VkImageView = c_uint64
VkSemaphore = c_uint64
VkFence = c_uint64
VkResult = c_int
VkBool32 = c_uint32

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

class VkSemaphoreCreateInfo(Structure):
    _fields_ = [("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32)]

class VkFenceCreateInfo(Structure):
    _fields_ = [("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32)]

class VkPresentInfoKHR(Structure):
    _fields_ = [("sType", c_uint32), ("pNext", c_void_p), ("waitSemaphoreCount", c_uint32), ("pWaitSemaphores", c_void_p), ("swapchainCount", c_uint32), ("pSwapchains", c_void_p), ("pImageIndices", c_void_p), ("pResults", c_void_p)]

print("Loading libraries...")
try:
    vk = CDLL("libvulkan.so.1")
    xcb = CDLL("libxcb.so.1")
    print("OK")
except Exception as e:
    print("FAIL:", e)
    sys.exit(1)

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
vkCreateInstance.restype = VkResult
vkEnumeratePhysicalDevices = vk.vkEnumeratePhysicalDevices
vkEnumeratePhysicalDevices.argtypes = [VkInstance, POINTER(c_uint32), POINTER(VkPhysicalDevice)]
vkEnumeratePhysicalDevices.restype = VkResult
vkGetPhysicalDeviceQueueFamilyProperties = vk.vkGetPhysicalDeviceQueueFamilyProperties
vkGetPhysicalDeviceQueueFamilyProperties.argtypes = [VkPhysicalDevice, POINTER(c_uint32), POINTER(VkQueueFamilyProperties)]
vkGetPhysicalDeviceSurfaceSupportKHR = vk.vkGetPhysicalDeviceSurfaceSupportKHR
vkGetPhysicalDeviceSurfaceSupportKHR.argtypes = [VkPhysicalDevice, c_uint32, VkSurfaceKHR, POINTER(VkBool32)]
vkGetPhysicalDeviceSurfaceSupportKHR.restype = VkResult
vkCreateDevice = vk.vkCreateDevice
vkCreateDevice.argtypes = [VkPhysicalDevice, POINTER(VkDeviceCreateInfo), c_void_p, POINTER(VkDevice)]
vkCreateDevice.restype = VkResult
vkGetDeviceQueue = vk.vkGetDeviceQueue
vkGetDeviceQueue.argtypes = [VkDevice, c_uint32, c_uint32, POINTER(VkQueue)]
vkGetPhysicalDeviceSurfaceCapabilitiesKHR = vk.vkGetPhysicalDeviceSurfaceCapabilitiesKHR
vkGetPhysicalDeviceSurfaceCapabilitiesKHR.argtypes = [VkPhysicalDevice, VkSurfaceKHR, POINTER(VkSurfaceCapabilitiesKHR)]
vkGetPhysicalDeviceSurfaceCapabilitiesKHR.restype = VkResult
vkGetPhysicalDeviceSurfaceFormatsKHR = vk.vkGetPhysicalDeviceSurfaceFormatsKHR
vkGetPhysicalDeviceSurfaceFormatsKHR.argtypes = [VkPhysicalDevice, VkSurfaceKHR, POINTER(c_uint32), POINTER(VkSurfaceFormatKHR)]
vkGetPhysicalDeviceSurfaceFormatsKHR.restype = VkResult
vkCreateSwapchainKHR = vk.vkCreateSwapchainKHR
vkCreateSwapchainKHR.argtypes = [VkDevice, POINTER(VkSwapchainCreateInfoKHR), c_void_p, POINTER(VkSwapchainKHR)]
vkCreateSwapchainKHR.restype = VkResult
vkGetSwapchainImagesKHR = vk.vkGetSwapchainImagesKHR
vkGetSwapchainImagesKHR.argtypes = [VkDevice, VkSwapchainKHR, POINTER(c_uint32), POINTER(VkImage)]
vkGetSwapchainImagesKHR.restype = VkResult
vkCreateImageView = vk.vkCreateImageView
vkCreateImageView.argtypes = [VkDevice, POINTER(VkImageViewCreateInfo), c_void_p, POINTER(VkImageView)]
vkCreateImageView.restype = VkResult
vkCreateSemaphore = vk.vkCreateSemaphore
vkCreateSemaphore.argtypes = [VkDevice, POINTER(VkSemaphoreCreateInfo), c_void_p, POINTER(VkSemaphore)]
vkCreateSemaphore.restype = VkResult
vkCreateFence = vk.vkCreateFence
vkCreateFence.argtypes = [VkDevice, POINTER(VkFenceCreateInfo), c_void_p, POINTER(VkFence)]
vkCreateFence.restype = VkResult
vkWaitForFences = vk.vkWaitForFences
vkWaitForFences.argtypes = [VkDevice, c_uint32, POINTER(VkFence), c_bool, c_uint64]
vkWaitForFences.restype = VkResult
vkResetFences = vk.vkResetFences
vkResetFences.argtypes = [VkDevice, c_uint32, POINTER(VkFence)]
vkResetFences.restype = VkResult
vkAcquireNextImageKHR = vk.vkAcquireNextImageKHR
vkAcquireNextImageKHR.argtypes = [VkDevice, VkSwapchainKHR, c_uint64, VkSemaphore, VkFence, POINTER(c_uint32)]
vkAcquireNextImageKHR.restype = VkResult
vkQueuePresentKHR = vk.vkQueuePresentKHR
vkQueuePresentKHR.argtypes = [VkQueue, POINTER(VkPresentInfoKHR)]
vkQueuePresentKHR.restype = VkResult
vkDestroyImageView = vk.vkDestroyImageView
vkDestroyImageView.argtypes = [VkDevice, VkImageView, c_void_p]
vkDestroySwapchainKHR = vk.vkDestroySwapchainKHR
vkDestroySwapchainKHR.argtypes = [VkDevice, VkSwapchainKHR, c_void_p]
vkDestroySemaphore = vk.vkDestroySemaphore
vkDestroySemaphore.argtypes = [VkDevice, VkSemaphore, c_void_p]
vkDestroyFence = vk.vkDestroyFence
vkDestroyFence.argtypes = [VkDevice, VkFence, c_void_p]
vkDestroyDevice = vk.vkDestroyDevice
vkDestroyDevice.argtypes = [VkDevice, c_void_p]
vkDeviceWaitIdle = vk.vkDeviceWaitIdle
vkDeviceWaitIdle.argtypes = [VkDevice]
vkDeviceWaitIdle.restype = VkResult
vkDestroySurfaceKHR = vk.vkDestroySurfaceKHR
vkDestroySurfaceKHR.argtypes = [VkInstance, VkSurfaceKHR, c_void_p]
vkDestroyInstance = vk.vkDestroyInstance
vkDestroyInstance.argtypes = [VkInstance, c_void_p]
vkCreateXcbSurfaceKHR = vk.vkCreateXcbSurfaceKHR
vkCreateXcbSurfaceKHR.argtypes = [VkInstance, POINTER(VkXcbSurfaceCreateInfoKHR), c_void_p, POINTER(VkSurfaceKHR)]
vkCreateXcbSurfaceKHR.restype = VkResult

def vk_check(result, msg):
    if result != VK_SUCCESS and result != VK_SUBOPTIMAL_KHR:
        print("ERROR:", msg, "=", result)
        sys.exit(1)

print("=== Vulkan WSI Present Test (panvk) ===")
print("DISPLAY =", os.environ.get("DISPLAY", ":0"))
print("VK_ICD =", os.environ.get("VK_ICD_FILENAMES", ""))
print("PAN_I_WANT_A_BROKEN_VULKAN_DRIVER =", os.environ.get("PAN_I_WANT_A_BROKEN_VULKAN_DRIVER", ""))

print("[1] Creating XCB window...")
conn = xcb_connect(None, None)
if not conn:
    print("ERROR: Cannot connect to X server")
    sys.exit(1)
print("OK: Connected")

screen_ptr = xcb_setup_roots_iterator(xcb_get_setup(conn))
Screen = type("Screen", (Structure,), {"_fields_": [("root", c_uint32), ("default_colormap", c_uint32), ("white_pixel", c_uint32), ("black_pixel", c_uint32), ("current_input_masks", c_uint32), ("width_in_pixels", c_uint16), ("height_in_pixels", c_uint16), ("width_in_millimeters", c_uint16), ("height_in_millimeters", c_uint16), ("min_installed_maps", c_uint16), ("max_installed_maps", c_uint16), ("root_visual", c_uint32), ("backing_stores", c_uint8), ("save_unders", c_uint8), ("root_depth", c_uint8), ("allowed_depths_len", c_uint8)]})
screen = cast(screen_ptr, POINTER(Screen)).contents

window = xcb_generate_id(conn)
values = (c_uint32 * 1)(screen.white_pixel)
xcb_create_window(conn, 0, window, screen.root, 100, 100, 640, 480, 0, 0, screen.root_visual, 2, values)
xcb_map_window(conn, window)
xcb_flush(conn)
print("OK: Window", window, "(640x480)")

print("[2] Creating Vulkan instance...")
app_info = VkApplicationInfo()
app_info.sType = VK_STRUCTURE_TYPE_APPLICATION_INFO
app_info.pApplicationName = b"Test"
app_info.apiVersion = VK_API_VERSION_1_0

exts = (c_char_p * 2)()
exts[0] = VK_KHR_SURFACE.encode()
exts[1] = VK_KHR_XCB_SURFACE.encode()

inst_info = VkInstanceCreateInfo()
inst_info.sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO
inst_info.pApplicationInfo = cast(byref(app_info), c_void_p).value
inst_info.enabledExtensionCount = 2
inst_info.ppEnabledExtensionNames = exts

instance = VkInstance()
vk_check(vkCreateInstance(byref(inst_info), None, byref(instance)), "vkCreateInstance")
print("OK")

print("[3] Creating XCB surface...")
surface_info = VkXcbSurfaceCreateInfoKHR()
surface_info.sType = VK_STRUCTURE_TYPE_XCB_SURFACE_CREATE_INFO_KHR
surface_info.connection = conn
surface_info.window = window

surface = VkSurfaceKHR()
vk_check(vkCreateXcbSurfaceKHR(instance, byref(surface_info), None, byref(surface)), "vkCreateXcbSurfaceKHR")
print("OK:", surface)

print("[4] Enumerating physical devices...")
device_count = c_uint32()
vk_check(vkEnumeratePhysicalDevices(instance, byref(device_count), None), "vkEnumeratePhysicalDevices")
print("Found:", device_count.value)
if device_count.value == 0:
    print("ERROR: No Vulkan devices")
    sys.exit(1)

phys_dev = VkPhysicalDevice()
vk_check(vkEnumeratePhysicalDevices(instance, byref(device_count), byref(phys_dev)), "vkEnumeratePhysicalDevices")

print("[5] Finding queue family...")
queue_family_count = c_uint32()
vkGetPhysicalDeviceQueueFamilyProperties(phys_dev, byref(queue_family_count), None)
queue_families = (VkQueueFamilyProperties * queue_family_count.value)()
vkGetPhysicalDeviceQueueFamilyProperties(phys_dev, byref(queue_family_count), queue_families)

queue_family_index = 0xFFFFFFFF
for i in range(queue_family_count.value):
    present_support = VkBool32()
    vkGetPhysicalDeviceSurfaceSupportKHR(phys_dev, i, surface, byref(present_support))
    if (queue_families[i].queueFlags & VK_QUEUE_GRAPHICS_BIT) and present_support.value:
        queue_family_index = i
        print("OK: Queue family", i)
        break

if queue_family_index == 0xFFFFFFFF:
    print("ERROR: No suitable queue family")
    sys.exit(1)

print("[6] Creating logical device...")
queue_priority = (c_float * 1)(1.0)
queue_info = VkDeviceQueueCreateInfo()
queue_info.sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO
queue_info.queueFamilyIndex = queue_family_index
queue_info.queueCount = 1
queue_info.pQueuePriorities = queue_priority

dev_exts = (c_char_p * 1)()
dev_exts[0] = VK_KHR_SWAPCHAIN.encode()

dev_info = VkDeviceCreateInfo()
dev_info.sType = VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO
dev_info.queueCreateInfoCount = 1
dev_info.pQueueCreateInfos = cast(byref(queue_info), c_void_p).value
dev_info.enabledExtensionCount = 1
dev_info.ppEnabledExtensionNames = dev_exts

device = VkDevice()
vk_check(vkCreateDevice(phys_dev, byref(dev_info), None, byref(device)), "vkCreateDevice")
print("OK")

queue = VkQueue()
vkGetDeviceQueue(device, queue_family_index, 0, byref(queue))

print("[7] Creating swapchain...")
caps = VkSurfaceCapabilitiesKHR()
vk_check(vkGetPhysicalDeviceSurfaceCapabilitiesKHR(phys_dev, surface, byref(caps)), "vkGetSurfaceCapabilities")

format_count = c_uint32()
vk_check(vkGetPhysicalDeviceSurfaceFormatsKHR(phys_dev, surface, byref(format_count), None), "vkGetSurfaceFormats")
formats = (VkSurfaceFormatKHR * format_count.value)()
vk_check(vkGetPhysicalDeviceSurfaceFormatsKHR(phys_dev, surface, byref(format_count), formats), "vkGetSurfaceFormats")

print("Extent:", caps.currentExtent[0], "x", caps.currentExtent[1])
print("Formats:", format_count.value)

swap_info = VkSwapchainCreateInfoKHR()
swap_info.sType = VK_STRUCTURE_TYPE_SWAPCHAIN_CREATE_INFO_KHR
swap_info.surface = surface
swap_info.minImageCount = caps.minImageCount + 1
swap_info.imageFormat = formats[0].format
swap_info.imageColorSpace = formats[0].colorSpace
swap_info.imageExtent[0] = caps.currentExtent[0]
swap_info.imageExtent[1] = caps.currentExtent[1]
swap_info.imageArrayLayers = 1
swap_info.imageUsage = VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT
swap_info.imageSharingMode = VK_SHARING_MODE_EXCLUSIVE
swap_info.preTransform = caps.currentTransform
swap_info.compositeAlpha = VK_COMPOSITE_ALPHA_OPAQUE_BIT_KHR
swap_info.presentMode = VK_PRESENT_MODE_FIFO_KHR
swap_info.clipped = True

swapchain = VkSwapchainKHR()
vk_check(vkCreateSwapchainKHR(device, byref(swap_info), None, byref(swapchain)), "vkCreateSwapchainKHR")
print("OK")

print("[8] Getting swapchain images...")
image_count = c_uint32()
vk_check(vkGetSwapchainImagesKHR(device, swapchain, byref(image_count), None), "vkGetSwapchainImages")
images = (VkImage * image_count.value)()
vk_check(vkGetSwapchainImagesKHR(device, swapchain, byref(image_count), images), "vkGetSwapchainImages")
print("OK:", image_count.value, "images")

print("[9] Creating image views...")
image_views = (VkImageView * image_count.value)()
for i in range(image_count.value):
    view_info = VkImageViewCreateInfo()
    view_info.sType = VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO
    view_info.image = images[i]
    view_info.viewType = VK_IMAGE_VIEW_TYPE_2D
    view_info.format = formats[0].format
    view_info.subresourceRange[0] = VK_IMAGE_ASPECT_COLOR_BIT
    view_info.subresourceRange[1] = 0
    view_info.subresourceRange[2] = 1
    view_info.subresourceRange[3] = 0
    view_info.subresourceRange[4] = 1
    vk_check(vkCreateImageView(device, byref(view_info), None, byref(image_views[i])), "vkCreateImageView")
print("OK")

print("[10] Creating sync objects...")
semaphore_info = VkSemaphoreCreateInfo()
semaphore_info.sType = VK_STRUCTURE_TYPE_SEMAPHORE_CREATE_INFO

image_available = VkSemaphore()
render_finished = VkSemaphore()
vk_check(vkCreateSemaphore(device, byref(semaphore_info), None, byref(image_available)), "vkCreateSemaphore")
vk_check(vkCreateSemaphore(device, byref(semaphore_info), None, byref(render_finished)), "vkCreateSemaphore")

fences = (VkFence * image_count.value)()
fence_info = VkFenceCreateInfo()
fence_info.sType = VK_STRUCTURE_TYPE_FENCE_CREATE_INFO
fence_info.flags = VK_FENCE_CREATE_SIGNALED_BIT
for i in range(image_count.value):
    vk_check(vkCreateFence(device, byref(fence_info), None, byref(fences[i])), "vkCreateFence")
print("OK")

print("[11] Present loop (5 frames)...")
for frame in range(5):
    vkWaitForFences(device, 1, byref(fences[0]), True, 0xFFFFFFFFFFFFFFFF)
    vkResetFences(device, 1, byref(fences[0]))
    
    image_index = c_uint32()
    result = vkAcquireNextImageKHR(device, swapchain, 0xFFFFFFFFFFFFFFFF, image_available, VK_NULL_HANDLE, byref(image_index))
    
    if result == VK_SUBOPTIMAL_KHR:
        print("Frame", frame, ": SUBOPTIMAL")
    else:
        vk_check(result, "vkAcquireNextImageKHR")
        print("Frame", frame, ": Acquired", image_index.value)
    
    present_info = VkPresentInfoKHR()
    present_info.sType = VK_STRUCTURE_TYPE_PRESENT_INFO_KHR
    present_info.swapchainCount = 1
    present_info.pSwapchains = cast(byref(swapchain), c_void_p).value
    present_info.pImageIndices = cast(byref(image_index), c_void_p).value
    
    result = vkQueuePresentKHR(queue, byref(present_info))
    if result == VK_SUBOPTIMAL_KHR:
        print("Frame", frame, ": SUBOPTIMAL")
    else:
        vk_check(result, "vkQueuePresentKHR")
        print("Frame", frame, ": OK")
    
    time.sleep(0.5)

print("=== SUCCESS ===")
print("Window should appear on X11 display")

print("Cleaning up...")
vkDeviceWaitIdle(device)
for i in range(image_count.value):
    vkDestroyImageView(device, image_views[i], None)
vkDestroySwapchainKHR(device, swapchain, None)
vkDestroySemaphore(device, image_available, None)
vkDestroySemaphore(device, render_finished, None)
for i in range(image_count.value):
    vkDestroyFence(device, fences[i], None)
vkDestroyDevice(device, None)
vkDestroySurfaceKHR(instance, surface, None)
vkDestroyInstance(instance, None)
xcb_destroy_window(conn, window)
xcb_disconnect(conn)
print("Done")
