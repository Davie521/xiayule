# 下雨了么

macOS 菜单栏天气插件。不告诉你「今天有雨」，告诉你几点下、几点停。

<p align="center">
  <img src="docs/menubar.png" width="200" alt="菜单栏显示「18-22时雨」">
</p>

没雨的时候它只是个温度。雨快来了亮起雨伞和时段，正在下雨时告诉你还有多久停。抬眼一次就知道要不要带伞。

数据来自[彩云天气](https://caiyunapp.com/)，1km 网格、雷达外推。跑在 [SwiftBar](https://github.com/swiftbar/SwiftBar) 上，纯 Python 标准库，没有任何依赖。

## 菜单栏长什么样

- 没雨：`☀️ 28°`
- 三小时内有雨：`☂ 18-22时雨`（下不停就是 `18时起雨`）
- 正在下雨：`🌧 46分停`

点开是实时天气、最近的降水带在几公里外、下雨时段、24 小时降水柱状图、三日预报。有气象预警会多一条橙色的。下雪会自动换成雪的图标和文案，不会把雪说成雨。

## 装

```bash
brew install --cask swiftbar
git clone https://github.com/Davie521/xiayule.git
cd xiayule && ./install.sh
```

`install.sh` 把脚本拷到 `~/Library/Application Support/xiayule/plugin/`，再把 SwiftBar 的插件目录指过去。**跑起来的是那份副本，不是仓库里这份**——所以仓库随便挪、随便改名都不会让菜单栏变空（[为什么这么装](docs/notes.md#跑的是副本不是仓库)）。代价是改完代码要重跑一次 `./install.sh` 才生效。

然后去 [platform.caiyunapp.com](https://platform.caiyunapp.com/) 注册领 token，创建应用时类型选「天气」，免费版够用。点菜单栏那个钥匙图标，按提示把 token 粘进去。

最后改位置。默认坐标在上海青浦徐泾（作者家门口），装完第一件事就是改掉。SwiftBar 菜单 → Preferences → Plugins → 选中插件：

| 变量 | 说明 |
|---|---|
| `VAR_LOC` | `经度,纬度`，经度在前。[高德坐标拾取器](https://lbs.amap.com/tools/picker)给的格式正好能直接粘 |
| `VAR_PLACE` | 下拉菜单里显示的地名 |
| `VAR_CAIYUN_TOKEN` | 填了就用它，留空则读 `~/.config/caiyun/token` |

刷新频率写在文件名里：`xiayule.5m.py` 是 5 分钟一次，288 次/天。嫌费额度就改名成 `.15m.py`。

## 免费版拿不到分钟级

彩云的分钟级降水和气象预警属于企业套餐的增值项，免费 token 没有。插件会降级到小时级，并在页脚灰字标一句「时段为小时级精度」——不假装自己有分钟级数据。

区别在精度：时段是 `18:00–22:00` 而不是 `15:31–16:01`，菜单栏是 `18-22时雨` 而不是 `25分后雨`。判断要不要带伞够用了。

## 别的

网络抖动、彩云偶发 5xx、免费版的 QPS 限流，都不会让菜单栏变成错误卡片。插件会退避重试，还不行就拿上一次成功的数据顶班，并在下拉菜单顶部标明这是几分钟前的。失败记录留在 `~/.cache/xiayule/errors.log`。

跑测试：`python3 test_plugin.py`，65 项，纯 mock 不打真实 API。CI（`.github/workflows/ci.yml`）在 Python 3.9 和 3.14 上各跑一遍——3.9 是 macOS 自带的那个 `/usr/bin/python3`，插件 shebang 写的是 `env python3`，而 SwiftBar 给插件的 PATH 未必包含 homebrew，所以下限得真跑过才算数。

剩下的细节——SwiftBar 的插件扫描规则、菜单栏那个方框问号到底是什么、彩云 API 的雨强分档、调试命令——都在 [docs/notes.md](docs/notes.md)。

## 卸载

删掉 `~/Library/Application Support/xiayule/`（缓存另在 `~/.cache/xiayule/`，一起删），然后：

```bash
defaults delete com.ameba.SwiftBar PluginDirectory
killall SwiftBar; open -a SwiftBar
```

第二步不能省。`install.sh` 改的是 SwiftBar 的**全局偏好**，只删目录的话它会一直指着一个不存在的路径——而那个状态是静默的：诊断报告写 `Plugin Directory: none`、`Loaded Plugins: 0`，SwiftBar 拿自己的图标顶住菜单栏那个位置，看起来不像出了事。

删掉偏好之后 SwiftBar 再启动会弹一个 **Set SwiftBar Plugins Location**（"Select a folder to store the plugins repository"）。这是正常的——它在问插件放哪。真要卸载就选 `Quit SwiftBar`；还想留着 SwiftBar 跑别的插件，就 `OK` 然后指给它新目录。

## License

MIT
