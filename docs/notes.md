# 笔记

写这个插件时踩的坑和查清的机制。都是实测或读源码得来的，源码行号对应 SwiftBar v2.1.1 (build 597)。

## 插件目录里只能放插件

菜单栏上冒出一个方框问号，这个项目里发生过三次。

那个「问号」不是 SwiftBar 画的图标。插件执行失败时它把菜单栏标题设成 `􀇾`（U+1001FE，SF Symbols 私有区码位），而菜单栏字体没有这个码位的字形，CoreText 回落到 `.LastResort` 字体，私有区一律画成方框问号。所以看见 ❓ 就等于：有个「插件」跑挂了。

挂掉的往往不是你的插件，是插件目录里根本不该被当插件的文件。SwiftBar 的扫描规则比想象中激进（`PluginManger.swift` 的 `getPluginList()`），任意深度下满足这些条件的文件都会被加载执行：

- 非隐藏（点开头的跳过）
- 扩展名不是 `.json`（唯一按扩展名排除的类型）
- 是普通文件、且非空
- 没被 `.swiftbarignore` 匹配
- 目录内候选总数 < 50

它用 `FileManager.enumerator(at:)` 递归遍历，子目录里的文件照样算。`MakePluginExecutable` 默认开着，没有执行位的文件会被 `chmod +x`（`Plugin.makeScriptExecutable`）之后执行。文件名里没有合法刷新间隔也照样加载，只是间隔变成一百天——但仍会立即执行一次，足够挂给你看。

三次问号分别是：`__pycache__` 里的 `.pyc`（两次）、以及把插件目录指到仓库根目录时被执行的 `README.md`。SwiftBar 会给每个加载过的插件在 `~/Library/Application Support/SwiftBar/Plugins/` 下建数据目录，这些目录至今还在，是现成的物证。建目录的 `createSupportDirs()` 有三个调用点，全在插件的构造函数里（`ExecutablePlugin.swift:72`、`StreamablePlugin.swift:63`、`PackagedPlugin.swift:100`），而构造函数只对通过筛选的文件执行——所以目录存在就等于「它确实被当插件加载过」。

所以这个仓库有三道防线：脚本单独放 `plugin/`，文档留在仓库根目录；`plugin/.swiftbarignore` 排除构建产物；仓库根目录再放一份一样的兜底——因为 SwiftBar 只读插件目录根部那一份，万一有人把目录指到仓库根，`plugin/` 里那份根本读不到。

### 写排除规则有两个坑，第二个是 SwiftBar 的 bug

**一、光写目录名挡不住目录里的文件。** 递归枚举第一遍就把子目录里的文件全平铺进候选列表了，而匹配是逐个文件做的——`__pycache__` 这一条只能省掉一次冗余扫描，拦不住 `__pycache__/x.pyc`。

**二、`**/` 那条转换是死代码。** 源码是这么写的：

```swift
NSRegularExpression.escapedPattern(for: pattern)
    .replacingOccurrences(of: "\\*\\*/", with: "(.*/)?")
```

但 Foundation 的 `escapedPattern` 会把 `/` 也转义掉，于是字符串里是 `\*\*\/`，而待替换的字面量是 `\*\*/`——永远匹配不上。跑一段 Swift 就能看到：

```
docs/**/*   →   ^docs\/[^/]*[^/]*\/[^/]*$      要求正好三段路径
docs/*      →   ^docs\/[^/]*$                  才匹配得到 docs/menubar.png
```

所以 `dir/**/*` 不是「任意深度」，而是「刚好两层」。目录必须按深度逐条列：`dir/*`、`dir/*/*`。

