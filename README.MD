# 家目录仓库(`~`)

`$HOME` 下的 dotfiles 和自用小工具,一个 `git` 管全部,工作树就是 `~`。
2026-11-04 由原来的 `self_configurations` 仓库整体合并进来(历史用 merge commit 接上),
远端现在是 `github.com/ToyosatomiminoMiko/miko_configurations`。

## 里面有什么

| 路径 | 是什么 |
| --- | --- |
| `.bashrc.d/00-self.sh` | shell 片段(别名、cargo/ghcup 环境、PS1、`info`/`error`),由 `~/.bashrc` 的 drop-in 循环 source |
| `.config/{kitty,htop,btop,fastfetch,environment.d}` | 各程序的配置 |
| `.dsh/AGENTS.md` | 全局 agent 规则 |
| `.gtkrc-2.0` | GTK2 主题 |
| `apps/` | 自成一体的小应用 |
| `scripts/` | 一次性或偶尔用的小脚本 |

纳入范围由 `.gitignore` **白名单**决定:`/*` 先忽略一切,再逐个 `!` 放行。好处是
`.ssh`、`.gnupg`、`.cache`、`.local`、`.dsh` 里除 `AGENTS.md` 之外的东西天然进不来,
不用维护黑名单。

`~/.bashrc` 本身**不在**仓库里,只有那 26 行发行版默认头;换发行版(比如 NixOS)时
不用连 Fedora 的头部一起搬,片段在 `.bashrc.d/` 里自动生效。

## 换机器怎么带走

```bash
git clone https://github.com/ToyosatomiminoMiko/miko_configurations.git /tmp/dot \
    && rsync -a /tmp/dot/ ~/     # 连 .git 一起拷,之后在 ~ 里就能继续 commit
```

前提是新机器的 `~/.bashrc` 里有 drop-in 循环(Fedora 默认有;Debian/Ubuntu 需要自己补):

```bash
if [ -d ~/.bashrc.d ]; then
    for rc in ~/.bashrc.d/*; do
        [ -f "$rc" ] && . "$rc"
    done
fi
unset rc
```

## apps/

| 目录 | 是什么 |
| --- | --- |
| `apps/image_browser/` | FastAPI 只读服务,把某个目录的图片/文本暴露成网页,局域网内用浏览器看。 |
| `apps/file_drop.py` | 只依赖标准库的文件投放服务,收 curl 发来的文件或文本,并支持用 wget/curl 从 `uploads/` 取回。 |

### image_browser

```bash
cd ~/apps/image_browser
uv venv .venv
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python main.py
```

配置固定读**当前工作目录**的 `image_browser_conf.toml`(已 ignore),字段只有
`dir` / `host` / `port`;不写会直接退出并打印模板,也可以照抄 `main.py` 里的
`CONFIG_TEMPLATE`。细节见 `apps/image_browser/README.md`。

### file_drop

```bash
python3 ~/apps/file_drop.py
```

没有命令行开关,默认值(`host` / `port` / `upload_dir`)在脚本的 `DEFAULTS` 里;
想覆盖就在脚本同目录放 `apps/file_drop.toml`(已 ignore),只写要改的字段:

```toml
host = "0.0.0.0"        # 监听地址, 0.0.0.0 = 所有网卡
port = 8080             # 监听端口
upload_dir = "uploads"  # 落盘目录, 相对路径按本文件所在目录解析
```

字段名写错或类型不对会在启动阶段报错退出,不会静默退回默认值。解析用标准库 `tomllib`,
所以需要 Python 3.11+。取回和上传是同一个服务:

```bash
wget http://ip:8080/bashrc            # 只认 URL 最后一段
```

## scripts/

| 文件 | 说明 |
| --- | --- |
| `scripts/rename_index.sh` | 把文件名末尾 `_p<数字>` 补零对齐(默认 2 位,`-3` 为 3 位),方便排序。 |
| `scripts/launch_webgpu.sh` | 用无沙盒 + WebGPU 参数启动 chromium 和 VS Code。 |
| `scripts/fastfetch_gen.sh` | 一行 `fastfetch --gen-config`,重新生成 `~/.config/fastfetch/config.jsonc`。 |

## 环境更新备忘

Haskell / Rust 工具链的更新与版本检查(以前是 `config/_env_.sh`,那个文件写明了自己
是"文档,不是用来执行"的):

```bash
# Haskell: cabal 管构建和依赖, ghc 是真正的编译器, HLS 是可选的语言服务器
cabal update
cabal --version; ghc --version

# Rust
rustup update
cargo --version; rustc --version; rustup --version
```

## 说明

- `.venv/`、`__pycache__/`、`uploads/`、`*.toml` 是本地或运行时内容,已在 `.gitignore` 里排除。
- 本仓库的历史包含合并前的 `self_configurations`,用 `git log --all` 或
  `git log --follow <file>` 能追到改名/搬迁之前的记录。
