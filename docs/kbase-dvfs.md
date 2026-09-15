# PanVK kbase DVFS control

Proprietary Android kbase drivers do not expose GPU frequency control through
the Vulkan API.  On kernels which provide the Mali private sysfs frequency
interface, the kbase PanVK backend can configure it during device discovery.

Set `PANVK_KBASE_DVFS` before starting a Vulkan application:

- `auto`: select `quickstep_use_mcu` (or `capacity_use_mcu` as a fallback) and
  retain the full frequency range.
- `max`: fix the GPU at the highest frequency advertised by the kernel.
- `default`: select the kernel's `quickstep` governor and retain the full
  frequency range.
- A decimal number, such as `572000`: fix the GPU at that frequency in kHz.
- `none`, or leaving the variable unset: do not modify GPU DVFS settings.

For example:

```sh
PANVK_KBASE_DVFS=auto vkcube
PANVK_KBASE_DVFS=848000 vkmark
```

The setting is global to the Mali device, not private to the Vulkan process.
Writing the sysfs controls normally requires root or adjusted file
permissions.  If the controls are unavailable or not writable, PanVK logs a
warning and continues device initialization without changing DVFS.
