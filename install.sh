#!/bin/bash
# 安装「下雨了么」：把插件拷进 ~/Library/Application Support/xiayule/plugin/，
# 再把 SwiftBar 的插件目录指过去。
#
# 为什么不让 SwiftBar 直接指仓库目录：仓库一改名或挪位置，菜单栏立刻变空，而且不报错。
# 2026-08-20 把仓库挪进 small_projects/ 时就这么静默挂过一次，是隔了几天才发现的。
# 装出来的是运行时副本，仓库退回纯源码，随便挪。
#
# 用法: ./install.sh [--force]
#   --force  SwiftBar 当前插件目录里还有别的插件时，也照样改指向
set -euo pipefail
cd "$(dirname "$0")"

FORCE=0
if [ "$#" -gt 1 ]; then echo "参数过多：只接受一个可选的 --force" >&2; exit 2; fi
case "${1:-}" in
    "")        ;;
    --force)   FORCE=1 ;;
    *)         echo "未知参数: $1（只支持 --force）" >&2; exit 2 ;;
esac

# set -u 挡得住 HOME 没定义，挡不住 HOME=""——那样下面的路径会指到 /Library/…
if [ -z "${HOME:-}" ] || [ ! -d "$HOME" ]; then
    echo "HOME 没设好: '${HOME:-}'" >&2
    exit 2
fi

SRC_PLUGIN="plugin/xiayule.5m.py"
SRC_IGNORE="plugin/.swiftbarignore"
RUNTIME="$HOME/Library/Application Support/xiayule"
PLUGIN_DIR="$RUNTIME/plugin"
DEST_PLUGIN="$PLUGIN_DIR/xiayule.5m.py"
DEST_IGNORE="$PLUGIN_DIR/.swiftbarignore"
# 临时文件一律加点前缀：SwiftBar 只按「隐藏」跳过文件，扩展名里只排除 .json。
# 叫 xiayule.5m.py.new 的话，装到一半被 DirectoryObserver 撞见就会被 chmod +x 然后执行。
TMP_PLUGIN="$PLUGIN_DIR/.xiayule.5m.py.new"
TMP_IGNORE="$PLUGIN_DIR/.swiftbarignore.new"
DOMAIN="com.ameba.SwiftBar"
REPORT="$HOME/Library/Application Support/SwiftBar/Diagnostics/latest-system-report.txt"

cleanup() { rm -f "$TMP_PLUGIN" "$TMP_IGNORE"; }
trap cleanup EXIT

for f in "$SRC_PLUGIN" "$SRC_IGNORE"; do
    [ -f "$f" ] || { echo "缺文件: $f（这个脚本要在仓库根目录跑）" >&2; exit 1; }
done

open -Ra SwiftBar >/dev/null 2>&1 || {
    echo "没找到 SwiftBar，先装: brew install --cask swiftbar" >&2
    exit 1
}

# 装之前先验语法：语法错的脚本装进去，菜单栏就是一个方框问号，没有别的提示。
# 用 ast.parse 不用 py_compile——后者会在源文件旁边生成 __pycache__，
# 那个 .pyc 自己又会被 SwiftBar 当插件执行（来龙去脉见 docs/notes.md）。
python3 -c "import ast,sys; f=sys.argv[1]; ast.parse(open(f, encoding='utf-8').read(), f)" "$SRC_PLUGIN"

# 逐行缩进，给下面两处清单用。不走 `sed 's/^/  /'`：shellcheck 会报 SC2001，
# 而 ${var//.../} 又没法给多行变量的每一行都加前缀。
indent() { while IFS= read -r line; do echo "  $line"; done; }

# 列出 SwiftBar 会当插件加载的文件：非隐藏、扩展名不是 .json、普通文件且非空。
# 递归——SwiftBar 用 enumerator(at:) 遍历，子目录里的文件照样算。
list_loadable() {
    [ -d "$1" ] || return 0
    find "$1" -type f ! -path '*/.*' ! -name '*.json' -size +0c 2>/dev/null || true
}

CUR="$(defaults read "$DOMAIN" PluginDirectory 2>/dev/null || true)"

# SwiftBar 全局只有一个插件目录。改指向 = 原目录里的插件全部停掉，而且是静默的。
if [ "$FORCE" -eq 0 ] && [ -n "$CUR" ] && [ "$CUR" != "$PLUGIN_DIR" ]; then
    others="$(list_loadable "$CUR" | grep -v '/xiayule\.5m\.py$' || true)"
    if [ -n "$others" ]; then
        echo "SwiftBar 现在的插件目录里还有别的插件，改指向会让它们全部停掉：" >&2
        echo "$others" | indent >&2
        echo "确认要改就跑: ./install.sh --force" >&2
        exit 1
    fi