这个 bug 的身世（读上游 git 历史查清的）：`.swiftbarignore` 是 2023-04 加入的（[#358](https://github.com/swiftbar/SwiftBar/issues/358)，v2.0.0 发布），初版只拿模式去整串匹配「URL 字符串式相对路径」——子目录里的精确文件名永远匹配不上，路径带空格还会被百分号编码搅局。于是有了 [#436](https://github.com/swiftbar/SwiftBar/issues/436)「.swiftbarignore not works」（2025-03）。修它的提交 `7626f518`（"Fix #436"，v2.1.0-beta-1 起发布）重写了匹配器：改用真路径、加了文件名与相对路径双臂、`*` 改成不跨斜杠——都是对的，但顺手加的 `**/` 支持从写下那一刻就是死代码。上游 4270 行测试里没有一条测 `.swiftbarignore`，两代 bug 都是这么溜出去的。

**最省事的写法是只写文件名的 glob**（`*.pyc`、`*.png`），因为匹配会拿 `lastPathComponent` 试一次，任意深度都生效。

匹配语义完整版：先精确比对文件名或相对插件目录的路径，再把 glob 转正则（`*` → `[^/]*` 不跨斜杠，`?` → `[^/]`），同样对文件名和相对路径两者分别尝试。`#` 开头的行是注释，所以 emacs 的 `#autosave#` 没法用规则排除；点开头的路径本来就被跳过，写进去是死规则。

还有一点值得单说：把名叫 `token` 的明文凭据放进插件目录，它会被 `chmod +x` 然后**执行**。所以排除规则里专门列了 `token`、`id_rsa`、`*.pem`、`*.p12` 这些。但黑名单不可能覆盖全——SwiftBar 没有白名单也不支持 `!` 取反，像 `node_modules` 这种任意深度的树只能逐层列。真正的保障是「插件目录里只放插件」这条纪律，测试里那条 `os.listdir` 断言就是干这个的，不依赖任何对 SwiftBar 语义的建模。

### 清理完要不要重启

通常不用。brew 装的（非 App Store 版）有 `DirectoryObserver`，插件目录变动约 0.5 秒后自动重扫。

但它只是插件目录本身 fd 上的一个 vnode 监听，**不递归**：改动如果只发生在已存在的子目录内部（比如删掉 `plugin/__pycache__/` 里的某个文件），不会触发重扫，问号会赖着不走，这时才需要 `killall SwiftBar; open -a SwiftBar`。

菜单里的「Refresh all」在非 App Store 版**不会**重扫目录——`loadPlugins()` 只在 App Store 分支的刷新路径里被调用。

## py_compile 会偷偷生成 __pycache__

`PYTHONDONTWRITEBYTECODE=1` 管不住 `python3 -m py_compile`。那个环境变量只影响 import 时的隐式字节码写入，不影响显式编译，`-B` 同样管不住。用 `importlib` 把插件当模块 import 来跑测试时也会在源文件旁边生成 `__pycache__`。

这就是问号反复出现的直接原因——每次做语法检查都在重新种一个。

现在两条路都堵上了：`.swiftbarignore` 保证 `.pyc` 不会变成问号，`test_plugin.py` 开头设了 `sys.dont_write_bytecode = True` 所以压根不生成。手动检查语法用这个，零产物且报错会指出文件名：

```bash
python3 -c "import ast,sys; f=sys.argv[1]; ast.parse(open(f).read(), f)" plugin/xiayule.5m.py
```

非要用会写字节码的工具，把产物丢到别处：

```bash
export PYTHONPYCACHEPREFIX="${TMPDIR:-/tmp/}pycache"
```

注意那个 `:-/tmp/` 兜底——`TMPDIR` 未设时 `"${TMPDIR}pycache"` 会变成当前目录下的相对路径，等于没改。

## 免费版 QPS = 1

下拉菜单顶部偶尔出现橙色的「取数失败」横幅，最常见的原因是 HTTP 429 `Rate limit exceeded`。

实测：同一秒内发两个请求，第二个必定 429；间隔 1 秒就正常。SwiftBar 重启、手动刷新撞上 5 分钟定时、系统唤醒补跑，都可能让两次请求挤进同一秒。

插件的退避重试是 0 秒、1 秒、3 秒，那个 1 秒重试正好能清掉这种限流，所以通常只会看到一闪而过的橙色横幅，数据仍然是好的。真实状态码可以在 `~/.cache/xiayule/errors.log` 里查（保留最近 50 条）。

如果日志里频繁出现 `400` 加 quota 字样，那是每日额度用完了，把文件名改成 `.15m.py` 降频。

容错的完整策略：429/5xx/网络异常退避重试三次，4xx 是自己的问题不重试；仍然失败就拿最近一次成功的数据顶班，顶部横幅标明数据是几分钟前的，展开能看具体错误和跳转日志；缓存超过 2 小时或者压根没有，才显示错误卡片。用缓存顶班时会按响应里的 `server_time` 校正漂移，所以「还有几分钟停」不会因为数据是十分钟前的就算错。

## 彩云 API

一次请求打包拿全：

```
GET https://api.caiyunapp.com/v2.6/{token}/{经度},{纬度}/weather
    ?alert=true&dailysteps=3&hourlysteps=24&unit=metric:v2
```

`unit=metric:v2` 让所有降水强度以 mm/h 返回，然后按官方分档表判定雨档：分钟级 ≥0.08 小雨、≥3.44 中雨、≥11.33 大雨、≥51.30 暴雨；小时级 ≥0.0606 算有雨。

阈值在代码里只有一处出处（`RAIN_TIERS`），图标、档名、雨雪相态、sparkline 的柱高全部由它驱动。

「下雨时段」是把降水序列扫成连续区间得到的，跨天自动标「明天」，下不停的用开区间措辞（「18时起有雨，24小时内不停」）。分钟级的 sparkline 按每 5 分钟取峰值而不是抽样——抽样会漏掉只下三分钟的短阵雨，画出来的图和上面的文字自相矛盾。

token 不会打印到菜单里：格式非法时只报字符数不回显内容，网络异常信息里出现 token 一律替换成 `***`。

想换数据源的话，和风天气的免费开发者版有分钟级降水（`/v7/minutely/5m`），照着 `main()` 里的解析逻辑改就行，渲染部分不用动。

## 调试

```bash
./plugin/xiayule.5m.py                   # 直接跑，看输出文本
open -g "swiftbar://refreshallplugins"   # 让 SwiftBar 立即刷新
python3 test_plugin.py                   # 65 项回归测试，纯 mock
```

SwiftBar 自己有诊断报告，里面有插件候选清单、加载状态、错误信息，出问题先看它：

```bash
cat ~/Library/Application\ Support/SwiftBar/Diagnostics/latest-system-report.txt
```

测试里有一组插件目录卫生断言。最硬的一条是直接比对 `os.listdir(plugin/)`——不依赖任何对 SwiftBar 语义的建模，塞进去东西就报错。另外几条用复刻的发现逻辑验证插件目录和仓库根目录都只会加载真插件，35 个杂物做穿透测试。

那个复刻实现有个容易写错的地方：Python 的 `re.escape` 不转义 `/`，Foundation 的会。不补上这个差异，模型就比真实 SwiftBar 宽松，测试会在有 bug 的规则上照样变绿——这坑我踩过一次，规则里的 `dir/**/*` 就是这么混过测试上线的。现在模型和一份逐行移植的 Swift oracle 在三棵目录树上逐文件对齐过。
