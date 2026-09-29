# FristOneRR PanVK Source

Full source code of the **FristOneRR PanVK driver**: Mesa PanVK running on Arm's vendor
**kbase** (Job Manager) kernel driver for Mali GPUs on Android.

Driver releases, the compatibility list and install guide are here:
**[FristOneRR/FristOneRR-Panvk-Driver](https://github.com/FristOneRR/FristOneRR-Panvk-Driver)**

---

## A note on credits

This is my first project on GitHub, and I made a mistake. When I released beta 1.0.0 I didn't
credit everyone whose work ended up in the driver. I'm sorry, especially to **Noysz**,
**mexicanbr0auth** and **LukeValen**.

During three months of development I studied and tested other PanVK/kbase projects, and some
of their code ended up in my source tree. My working copy was also overwritten from other
repositories a few times by mistake. I didn't track where each change came from, so the first
release gave the wrong impression that everything was my own work.

To fix this, I'm publishing the full source together with a script that anyone can run to see
which lines match other projects:

| Project | Lines | Where in our code |
|---|---:|---|
| [mexicanbr0auth/mesa-panvk-g57](https://github.com/mexicanbr0auth/mesa-panvk-g57) | 60 (3.6 %) | v9 draw path `jm/panvk_vX_cmd_draw.c` (35), `kbase_kmod.c` (12), `jm/panvk_vX_cmd_dispatch.c` (6), others (7) |
| [Noysz/panvk-g99-jm](https://github.com/Noysz/panvk-g99-jm) | 40 (2.4 %) | v9 draw path `jm/panvk_vX_cmd_draw.c` (15), `kbase_kmod.c` (9), `jm/panvk_vX_cmd_dispatch.c` (7), `libpan/draw_helper.cl` (6), others (3) |
| [0x8055/panvk-g52-oppo-a38](https://github.com/0x8055/panvk-g52-oppo-a38) (LukeValen) | 11 (0.7 %) | `kbase_kmod.c` (11) |

Most of the matches in `kbase_kmod.c` are kbase interface definitions (for example
`struct base_jd_event_v2` and `BASE_JD_EVENT_DONE`) that every kbase project copies from Arm's
kernel headers, plus a few generic lines. The matches in the **draw and dispatch code** are the
part that most likely came from these projects.

About two-thirds of the lines I added (1,119 of 1,669) don't appear in the base or in any of
these projects. The rest belongs to the people above and to the Mesa developers, and they are
now credited properly. If you find anything else I missed, please open an issue and I'll fix it.

— FristOneRR

---

## Why this repository is public

This source is published to show where every part of the driver comes from, and to give
credit to everyone whose work it builds on. The full git history is included. You can
check every change we made against the original base yourself.

---

## Base

| | |
|---|---|
| Upstream | Mesa (PanVK), MIT license |
| Direct base | [funnymdzz/mesa](https://github.com/funnymdzz/mesa) `main` @ `6598829019c0746aa8e473b4ae1c980cbfa6ea4b` |
| Our work | Everything that differs from that commit |

**About the first commit:** this repository's history starts with an import commit
("Working baseline"). It contains the funnymdzz base **together with** our early work, so the
author name on that commit does **not** mean we wrote Mesa. To see exactly what we changed,
compare against the base commit in the original repository (below).

Result at release 1.1.0: **76 files changed, 3,615 lines added, 350 lines removed** (driver source only; this README and `tools/fristonerr/` are not counted).

---

## Code origin

We took every line **we added on top of the base** (25+ characters and not comment-only, so
short boilerplate like `}` or `break;` doesn't count) and checked whether it also appears in the
base itself or in other public PanVK/kbase projects.

| Where the line also appears | Lines | Share |
|---|---:|---:|
| **Total lines added by us** | **1,669** | **100 %** |
| Elsewhere in the funnymdzz base (code we moved or reused) | 468 | 28.0 % |
| [mexicanbr0auth/mesa-panvk-g57](https://github.com/mexicanbr0auth/mesa-panvk-g57) | 60 | 3.6 % |
| [Noysz/panvk-g99-jm](https://github.com/Noysz/panvk-g99-jm) | 40 | 2.4 % |
| [0x8055/panvk-g52-oppo-a38](https://github.com/0x8055/panvk-g52-oppo-a38) (LukeValen) | 11 | 0.7 % |
| [Vtgamer998/PanVK-v9-Driver](https://github.com/Vtgamer998/PanVK-v9-Driver) | 0 | 0.0 % |
| MESA-KMOD (Vtgamer998) ¹ | — | ≈ 4.5 % |
| **Not found in the base or in any project above** | **1,119** | **67.0 %** |

Measured on 2026-09-29 at release 1.1.0.

¹ MESA-KMOD is not in the script because we don't have a public link to it. The ≈ 4.5 % comes from an earlier manual check on 2026-09-28 and is shown so nothing is left out.

What the numbers mean:
- **mexicanbr0auth:** our source was never public before this release, so these lines most likely came **from** that project into ours during development. They are credited below.
- **Noysz:** we used panvk-g99-jm as a reference for the Valhall v9 draw path.
- **Base (28 %):** lines that already exist somewhere in Mesa/funnymdzz. We reused or moved them; they are not new code.
- A line can appear in more than one project, so the rows don't add up exactly to the total.

### How to check it yourself

```sh
git clone https://github.com/FristOneRR-Admin/FristOneRR-Panvk-Source
cd FristOneRR-Panvk-Source
BASE=6598829019c0746aa8e473b4ae1c980cbfa6ea4b
git fetch --depth=1 https://github.com/funnymdzz/mesa.git $BASE   # the original base
git diff --stat $BASE HEAD -- . ':!.github' ':!tools/fristonerr'    # every file we changed
git diff $BASE HEAD -- src/panfrost/                                # our driver changes
python3 tools/fristonerr/code_origin.py                             # re-run the table above
```

---

## Main changes on top of the base

- kbase Job Manager backend: atom submission, event handling, sync objects, GPU cold-start handling
- Automatic JOB_SUBMIT atom-stride detection (64 / 56 bytes)
- Valhall v9 draw path: IDVS varying stage, vertex+tiler job requirements, occlusion queries
- Hang, flicker and performance fixes (atom event race, vtc→frag dependency)
- DXVK support: robustness2 / nullDescriptor on v9, extension and feature fixes
- GPU model table: G52 r1 lookup, G68, G77, G78
- Lower RAM use (smaller libpoly heap)

---

## Building (Termux, Android)

The exact options used for the releases are in
[`tools/fristonerr/build-options.txt`](tools/fristonerr/build-options.txt); the cross file is
[`android-cross.txt`](android-cross.txt). It expects a host build of `mesa_clc` in `build-host/` (the path in the file is the default Termux home, `/data/data/com.termux/files/home/mesa`).

```sh
meson setup build-android-final --cross-file android-cross.txt $(cat tools/fristonerr/build-options.txt)
ninja -C build-android-final
# output: build-android-final/src/panfrost/vulkan/libvulkan_panfrost.so
```

---

## Credits

| Who | Contribution |
|---|---|
| **Mesa / PanVK developers** (Collabora, Arm and contributors) | PanVK itself |
| **funnymdzz** & **leegao** | The Mesa fork we started from; bionic Vulkan wrapper; advice |
| **Noysz** / [panvk-g99-jm](https://github.com/Noysz/panvk-g99-jm) | Valhall v9 / Job Manager groundwork (in the base); reference for the v9 draw path |
| **Vtgamer998** (MESA-KMOD) | kbase kernel-interface work (see note ¹ under the table) |
| **mexicanbr0auth** / [mesa-panvk-g57](https://github.com/mexicanbr0auth/mesa-panvk-g57) | PanVK/kbase work for Mali-G57. Parts of our code match this project and most likely came from it during development (see table) |
| **LukeValen** / [0x8055/panvk-g52-oppo-a38](https://github.com/0x8055/panvk-g52-oppo-a38) | Mali-G52 research |
| **BossDrk** | Mali-G52 testing (stride fix) |
| **Claude** (AI assistant by Anthropic) | Development help, debugging and code review; audited the code origin and helped write this credit list |
| **Community testers** | Device reports and logs via Issues |

## License

MIT (same as Mesa). See the license headers in each file.