fi

mkdir -p "$PLUGIN_DIR"

# 先落地排除规则再落地插件：反过来的话，中间那一小段时间里插件已经在跑、
# 而 .swiftbarignore 还没到位，目录里万一有杂物就会被当插件执行。
cp "$SRC_IGNORE" "$TMP_IGNORE"
cp "$SRC_PLUGIN" "$TMP_PLUGIN"
chmod +x "$TMP_PLUGIN"
mv -f "$TMP_IGNORE" "$DEST_IGNORE" || { echo "写入 $DEST_IGNORE 失败，没动 SwiftBar。" >&2; exit 1; }
mv -f "$TMP_PLUGIN" "$DEST_PLUGIN" || { echo "写入 $DEST_PLUGIN 失败，没动 SwiftBar。" >&2; exit 1; }

# 插件目录里只能有插件。SwiftBar 设置里改过 VAR_* 的话会在这里留一份 .json，
# 那个扩展名 SwiftBar 自己就排除了，所以 list_loadable 不会把它算进来。
junk="$(list_loadable "$PLUGIN_DIR" | grep -v '/xiayule\.5m\.py$' || true)"
if [ -n "$junk" ]; then
    echo "警告：插件目录里有不该在的文件，SwiftBar 会把它们也当插件执行（菜单栏会冒方框问号）：" >&2
    echo "$junk" | indent >&2
fi

if [ "$CUR" = "$PLUGIN_DIR" ]; then
    # 指向没变，只是换了脚本内容。插件目录根部的文件被替换会触发 SwiftBar 的
    # DirectoryObserver 自动重扫（约 0.5 秒），不用重启整个 App；
    # 再推一下让它立刻重跑，而不是干等下一个 5 分钟。
    open -g "swiftbar://refreshallplugins" 2>/dev/null || true
else
    # 先杀再写 defaults，是保守做法不是实测结论：手动按「先写后杀」跑过一次也生效了。
    # 但 App 活着的时候 cfprefsd 给它的是缓存副本，它退出时又可能把内存里那份整体回写，
    # 一旦撞上就是「defaults write 返回 0、重启后路径又变回去了」这种最难查的样子。
    # 进程先没了就不存在这个窗口，成本只是多等几秒。
    killall SwiftBar 2>/dev/null || true
    for _ in 1 2 3 4 5; do
        pgrep -x SwiftBar >/dev/null 2>&1 || break
        sleep 1
    done
    defaults write "$DOMAIN" PluginDirectory "$PLUGIN_DIR"
    open -a SwiftBar
fi

# 写完要亲眼确认，别打一句自己没验证过的「已安装」。
NOW="$(defaults read "$DOMAIN" PluginDirectory 2>/dev/null || true)"
if [ "$NOW" != "$PLUGIN_DIR" ]; then
    echo "插件目录没写进去，现在是: '${NOW:-（空）}'" >&2
    exit 1
fi

running=0
for _ in 1 2 3 4 5 6 7 8; do
    if pgrep -x SwiftBar >/dev/null 2>&1; then running=1; break; fi
    sleep 1
done
if [ "$running" -eq 0 ]; then
    echo "插件已装好，但 SwiftBar 没起来。手动开一下: open -a SwiftBar" >&2
    exit 1
fi

# SwiftBar 每次重扫插件都会重写这份诊断报告，里面有候选清单和加载状态。
# 老版本可能不生成，所以查不到只提示、不当失败。
loaded=0
for _ in 1 2 3 4 5 6 7 8; do
    if [ -f "$REPORT" ] && grep -qF "$DEST_PLUGIN" "$REPORT" 2>/dev/null; then loaded=1; break; fi
    sleep 1
done

echo "已安装: $DEST_PLUGIN"
echo "SwiftBar 插件目录: $PLUGIN_DIR"
if [ "$loaded" -eq 1 ]; then
    echo "SwiftBar 已认到这个插件（诊断报告已确认）。"
else
    echo "没能从诊断报告里确认加载状态，自己看一眼: cat \"$REPORT\"" >&2
fi
echo
echo "接下来："
echo "  · token 放 ~/.config/caiyun/token，或在 SwiftBar 设置里填 VAR_CAIYUN_TOKEN"
echo "  · 位置改 VAR_LOC / VAR_PLACE（默认是徐泾）"
echo "  · 改完代码要重跑一次 ./install.sh 才生效——跑的是副本，不是仓库里这份"
