
# 用户定义 User-defined
alias grep='grep --color=auto'
alias ls='ls --color=auto'
# cargo
. "$HOME/.cargo/env"
# rustup
export RUSTUP_UPDATE_ROOT=https://mirrors.tuna.tsinghua.edu.cn/rustup/rustup
export RUSTUP_DIST_SERVER=https://mirrors.tuna.tsinghua.edu.cn/rustup
# GHCup
export PATH="$HOME/.ghcup/bin:$PATH"

# 抑制原有的 `(venv)`
export VIRTUAL_ENV_DISABLE_PROMPT=1

# 颜色定义(解耦颜色值)
# 使用 256 色或标准颜色,便于修改
COLOR_VENV="\033[38;2;144;255;144m"   # 浅绿
COLOR_USER="\033[38;2;243;168;183m"   # 粉红
COLOR_TIME="\033[38;2;91;206;250m"    # 粉蓝
COLOR_PATH="\033[38;2;255;255;255m"   # 白色
COLOR_BAT="\033[38;2;250;214;120m"    # 浅黄
COLOR_LOW="\033[38;2;255;94;94m"      # 红
COLOR_RESET="\033[0m"

# 电量提示函数
# 只输出 "[100%] ";机器没有 BAT*(台式机)时输出空串,提示符里不留空括号
# 直接读 sysfs,不 fork upower/acpi;多电池取平均
# 括号内固定 4 个字符("%3d%%" 补空格),从左往右铺 1~4 格底色,格数/颜色随电量变化
# 直接读 sysfs 不 fork upower/acpi;多电池取平均;无 BAT* 时整段不输出
__battery_prompt() {
    local dir cap sum=0 n=0
    for dir in /sys/class/power_supply/BAT*/; do
        [[ -r "$dir/capacity" ]] || continue
        cap=$(<"$dir/capacity")
        [[ $cap =~ ^[0-9]+$ ]] || continue
        sum=$((sum + cap)); n=$((n + 1))
    done
    (( n )) || return 0
    
    local lvl=$((sum / n)) text cells color
    if   (( lvl >= 90 )); then cells=4; color=$COLOR_VENV
        elif (( lvl >= 50 )); then cells=3; color=$COLOR_VENV
        elif (( lvl >= 25 )); then cells=2; color=$COLOR_BAT
    else                       cells=1; color=$COLOR_LOW
    fi
    printf -v text '%3d%%' "$lvl"
    
    # 调色板里存的是字面 "\033[38;2;..."(留给提示符解码),这里要先转成真 ESC;
    # 同一套 RGB 把 38; 换成 48; 当背景色,再配黑字,浅色底上才读得清;
    # \001/\002 是 readline 的不可见区标记:不标的话转义序列会被算进提示符宽度,长命令换行错位;
    local esc on=$'\001' off=$'\002' black=$'\033[30m' reset=$'\033[0m'
    printf -v esc '%b' "${color/38;/48;}"
    printf '[%s%s%s%s] ' "$on$esc$black$off" "${text:0:cells}" "$on$reset$off" "${text:cells}"
}

# venv 提示函数
__venv_prompt() {
    [[ -n "$VIRTUAL_ENV" ]] && echo "[$(basename "$VIRTUAL_ENV")] "
}

# 时间提示函数
__time_prompt() {
    date "+%Y.%m.%d.%H:%M:%S"
}

info() {
    printf '[%s][info] %s\n' "$(__time_prompt)" "$*"
}

error() {
    printf '[%s][error] %s\n' "$(__time_prompt)" "$*" >&2
}

# 构建 PS1
# 注意:${COLOR_...} 是 ANSI 转义序列,需放在 '[' 和 '\]' 之间以正确计算长度(可选)
PS1="\[${COLOR_VENV}\]\$(__venv_prompt)\[${COLOR_RESET}\]"
PS1+="\[${COLOR_USER}\][\u 🍥 \h]\[${COLOR_RESET}\] "
PS1+="\[${COLOR_TIME}\][\$(__time_prompt)]\[${COLOR_RESET}\] "
PS1+="\$(__battery_prompt)\n"
PS1+="\[${COLOR_PATH}\][\w]\[${COLOR_RESET}\]"
PS1+="\n\\$ " # 专用转义序列:普通用户$;root#

export PS1

# 仅交互式 shell 打印:否则会污染 scp/sftp/rsync 等非交互会话的协议流
if [[ $- == *i* ]]; then
    printf "Was vernünftig ist, das ist wirklich;\n"
    printf "und was wirklich ist, das ist vernünftig.\n"
    printf "                                         ---- G.W.F.Hegel\n"
fi

#fastfetch #--sixel ~/fetch.png --logo-width 40
