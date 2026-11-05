#!/usr/bin/env bash
# 是什么: 系统 Python 从 3.14 升到 3.15 后, 重建项目里的 .venv 并重装依赖.
#
# 为什么:
#   1. venv 的 bin/python 是 /usr/bin/python 的符号链接, 系统升级后它自动指向 3.15;
#      但 site-packages 还在 lib/python3.14/ 下, 于是 venv 里所有第三方包都 import 不到,
#      这种 venv 没法原地修, 只能删掉重建.
#   2. 系统已没有 python3.14 (dnf 已不再提供), 所以重建是唯一出路.
#   3. 依赖来源按优先级取: uv.lock + pyproject > requirements.txt > 旧 venv 的 dist-info 快照.
#      快照先存到 ~/.local/share 下再删旧 venv, 保证没有依赖清单的项目也不会丢依赖信息.
#   4. 旧 pin 在 3.15 上没有 wheel 的 (例如 numpy 2.5.0 / pandas 3.0.3), 由
#      py315_resolve_reqs.py 换成该包最新的可装版本; 改的是临时清单, 项目文件一律不动.
#
# 用法:
#   scripts/py315_venv_rebuild.sh                    # 扫描 /mnt/IVSTINIANVS 下所有含 .venv 的项目
#   scripts/py315_venv_rebuild.sh DIR [DIR ...]      # 只处理指定项目
#
# 元信息: tempest, 2026-11-06.
set -uo pipefail

PY315=${PY315:-/usr/bin/python3.15}
UV=${UV:-uv}
SNAP_ROOT=${SNAP_ROOT:-$HOME/.local/share/python-reconfigure-2026-11-06/venv-pins}
HERE=$(dirname "$(readlink -f "$0")")
RESOLVER=$HERE/py315_resolve_reqs.py
DEFAULT_ROOT=/mnt/IVSTINIANVS

FAILED=()
DONE=()

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }

# 是什么: 从旧 venv 的 dist-info 里抓 Name/Version, 写成 requirements 风格快照.
# 为什么: 有些项目自己没写 requirements/pyproject, 只有 venv 里装着的东西能说明它依赖什么;
#         旧 venv 删掉之前必须先落盘.
snapshot_pins() {
    local proj=$1 out=$2
    "$PY315" - "$proj" "$out" <<'PY'
import glob
import sys
from pathlib import Path

proj, out = Path(sys.argv[1]), Path(sys.argv[2])
rows = []
for sp in glob.glob(str(proj / ".venv" / "lib" / "python3.*" / "site-packages")):
    for di in glob.glob(sp + "/*.dist-info"):
        md = Path(di) / "METADATA"
        name = ver = None
        if md.exists():
            for line in md.read_text(errors="replace").splitlines():
                if not line.strip():
                    break
                if line.startswith("Name: ") and name is None:
                    name = line[6:].strip()
                elif line.startswith("Version: ") and ver is None:
                    ver = line[9:].strip()
        if name and ver:
            rows.append(f"{name}=={ver}")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text("\n".join(sorted(set(rows))) + "\n")
print(f"  旧依赖快照 {len(rows)} 个包 -> {out}")
PY
}

