#!/usr/bin/env python3
"""Code-origin check for the FristOneRR PanVK source.

Takes every line we added on top of the base (funnymdzz/mesa @ BASE),
keeps lines of 25+ characters that are not comment-only, and checks
whether each line also appears in other public PanVK/kbase projects.

Anyone can run it and get the same numbers:
    python3 tools/fristonerr/code_origin.py
(requires git and network access; the base commit must be fetchable)
"""
import collections
import os
import re
import subprocess
import sys

BASE = "6598829019c0746aa8e473b4ae1c980cbfa6ea4b"
BASE_URL = "https://github.com/funnymdzz/mesa.git"
MIN_LEN = 25

# name -> (git url, sparse paths or None for a full shallow clone)
PROJECTS = {
    "Noysz/panvk-g99-jm": ("https://github.com/Noysz/panvk-g99-jm.git", None),
    "mexicanbr0auth/mesa-panvk-g57": (
        "https://github.com/mexicanbr0auth/mesa-panvk-g57.git",
        ["src/panfrost", "src/vulkan", "include"]),
    "Vtgamer998/PanVK-v9-Driver": (
        "https://github.com/Vtgamer998/PanVK-v9-Driver.git",
        ["src/panfrost", "src/vulkan", "include", "patches"]),
    "0x8055/panvk-g52-oppo-a38 (LukeValen)": (
        "https://github.com/0x8055/panvk-g52-oppo-a38.git", None),
}

TEXT_EXT = (".c", ".h", ".cpp", ".hpp", ".py", ".build", ".txt", ".patch",
            ".diff", ".md", ".sh", ".json", ".xml", ".inc")


def run(*args, **kw):
    return subprocess.run(args, capture_output=True, text=True,
                          errors="replace", **kw)


def norm(line):
    return re.sub(r"\s+", " ", line.strip())


def keep(line):
    return len(line) >= MIN_LEN and not line.startswith(("//", "/*", "*"))


def strip_diff_prefix(line):
    # lines inside .patch/.diff files start with +, - or space
    if line[:1] in "+- " and not line.startswith(("+++", "---")):
        return line[1:]
    return line


def our_added_lines(repo):
    out = run("git", "-C", repo, "diff", BASE, "HEAD", "--", ".",
              ":!tools/fristonerr", ":!.github").stdout
    lines = []
    cur = "?"
    for l in out.splitlines():
        if l.startswith("+++ "):
            cur = l[6:] if l.startswith("+++ b/") else l[4:]
        elif l.startswith("+"):
            n = norm(l[1:])
            if keep(n):
                lines.append((cur, n))
    return lines


def base_line_set(repo):
    names = run("git", "-C", repo, "ls-tree", "-r", "--name-only",
                BASE).stdout.split("\n")
    names = [n for n in names if n.endswith(TEXT_EXT)]
    p = subprocess.Popen(["git", "-C", repo, "cat-file", "--batch"],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    data, _ = p.communicate("\n".join(f"{BASE}:{n}" for n in names).encode())
    s = set()
    for l in data.decode("utf-8", "replace").splitlines():
        n = norm(l)
        if keep(n):
            s.add(n)
    return s


def dir_line_set(path):
    s = set()
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d != ".git"]
        for f in files:
            if not f.endswith(TEXT_EXT):
                continue
            try:
                with open(os.path.join(root, f), errors="replace") as fh:
                    for l in fh:
                        n = norm(strip_diff_prefix(l.rstrip("\n")))
                        if keep(n):
                            s.add(n)
            except OSError:
                pass
    return s


def clone(name, url, sparse, dest):
    if os.path.isdir(dest):
        return True
    if sparse:
        r = run("git", "clone", "-q", "--depth=1", "--filter=blob:none",
                "--sparse", url, dest)
        if r.returncode == 0:
            run("git", "-C", dest, "sparse-checkout", "set", "--no-cone",
                *sparse)
    else:
        r = run("git", "clone", "-q", "--depth=1", url, dest)
    if r.returncode != 0:
        print(f"  ! could not clone {name}: {r.stderr.strip()[:200]}")
        return False
    return True


def main():
    repo = run("git", "rev-parse", "--show-toplevel").stdout.strip()
    if not repo:
        sys.exit("run this inside the source repository")
    if run("git", "-C", repo, "cat-file", "-e", BASE + "^{commit}").returncode:
        print("fetching base commit ...")
        run("git", "-C", repo, "fetch", "-q", "--depth=1", BASE_URL, BASE)

    head = run("git", "-C", repo, "rev-parse", "--short", "HEAD").stdout.strip()
    ours = our_added_lines(repo)
    base = base_line_set(repo)
    ours_new = [(f, l) for f, l in ours if l not in base]
    total = len(ours)

    work = os.path.join(os.environ.get("TMPDIR", "/tmp"), "code_origin")
    os.makedirs(work, exist_ok=True)

    print(f"base {BASE[:7]}  ->  HEAD {head}")
    print(f"lines added by us (>= {MIN_LEN} chars, not comment-only): {total}")
    print(f"  of which already exist elsewhere in the base (moved/common code): "
          f"{total - len(ours_new)}")
    print()

    found_any = set()
    rows = []
    details = {}
    samples = {}
    for name, (url, sparse) in PROJECTS.items():
        dest = os.path.join(work, re.sub(r"[^A-Za-z0-9]+", "_", name))
        if not clone(name, url, sparse, dest):
            rows.append((name, None))
            continue
        other = dir_line_set(dest)
        hits = [i for i, (f, l) in enumerate(ours_new) if l in other]
        found_any.update(hits)
        rows.append((name, len(hits)))
        details[name] = collections.Counter(ours_new[i][0] for i in hits)
        samples[name] = [ours_new[i] for i in hits[:3]]

    print(f"{'Project':45s} {'shared':>7s} {'share':>7s}")
    for name, n in rows:
        if n is None:
            print(f"{name:45s} {'n/a':>7s}")
        else:
            print(f"{name:45s} {n:7d} {100.0 * n / total:6.1f}%")
    only = total - (total - len(ours_new)) - len(found_any)
    print(f"{'Not found in the base or any project above':45s} {only:7d} "
          f"{100.0 * only / total:6.1f}%")

    if "--detail" in sys.argv:
        for name, cnt in details.items():
            if not cnt:
                continue
            print(f"\n== {name}: shared lines by file")
            for f, n in cnt.most_common():
                print(f"  {n:4d}  {f}")
            for f, l in samples[name]:
                print(f"  e.g. {f}: {l[:90]}")


if __name__ == "__main__":
    main()
