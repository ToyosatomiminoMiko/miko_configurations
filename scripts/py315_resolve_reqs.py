#!/usr/bin/env python3
"""是什么: 把一份 requirements 列表里"Python 3.15 装不上的固定版本"改写成能直接装 wheel 的版本,
        输出成一份新的 requirements 文本,供 uv pip install 使用.

为什么: Fedora 45 把系统 Python 从 3.14 升到 3.15, 旧 venv 里 pin 住的部分包只在旧 Python
        下发布过 wheel (例如 numpy 2.5.0 / pandas 3.0.3), 在 3.15 上只能源码编译或直接失败.
        这里查包索引的 simple 页面, 用 packaging 的 sys_tags() 判断某个 pin 是否有当前解释器
        (本机 3.15, x86_64) 可用的 wheel:
          1) 有 → 原样保留, 版本不动;
          2) 没有但该包更高版本有 → 换成"最新的有 wheel 的稳定版本", 只改这份临时清单, 不动项目文件;
          3) 压根没有 wheel 的纯源码小包 (如 docopt) → 保留原 pin, 让安装器自己构建.
        非固定版本 (>=, ~= 等) 一律原样保留, 交给解析器选 3.15 可装的版本.
        只读索引, 不写项目内任何文件; 输出文件由调用方决定 (脚本写到 ~/.local/share 下).

用法: py315_resolve_reqs.py IN_REQ OUT_REQ

元信息: tempest, 2026-11-06.
"""

from __future__ import annotations

import sys
import re
import html
import urllib.request
import concurrent.futures
from pathlib import Path

from packaging.requirements import Requirement, InvalidRequirement
from packaging.utils import parse_wheel_filename, parse_sdist_filename
from packaging.version import Version, InvalidVersion
from packaging.tags import sys_tags

# 本机解释器的可用标签集合; 3.15 的 cp315 / abi3 / py3-none-any / manylinux 都在里面.
TAGS = set(sys_tags())

# 索引地址与 pip 保持一致: 先读 pip 配置里的 index-url, 读不到就用 PyPI 官方.
DEFAULT_INDEX = "pypi.org/simple"
SIMPLE_TMPL = "{index}/{name}/"


def index_base() -> str:
    """是什么: 返回 simple 索引根地址 (末尾带 /simple).

    为什么: 本机 pip 已配清华镜像; uv 默认走 PyPI. 这里跟 pip 保持一致,
            避免解析结果和实际安装源不一致.
    """
    try:
        import subprocess

        out = subprocess.run(
            [sys.executable, "-m", "pip", "config", "get", "global.index-url"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
        if out:
            return out.rstrip("/").replace("/simple", "") + "/simple"
    except Exception:
        pass
    return "https://" + DEFAULT_INDEX


INDEX = index_base()
_cache: dict[str, str | None] = {}


def fetch_simple(name: str) -> str | None:
    """是什么: 取某个包的 simple 索引 HTML; 失败返回 None (调用方按"不确定"处理)."""
    key = name.lower()
    if key in _cache:
        return _cache[key]
    url = SIMPLE_TMPL.format(index=INDEX, name=key)
    try:
        with urllib.request.urlopen(url, timeout=40) as resp:
            txt = resp.read().decode("utf-8", "replace")
    except Exception:
        txt = None
    _cache[key] = txt
    return txt


def wheels_and_sdists(txt: str | None) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """是什么: 从 simple HTML 里拆出 {版本: [可装 wheel 文件名]} 和 {版本: [sdist 文件名]}.

    为什么: simple 页面里 href 带 #sha256= 片段, 所以不能要求 href 以引号结尾;
            解析 wheel 时用 packaging 统一处理名字/构建号/标签, 避免手写正则判断标签出错.
    """
    wheels: dict[str, list[str]] = {}
    sdists: dict[str, list[str]] = {}
    if not txt:
        return wheels, sdists
    for m in re.finditer(r'href="[^"]*?/([^"/#]+\.(?:whl|tar\.gz|zip))', txt):
        fn = html.unescape(m.group(1))
        if fn.endswith(".whl"):
            try:
                _n, ver, _b, tags = parse_wheel_filename(fn)
                if TAGS & tags:
                    wheels.setdefault(str(ver), []).append(fn)
            except Exception:
                continue
        else:
            try:
                _n, ver = parse_sdist_filename(fn)
                sdists.setdefault(str(ver), []).append(fn)
            except Exception:
                continue
    return wheels, sdists


def plan_line(line: str) -> tuple[str, str]:
    """是什么: 处理一行依赖, 返回 (写进新清单的行, 变更说明/空串).

    为什么: 只对"== 精确固定版本"做改写; 其它写法 (>=, ~=, extras, marker) 保持原样,
            因为解析器自己会在 3.15 可装的候选里挑, 不需要也不应该替它做主.
    """
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or stripped.startswith("-"):
        return line, ""
    try:
        req = Requirement(stripped)
    except InvalidRequirement:
        return line, ""

    # 只处理单一 == 固定版本; 通配符 (==1.*) 交给解析器.
    exact = None
    for spec in req.specifier:
        if spec.operator == "==" and "*" not in spec.version:
            exact = spec.version
    if exact is None or len(list(req.specifier)) != 1:
        return line, ""

    txt = fetch_simple(req.name)
    if txt is None:
        return line, f"?# 索引不可用, 保留原 pin: {stripped}"
    wheels, sdists = wheels_and_sdists(txt)
    if exact in wheels:
        return line, ""

    def latest(cands: dict[str, list[str]]) -> str | None:
        vs = []
        for v in cands:
            try:
                ver = Version(v)
            except InvalidVersion:
                continue
            if not ver.is_prerelease:
                vs.append(ver)
        return str(max(vs)) if vs else None

    # 没有该 pin 的 wheel: 先找同包最新有 wheel 的版本.
    best = latest(wheels)
    if best is not None:
        out = line.replace(exact, best, 1)
        return out, f"升级 {req.name} {exact} -> {best} (原 pin 无 3.15 wheel)"

    # 完全没有 wheel: 保留 pin (安装器会用 sdist 构建); pin 连 sdist 都没有则退到最新 sdist.
    if exact in sdists:
        return line, f"源码构建 {req.name}=={exact}"
    best_sd = latest(sdists)
    if best_sd is not None:
        return line.replace(exact, best_sd, 1), f"源码更新 {req.name} {exact} -> {best_sd}"
    return line, f"!! 索引里找不到 {stripped}, 保留原样"


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: py315_resolve_reqs.py IN_REQ OUT_REQ", file=sys.stderr)
        return 2
    src = Path(argv[1]).expanduser()
    dst = Path(argv[2]).expanduser()
    lines = src.read_text(encoding="utf-8").splitlines()

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        results = list(ex.map(plan_line, lines))

    changes = [(orig, out, why) for (orig, (out, why)) in zip(lines, results) if why]
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text("\n".join(out for _o, (out, _w) in zip(lines, results)) + "\n", encoding="utf-8")

    for orig, _out, why in changes:
        if orig.strip():
            print(f"  {why}: {orig.strip()}", file=sys.stderr)
    print(f"  {len(changes)} 处调整 -> {dst}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