# 是什么: 清空并重建一个项目的 .venv, 然后按依赖来源重装, 最后做基本验证.
rebuild_one() {
    local proj=$1
    local slug
    slug=$(basename "$proj")
    log "===== $slug : $proj"

    if [[ ! -d "$proj" ]]; then
        log "  目录不存在, 跳过"; FAILED+=("$slug (目录不存在)"); return
    fi

    local cfg="$proj/.venv/pyvenv.cfg"
    if [[ -f "$cfg" ]] && grep -qE '^(version|version_info) = 3\.15' "$cfg"; then
        if [[ -f "$proj/pyproject.toml" && -f "$proj/uv.lock" ]]; then
            log "  已经是 3.15, 用 uv sync 补齐锁定依赖"
            ( cd "$proj" && "$UV" sync ) || { FAILED+=("$slug (uv sync)"); return; }
        else
            log "  已经是 3.15, 跳过"
        fi
        DONE+=("$slug (已是 3.15)"); return
    fi

    mkdir -p "$SNAP_ROOT"
    if [[ -d "$proj/.venv" ]]; then
        snapshot_pins "$proj" "$SNAP_ROOT/$slug.pins.txt" || { FAILED+=("$slug (快照失败)"); return; }
    fi

    rm -rf "$proj/.venv" || { FAILED+=("$slug (删旧 venv 失败)"); return; }
    "$UV" venv "$proj/.venv" --python "$PY315" >/dev/null 2>&1 || { FAILED+=("$slug (uv venv)"); return; }
    log "  已建 3.15 venv"

    local installed=0
    if [[ -f "$proj/pyproject.toml" && -f "$proj/uv.lock" ]]; then
        log "  依赖: pyproject.toml + uv.lock (uv sync)"
        if ! ( cd "$proj" && "$UV" sync ); then FAILED+=("$slug (uv sync)"); return; fi
        installed=1
    else
        local reqs=""
        if [[ -f "$proj/requirements.txt" ]]; then
            reqs="$proj/requirements.txt"
            log "  依赖: requirements.txt"
        elif [[ -f "$SNAP_ROOT/$slug.pins.txt" ]]; then
            reqs="$SNAP_ROOT/$slug.pins.txt"
            log "  依赖: 旧 venv 快照 $reqs"
        else
            log "  没有找到任何依赖来源, venv 保持空的"
        fi

        if [[ -n "$reqs" ]]; then
            local resolved="$SNAP_ROOT/$slug.resolved.txt"
            if ! "$PY315" "$RESOLVER" "$reqs" "$resolved"; then
                FAILED+=("$slug (依赖解析失败)"); return
            fi
            # torch_test 这类项目: 旧 pin 的 torch/nvidia 是成套锁死的, 逐个升版本会错配,
            # 所以交给 uv 重新解析最新 torch 栈, 不用旧快照.
            if [[ "$slug" == "torch_test" ]]; then
                log "  torch 项目: 重新解析 torch + torchvision (下载较大)"
                if ! "$UV" pip install --python "$proj/.venv/bin/python" torch torchvision; then
                    FAILED+=("$slug (torch 安装失败)"); return
                fi
            else
                if ! "$UV" pip install --python "$proj/.venv/bin/python" -r "$resolved"; then
                    FAILED+=("$slug (uv pip install)"); return
                fi
            fi
            installed=1
        fi
    fi

    # 旧 venv 是 python -m venv 造的, 带 pip; 保持习惯, 新 venv 也补一个 pip.
    "$UV" pip install --python "$proj/.venv/bin/python" pip >/dev/null 2>&1

    local pyver n
    pyver=$("$proj/.venv/bin/python" -V 2>&1)
    n=$("$proj/.venv/bin/python" - <<'PY'
import importlib.metadata as m
print(len(list(m.distributions())))
PY
)
    log "  完成: $pyver, $n 个包"
    DONE+=("$slug ($pyver, ${n}包)")
}

main() {
    local projects=()
    if (( $# > 0 )); then
        projects=("$@")
    else
        while IFS= read -r v; do
            projects+=("$(dirname "$v")")
        done < <(find "$DEFAULT_ROOT" -maxdepth 3 -name .venv -type d 2>/dev/null | sort)
    fi

    log "待处理 ${#projects[@]} 个项目"
    for p in "${projects[@]}"; do
        rebuild_one "$(readlink -f "$p")"
    done

    echo
    log "======== 汇总 ========"
    for x in "${DONE[@]}";    do log "  OK   $x"; done
    for x in "${FAILED[@]}";  do log "  FAIL $x"; done
    (( ${#FAILED[@]} == 0 )) && return 0 || return 1
}

main "$@"
