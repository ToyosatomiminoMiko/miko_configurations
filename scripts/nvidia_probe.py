#!/usr/bin/env python3
"""列出 NVIDIA 内核态驱动与用户态驱动/工具链的版本信息（单文件，仅标准库）。

用法: python3 nvidia_probe.py
在任何 Linux / Windows 机器上运行都不会抛异常，摸不到的东西直接标 "-"。

作者: DSH agent  时间: 2026-11-22
"""

import ctypes
import glob
import os
import re
import shutil
import subprocess

# 找用户态 .so 的候选目录，Linux 各发行版布局不同，全扫一遍再按版本取最高
LIB_DIRS = [
    "/usr/lib64", "/usr/lib/x86_64-linux-gnu", "/usr/lib/aarch64-linux-gnu",
    "/usr/lib", "/lib64", "/lib", "/usr/local/lib",
    "/usr/lib64/nvidia", "/usr/lib/nvidia",
]
LIB_DIRS += glob.glob("/usr/local/cuda*/lib64")
LIB_DIRS += glob.glob("/usr/local/cuda*/targets/*/lib")
LIB_DIRS += [p for p in os.environ.get("LD_LIBRARY_PATH", "").split(":") if p]

# 组件名 -> 文件名通配符；driver 段是驱动用户态，tool 段是 CUDA 工具链
DRIVER_LIBS = [
    ("libcuda", "libcuda.so*"),
    ("libnvidia-ml", "libnvidia-ml.so*"),
    ("libnvidia-glcore", "libnvidia-glcore.so*"),
    ("libnvidia-eglcore", "libnvidia-eglcore.so*"),
    ("libnvidia-nvvm", "libnvidia-nvvm.so*"),
    ("libnvidia-ptxjitcompiler", "libnvidia-ptxjitcompiler.so*"),
    ("libnvidia-encode", "libnvidia-encode.so*"),
    ("libnvidia-decode", "libnvidia-decode.so*"),
    ("libnvidia-allocator", "libnvidia-allocator.so*"),
]
SHOW_PATH = {"libcuda"}

VER_RE = re.compile(r"(\d+\.\d+(?:\.\d+)?)")
DASH = "-"


def run(cmd, timeout=8):
    """执行外部命令，失败/超时/不存在一律返回空串，保证脚本不炸。"""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return ""
    return p.stdout.strip() if p.returncode == 0 else ""


def ver_key(v):
    return tuple(int(x) for x in v.split(".")) if v else ()


def best_lib(pattern):
    """在候选目录里找匹配文件，取文件名版本号最高的那个，返回 (版本, 路径)。"""
    hits = []
    for d in dict.fromkeys(LIB_DIRS):
        for p in glob.glob(os.path.join(d, pattern)):
            real = os.path.realpath(p)
            if not os.path.exists(real):
                continue
            m = VER_RE.search(os.path.basename(real))
            hits.append((m.group(1) if m else "", real))
    if not hits:
        return None
    hits.sort(key=lambda h: ver_key(h[0]), reverse=True)
    return hits[0]


def cuda_api_version():
    """调 cuDriverGetVersion 拿驱动支持的 CUDA 版本，不依赖 nvidia-smi。"""
    for name in ("libcuda.so.1", "libcuda.so", "nvcuda.dll"):
        try:
            lib = ctypes.CDLL(name)
            v = ctypes.c_int(0)
            if lib.cuDriverGetVersion(ctypes.byref(v)) == 0 and v.value:
                return f"{v.value // 1000}.{(v.value % 1000) // 10}"
        except (OSError, AttributeError):
            continue
    return ""


def cudart_version():
    """CUDA Runtime 版本，编码同 cuDriverGetVersion（major*1000 + minor*10）。"""
    for name in ("libcudart.so", "libcudart.so.12", "libcudart.so.13", "cudart64_12.dll"):
        try:
            v = ctypes.c_int(0)
            if ctypes.CDLL(name).cudaRuntimeGetVersion(ctypes.byref(v)) == 0 and v.value:
                return f"{v.value // 1000}.{(v.value % 1000) // 10}"
        except (OSError, AttributeError):
            continue
    return ""


def cudnn_version():
    for name in ("libcudnn.so", "libcudnn.so.9", "libcudnn.so.8", "cudnn64_9.dll"):
        try:
            v = ctypes.CDLL(name).cudnnGetVersion()
            return f"{v // 10000}.{(v % 10000) // 100}.{v % 100}"
        except (OSError, AttributeError):
            continue
    return ""


