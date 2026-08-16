# 下雨了么

> macOS 菜单栏天气插件 —— 不是告诉你「今天有雨」，而是告诉你**几点下、几点停**。

<img src="docs/menubar.png" width="106" alt="菜单栏显示 18-22时雨">

抬眼看一次就知道要不要带伞。没雨的时候它只是个安静的温度；雨快来了亮起雨伞和时段；正在下雨时告诉你还有几分钟停。

数据来自 [彩云天气](https://caiyunapp.com/)（国内 1km 网格、雷达外推），跑在 [SwiftBar](https://github.com/swiftbar/SwiftBar) 上，纯 Python 标准库，无依赖。

## 菜单栏三种形态

| 天气 | 显示 | 说明 |
|---|---|---|
| 没雨 | `☀️ 28°` | 图标跟随天气现象（晴/多云/阴/雾/霾…），最安静的形态 |
| 3 小时内有雨 | `☂ 18-22时雨` | 起止时段直接挂在菜单栏；雨下不停则显示 `18时起雨` |
| 正在下雨 | `🌧 46分停` | 雨强分档图标 + 停雨时间（无分钟级权限时显示 `22时停`） |

下雪自动换雪花图标和「雪」文案，不会把雪说成雨。

## 下拉菜单

真实输出（渲染后图标为 SF Symbols）：

```
多云，今天傍晚18点钟后转小雨，其后多云      ← 彩云的人话预报
────────────────────────────────
🌡 徐泾 29°（体感 32°）  💧76%  多云
🌬 东北风 7 km/h
📍 最近降水带 16.2 km 外，强度 1.57 mm/h    ← 雷达覆盖区特供
🌫 AQI 13（优）
────────────────────────────────
🌧 18:00–22:00  小雨                        ← 下雨时段，多段雨分开列
📊 24小时降水 ▁▁▂▂▂▂▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁     ← 降水时间轴，柱高=雨强
未来24小时…  ▸                              ← 子菜单：逐2小时图标+温度+☂概率
────────────────────────────────
今天  🌦 25–29°  小雨  ☂60%
明天  ⛅️ 25–31°  多云
后天  ⛅️ 26–32°  多云
────────────────────────────────
🗺 打开彩云雷达图
🔄 刷新
更新于 16:17 · 时段为小时级精度（分钟级未开通）
```

有气象预警时会多出一行橙色的预警条目。

## 网络抖动不会打断你

每 5 分钟请求一次，总会撞上偶发的网络切换、系统唤醒、彩云 5xx。这时插件**不会**把菜单栏变成错误卡片：

1. 429 / 5xx / 网络异常自动退避重试（立即、1 秒、3 秒）；4xx 是自己的问题，不做无谓重试
2. 仍然失败就用最近一次成功的数据顶班，下拉菜单顶部橙色横幅说明「取数失败，下面是 N 分钟前的数据」，展开可看具体错误、跳转失败日志、立即重试
3. 缓存超过 2 小时或压根没有，才显示错误卡片

失败记录留在 `~/.cache/xiayule/errors.log`（最近 50 条），偶发故障有迹可循。

## 安装

**1. 装 SwiftBar**

```bash
brew install --cask swiftbar
```

**2. 拉仓库**

```bash
git clone https://github.com/Davie521/xiayule.git ~/Desktop/xiayule
```

仓库结构：`plugin/` 里只有插件脚本本身和一个 `.swiftbarignore`，README/LICENSE/docs 都在仓库根目录——原因见下方 FAQ。

**3. 把 SwiftBar 的插件目录指向 `plugin/`**

首次启动 SwiftBar 会问你要插件目录，选仓库里的 **`plugin/`** 子目录（不是仓库根目录，原因见下方 FAQ）。或者命令行设：

```bash
defaults write com.ameba.SwiftBar PluginDirectory "$HOME/Desktop/xiayule/plugin"
killall SwiftBar; open -a SwiftBar
```

**4. 领一个彩云 API token**

去 [platform.caiyunapp.com](https://platform.caiyunapp.com/) 注册 → 创建应用（类型选「天气」）→ 复制 token。免费版够用。

然后点菜单栏的 🔑 图标，按三步引导把 token 粘贴进 `~/.config/caiyun/token` 即可（文件会自动创建，权限 600）。

**5. 改成你自己的位置**

默认坐标是作者所在的上海青浦徐泾，**装完第一件事就是改掉它**：

SwiftBar 菜单 → Preferences → Plugins → 选中本插件 → 改 `VAR_LOC` 和 `VAR_PLACE`。

## 配置

全部在 SwiftBar 的插件变量面板里改，不用动代码：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `VAR_LOC` | `121.2760,31.1760` | 位置「经度,纬度」（**经度在前**，彩云 API 的顺序）。填错格式会安全回落 |
| `VAR_PLACE` | `徐泾` | 显示在下拉菜单里的地点名 |
| `VAR_CAIYUN_TOKEN` | 空 | 填了就用它，留空则读 `~/.config/caiyun/token` |

**刷新频率**由文件名决定：`xiayule.5m.py` = 5 分钟一次（对齐彩云分钟级数据 ~5 分钟的发布周期），约 288 次/天。免费额度不够就改名成 `xiayule.15m.py`。

**怎么查自己的坐标**：[高德坐标拾取器](https://lbs.amap.com/tools/picker) 拿到的是「经度,纬度」，格式正好可以直接粘。

## 免费版能拿到什么

彩云的**分钟级降水**（`minutely`）和**气象预警**（`alert`）属于企业套餐增值项，免费 token 拿不到。插件对此做了完整降级，两种套餐都能正常用：

| | 免费版 | 有分钟级权限 |
|---|---|---|
| 下雨时段 | 小时精度 `18:00–22:00` | **分钟精度** `15:31–16:01` |
| 菜单栏 | `18-22时雨` / `22时停` | `25分后雨` / `46分停` |
| 降水概率 | 逐小时 ☂60% | 未来 2 小时四段概率 |
| 气象预警 | 无 | 有 |

免费版下页脚会灰字标注「时段为小时级精度」，不会假装自己有分钟级数据。

## 工作原理

一次请求打包拿全：

```
GET https://api.caiyunapp.com/v2.6/{token}/{经度},{纬度}/weather
    ?alert=true&dailysteps=3&hourlysteps=24&unit=metric:v2
```

`unit=metric:v2` 让所有降水强度以 **mm/h** 返回，然后按彩云官方分档表判定雨档：

| mm/h（分钟级） | 档位 | mm/h（小时级） |
|---|---|---|
| ≥ 0.08 | 小雨 | ≥ 0.0606 有雨 |
| ≥ 3.44 | 中雨 | |
| ≥ 11.33 | 大雨 | |
| ≥ 51.30 | 暴雨 | |

阈值在代码里只有一处出处（`RAIN_TIERS`），图标、档名、雨雪相态、sparkline 柱高全部由它驱动。

「下雨时段」是把降水序列扫成连续区间得到的，跨天自动标「明天」，下不停的用开区间措辞（「18时起有雨，24小时内不停」）。分钟级 sparkline 按每 5 分钟取**峰值**而非抽样，短阵雨不会被漏掉。

## FAQ

**菜单栏出现一个方框问号（❓）？**

那个「问号」其实是 **SwiftBar 的错误图标渲染失败**：插件执行失败时它把菜单栏标题设成 `􀇾`（U+1001FE，SF Symbols 私有区里的 `exclamationmark.triangle.fill`），但菜单栏字体没有这个码位的字形，回落到 `.LastResort` 字体后，私有区统一画成一个方框问号。所以看到 ❓ = **某个「插件」跑挂了**。

而挂掉的多半不是你的插件，是插件目录里根本不该被当插件的文件。SwiftBar 的扫描规则（`PluginManger.swift` 的 `getPluginList()` / `shouldLoadPluginFile`）比想象中激进——**任意深度**下满足以下条件的文件都会被加载执行：

- 非隐藏（`.skipsHiddenFiles`，点开头的跳过）
- 非 `.json`（唯一按扩展名排除的类型）
- 非空文件、是普通文件
- 未被 `.swiftbarignore` 匹配
- 目录内候选总数 < 50（超过会弹窗）

注意它用 `FileManager.enumerator(at:)` **递归**遍历，子目录里的文件照样算；`MakePluginExecutable` 默认开启，没有执行位的文件会被 `chmod +x`（`Plugin.makeScriptExecutable`）后执行。文件名里没有合法刷新间隔也照样加载，只是间隔变成「几乎不刷新」，但**仍会执行一次**——足够挂给你看。

本仓库的两道防线：

1. 脚本单独放 `plugin/` 子目录，README/LICENSE/docs 留在仓库根目录，物理隔离
2. `plugin/.swiftbarignore` 排除 `__pycache__`、`*.pyc` 等构建产物（实测有效：目录里放个 `.pyc`，SwiftBar 自动重扫后候选列表里没有它）

真混进杂物了：删掉即可。**不用重启 SwiftBar**——非 App Store 版（brew 安装的）有 `DirectoryObserver`，插件目录一变动就会在约 0.5 秒后自动重扫。反倒是菜单里的「Refresh all」不会重新扫描目录（`loadPlugins()` 只在 App Store 版的刷新路径里调用）。

**最容易踩的坑：`py_compile` 会偷偷生成 `__pycache__`**

`PYTHONDONTWRITEBYTECODE=1` **管不住** `python3 -m py_compile`（那个环境变量只影响 import 时的隐式字节码写入，不影响显式编译）。`importlib` 把插件当模块 import 来跑测试时同样会在源文件旁生成 `__pycache__`。

有了 `.swiftbarignore` 这些都不会再变成问号，但想让源码目录彻底干净，用下面调试小节里的命令。

**偶尔出现「取数失败」橙色横幅？**

这是正常的容错提示，不是故障。看 `~/.cache/xiayule/errors.log` 能查到每次失败的真实状态码。

最常见的是 **HTTP 429 `Rate limit exceeded`**：**免费版 QPS = 1**（实测：同一秒内发两个请求，第二个必定 429；间隔 1 秒就正常）。SwiftBar 重启、手动刷新撞上 5 分钟定时、系统唤醒补跑，都可能让两次请求挤在同一秒。插件的退避重试（1 秒那次）正好能清掉这种限流，所以你通常只会看到一闪而过的橙色横幅，数据仍然是好的。

如果日志里频繁出现 **400 + quota**，那是每日额度用完了，把文件名改成 `.15m.py` 降频。

**报错「彩云接口报错 / quota」？**

免费版有每日调用额度。5 分钟一刷是 288 次/天，如果同时还有别的应用共用这个 token 就可能超。去 [控制台](https://platform.caiyunapp.com/) 的「调用管理」看用量，或把刷新间隔调长。

**token 会泄露吗？**

不会打印到菜单里。脚本对 token 做了格式校验（非法格式只报字符数不回显内容），网络异常信息里出现 token 一律替换成 `***`。token 存在 `~/.config/caiyun/token`（权限 600），不在仓库里。

**能换成和风天气 / 其他数据源吗？**

目前只对接彩云。和风天气的免费开发者版**有分钟级降水**（`/v7/minutely/5m`），如果你需要分钟精度又不想付费，可以照着 `main()` 里的解析逻辑改数据源，渲染部分不用动。

**本地调试**

```bash
./plugin/xiayule.5m.py                   # 直接跑，看输出文本
open -g "swiftbar://refreshallplugins"   # 让 SwiftBar 立即刷新

# 语法检查：零产物，且报错会指出文件名（别用 py_compile，见上方 FAQ）
python3 -c "import ast,sys; f=sys.argv[1]; ast.parse(open(f).read(), f)" plugin/xiayule.5m.py

# 要跑 import 插件的测试时，把字节码丢到别处，源码目录保持干净
export PYTHONPYCACHEPREFIX="${TMPDIR}pycache"
```

出问题时先看 SwiftBar 自己的诊断报告，里面有插件候选清单、加载状态、错误信息：

```bash
cat ~/Library/Application\ Support/SwiftBar/Diagnostics/latest-system-report.txt
```

**回归测试**（58 项，纯 mock 不打真实 API，覆盖菜单栏状态机、空值免疫、重试/缓存顶班、时间漂移校正、输出格式清洗、纯函数）：

```bash
PYTHONPYCACHEPREFIX="${TMPDIR}pycache" python3 test_plugin.py
```

## License

MIT