def nvcc_version():
    for exe in ("nvcc", "/usr/local/cuda/bin/nvcc"):
        if not (os.path.sep in exe or _which(exe)):
            continue
        out = run([exe, "--version"])
        m = re.search(r"release\s+(\d+\.\d+)", out)
        if m:
            return m.group(1)
    return ""


def _which(exe):
    return shutil.which(exe)


def smi_banner():
    """nvidia-smi 是跨平台最可靠的信息源，Linux 的 /proc 在 Windows 上不存在。"""
    info = {}
    out = run(["nvidia-smi"])
    m = re.search(r"Driver Version:\s*([\d.]+)", out)
    if m:
        info["driver"] = m.group(1)
    m = re.search(r"CUDA Version:\s*([\d.]+)", out)
    if m:
        info["cuda"] = m.group(1)
    q = run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"])
    if q:
        info["gpu"] = q.splitlines()[0].strip()
    return info


def kernel_block():
    """Linux 内核态：/proc 里的 NVRM 版本串 + 模块列表 + 模块许可证（判断开源/闭源）。"""
    rows = []
    nvrm = ""
    try:
        with open("/proc/driver/nvidia/version", encoding="utf-8", errors="replace") as f:
            nvrm = f.read()
    except OSError:
        pass

    if nvrm:
        m = re.search(r"NVRM version:\s*(.+)", nvrm)
        rows.append(("nvrm", (m.group(1).strip() if m else nvrm.strip().splitlines()[0])))
        m = re.search(r"GCC version:\s*(.+)", nvrm)
        if m:
            rows.append(("built", m.group(1).strip()))
        flavor = "open" if "Open Kernel Module" in nvrm else "proprietary"
        m = re.search(r"\b(\d+\.\d+(?:\.\d+)?)\b", nvrm)
        rows.insert(0, ("driver", f"{m.group(1) if m else DASH} ({flavor})"))

    loaded = []
    try:
        with open("/proc/modules", encoding="utf-8", errors="replace") as f:
            loaded = [ln.split()[0] for ln in f if ln.startswith("nvidia")]
    except OSError:
        pass
    if loaded:
        rows.append(("modules", " ".join(loaded)))

    # 模块许可证字段区分 Dual MIT/GPL（开源）与 NVIDIA（闭源），比版本串更硬
    if _which("modinfo"):
        lic = run(["modinfo", "-F", "license", "nvidia"])
        if lic:
            rows.append(("license", f"{lic} -> {'open' if 'MIT' in lic else 'proprietary'}"))

    for info in sorted(glob.glob("/proc/driver/nvidia/gpus/*/information")):
        try:
            with open(info, encoding="utf-8", errors="replace") as f:
                m = re.search(r"Model:\s*(.+)", f.read())
        except OSError:
            continue
        if m:
            rows.append(("gpu", m.group(1).strip()))
            break

    return rows


def print_block(title, rows):
    if not rows:
        return False
    width = max(len(k) for k, _ in rows)
    print(f"== {title} ==")
    for k, v in rows:
        print(f"{k:<{width}}  {v}")
    print()
    return True


def main():
    smi = smi_banner()
    krows = kernel_block()

    # Windows 无 /proc，退回 nvidia-smi 的驱动版本
    if not krows and smi.get("driver"):
        krows.append(("driver", smi["driver"]))

    urows = []
    for name, pat in DRIVER_LIBS:
        hit = best_lib(pat)
        if not hit:
            continue
        ver, path = hit
        urows.append((name, f"{ver or DASH}  {path}" if name in SHOW_PATH else (ver or DASH)))

    # 既没有内核模块也没有用户态驱动库，说明这台机器跟 NVIDIA 无关，别输出一堆 "-"
    if not krows and not urows:
        print("未检测到 NVIDIA 驱动")
        return

    api = cuda_api_version() or smi.get("cuda", "")
    urows.append(("cuda (driver api)", api or DASH))
    hit = best_lib("libcudart.so*")
    urows.append(("cuda (runtime)", cudart_version() or (hit[0] if hit else DASH)))
    hit = best_lib("libcudnn.so*")
    urows.append(("cudnn", cudnn_version() or (hit[0] if hit else DASH)))
    urows.append(("nvcc", nvcc_version() or DASH))

    print_block("kernel", krows)
    print_block("userspace", urows)

    k = dict(krows).get("driver", "")
    k = k.split()[0] if k else ""
    u = dict(urows).get("libcuda", "")
    u = u.split()[0] if u else ""
    if k and u:
        state = "OK" if k == u else "MISMATCH (重启或重装驱动)"
        print(f"kernel {k} / userspace {u}  {state}")


if __name__ == "__main__":
    main()
