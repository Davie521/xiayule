#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""下雨了么 · 回归测试套件（纯 mock，不碰真实 API / 不污染插件目录）

    python3 test_plugin.py

本文件用 importlib 把插件当模块加载，默认会在 plugin/ 旁边生成 __pycache__，
而 SwiftBar 会把插件目录里的文件都执行一遍，于是菜单栏冒出方框问号。
下面第一行代码就关掉字节码写入，所以不需要靠人记得设环境变量。
"""
import sys

sys.dont_write_bytecode = True  # 必须在 import 插件之前，别挪到下面去

import importlib.util  # noqa: E402
import io  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import time  # noqa: E402
import urllib.error  # noqa: E402

REPO = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.join(REPO, "plugin")
PLUGIN = os.path.join(PLUGIN_DIR, "xiayule.5m.py")
os.environ["CAIYUN_TOKEN"] = "mocktoken123"

FAILURES = []
PASSED = 0


def load():
    spec = importlib.util.spec_from_file_location("xiayule", PLUGIN)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.RETRY_DELAYS = (0, 0.01, 0.02)  # 测试时不真睡
    m.CACHE_FILE = "/tmp/xy-test-cache.json"
    m.ERR_LOG = "/tmp/xy-test-errors.log"
    m.CACHE_DIR = "/tmp"
    return m


class FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


def serve(m, payload):
    m.urllib.request.urlopen = lambda url, timeout=None: FakeResp(json.dumps(payload).encode())


def raise_http(m, code, body=b'{"error":"boom"}', counter=None):
    def f(url, timeout=None):
        if counter is not None:
            counter.append(1)
        raise urllib.error.HTTPError(url, code, "err", {}, io.BytesIO(body))
    m.urllib.request.urlopen = f


def run(m):
    """跑 main()，捕获 stdout → 行列表"""
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        m.main()
    finally:
        sys.stdout = old
    return buf.getvalue().splitlines()


def check(name, cond, detail=""):
    global PASSED
    if cond:
        PASSED += 1
        print(f"  ✓ {name}")
    else:
        FAILURES.append(f"{name}  {detail}")
        print(f"  ✗ {name}  {detail}")


def hourly(vals, start_hour=16, day=16):
    out = []
    for i, v in enumerate(vals):
        h = start_hour + i
        d = day + h // 24
        out.append({"datetime": f"2026-08-{d:02d}T{h % 24:02d}:00+08:00",
                    "value": v, "probability": 80 if v > 0.06 else 5})
    return out


def base(**over):
    p = {
        "status": "ok", "tzshift": 28800, "server_time": time.time(),
        "result": {
            "realtime": {"temperature": 26, "apparent_temperature": 30, "humidity": 0.8,
                         "skycon": "CLOUDY",
                         "precipitation": {"local": {"intensity": 0}, "nearest": {"distance": 120}},
                         "wind": {"speed": 10, "direction": 90},
                         "air_quality": {"aqi": {"chn": 30}}},
            "hourly": {"precipitation": hourly([0.0] * 24),
                       "temperature": [{"datetime": h["datetime"], "value": 25} for h in hourly([0] * 24)],
                       "skycon": [{"datetime": h["datetime"], "value": "CLOUDY"} for h in hourly([0] * 24)]},
            "daily": {"temperature": [{"min": 24, "max": 29}] * 3,
                      "skycon": [{"value": "CLOUDY"}] * 3,
                      "precipitation": [{"probability": 1}, {"probability": 80}, {}]},
            "forecast_keypoint": "多云"}}
    p["result"].update(over)
    return p


print("=" * 62)
print("A. 菜单栏标题状态机")
print("=" * 62)

m = load()
# A1 无雨 → 天气图标+温度
serve(m, base())
out = run(m)
check("A1 无雨显示温度", out[0] == ":cloud.fill: 26°", out[0])

# A2 小时级：3 小时内有雨 → 起止时段
p = base()
for h in p["result"]["hourly"]["precipitation"][2:5]:
    h["value"] = 1.0
serve(m, p)
out = run(m)
check("A2 小时级雨伞时段", out[0] == ":umbrella.fill: 18-21时雨", out[0])

# A3 小时级：雨下到 24h 边界外 → 「起雨」
p = base()
for h in p["result"]["hourly"]["precipitation"][2:]:
    h["value"] = 1.0
serve(m, p)
out = run(m)
check("A3 开区间起雨", out[0] == ":umbrella.fill: 18时起雨", out[0])

# A4 超出 SOON_HOURS 的雨不亮伞
p = base()
for h in p["result"]["hourly"]["precipitation"][6:9]:
    h["value"] = 1.0
serve(m, p)
out = run(m)
check("A4 远处的雨不亮伞", out[0] == ":cloud.fill: 26°", out[0])

# A5 正在下雨 + 小时级停雨点
p = base()
p["result"]["realtime"]["skycon"] = "MODERATE_RAIN"
p["result"]["realtime"]["precipitation"]["local"]["intensity"] = 5.0
for h in p["result"]["hourly"]["precipitation"][:3]:
    h["value"] = 5.0
serve(m, p)
out = run(m)
check("A5 下雨中显示停雨钟点", out[0] == ":cloud.rain.fill: 19时停", out[0])

# A6 在下雨但小时级说现在没雨 → 不显示过去时间
p = base()
p["result"]["realtime"]["skycon"] = "MODERATE_RAIN"
p["result"]["realtime"]["precipitation"]["local"]["intensity"] = 5.0
serve(m, p)
out = run(m)
check("A6 不显示过去的停雨时间", out[0] == ":cloud.rain.fill: 中雨", out[0])

# A7 分钟级：N 分后有雨
p = base()
p["result"]["minutely"] = {"status": "ok", "precipitation_2h": [0.0] * 25 + [2.0] * 95,
                           "probability": [0.1, 0.9, 0.8, 0.5]}
serve(m, p)
out = run(m)
check("A7 分钟级 25 分后雨", out[0] == ":umbrella.fill: 25分后雨", out[0])

# A8 分钟级 stop_min==0（假值陷阱）
p = base()
p["result"]["realtime"]["skycon"] = "LIGHT_RAIN"
p["result"]["minutely"] = {"status": "ok", "precipitation_2h": [0.0] * 120, "probability": [0] * 4}
serve(m, p)
out = run(m)
check("A8 stop_min=0 不被吞", out[0] == ":cloud.drizzle.fill: 1分停", out[0])

# A9 雪相态
p = base()
p["result"]["realtime"]["skycon"] = "LIGHT_SNOW"
p["result"]["realtime"]["precipitation"]["local"]["intensity"] = 1.2
serve(m, p)
out = run(m)
check("A9 雪用雪图标雪文案", out[0] == ":cloud.snow.fill: 小雪", out[0])
check("A9b 雪强文案不说雨", any("当前雪强" in l for l in out), "")

# A10 付费层分钟级 2h 干 + 小时级 2-3h 有雨 → 仍亮伞
p = base()
p["result"]["minutely"] = {"status": "ok", "precipitation_2h": [0.0] * 120, "probability": [0] * 4}
for h in p["result"]["hourly"]["precipitation"][2:5]:
    h["value"] = 1.0
serve(m, p)
out = run(m)
check("A10 付费层不丢 3 小时预警", out[0] == ":umbrella.fill: 18-21时雨", out[0])

print()
print("=" * 62)
print("B. 空值 / 畸形数据免疫")
print("=" * 62)

# B1 体感温度 null
p = base()
p["result"]["realtime"]["apparent_temperature"] = None
serve(m, p)
out = run(m)
check("B1 体感 null 不崩", not any("插件异常" in l for l in out))
check("B1b 体感 null 时不显示体感", not any("体感" in l for l in out))

# B2 湿度 null → 不显示 0%
p = base()
p["result"]["realtime"]["humidity"] = None
serve(m, p)
out = run(m)
check("B2 湿度 null 不显示 0%", not any("0%" in l and "humidity" in l for l in out))

# B3 逐小时温度 null
p = base()
p["result"]["hourly"]["temperature"][2]["value"] = None
serve(m, p)
out = run(m)
check("B3 逐小时 null 不崩", not any("插件异常" in l for l in out))
check("B3b 后续区块仍完整", any("打开彩云雷达图" in l for l in out))

# B4 daily min/max 缺失 → 跳过该行不编 0-0
p = base()
p["result"]["daily"]["temperature"][1] = {"min": None, "max": 30}
serve(m, p)
out = run(m)
check("B4 daily null 不渲染 0–0°", not any("0–0°" in l for l in out))
check("B4b 其余日仍显示", sum(1 for l in out if "–" in l and "°" in l) >= 2)

# B5 hourly datetime 缺失
p = base()
del p["result"]["hourly"]["precipitation"][3]["datetime"]
for h in p["result"]["hourly"]["precipitation"][2:5]:
    h["value"] = 1.0
serve(m, p)
out = run(m)
check("B5 datetime 缺失不崩", not any("插件异常" in l for l in out))

# B6 整个 realtime 为空
p = base()
p["result"]["realtime"] = {}
serve(m, p)
out = run(m)
check("B6 realtime 空不崩", not any("插件异常" in l for l in out))

# B7 result 只有 realtime
p = {"status": "ok", "tzshift": 28800, "server_time": time.time(),
     "result": {"realtime": {"temperature": 20, "skycon": "CLEAR_DAY"}}}
serve(m, p)
out = run(m)
check("B7 极简响应不崩", out and out[0] == ":sun.max.fill: 20°", out[0] if out else "空")

print()
print("=" * 62)
print("C. 错误处理 / 重试 / 缓存顶班")
print("=" * 62)

# 先建一份好缓存
serve(m, base())
run(m)
check("C0 成功后写缓存", os.path.exists(m.CACHE_FILE))

# C1 429 重试 3 次
cnt = []
raise_http(m, 429, b'{"error":"Rate limit exceeded"}', cnt)
out = run(m)
check("C1 429 重试 3 次", len(cnt) == 3, f"实际 {len(cnt)}")
check("C1b 429 后用缓存顶班", any("取数失败" in l for l in out) and any("徐泾" in l for l in out))

# C2 500 重试
cnt2 = []
raise_http(m, 500, b'{"error":"oops"}', cnt2)
run(m)
check("C2 500 重试 3 次", len(cnt2) == 3, f"实际 {len(cnt2)}")

# C3 400 不重试
cnt3 = []
raise_http(m, 400, b'{"error":"token is invalid"}', cnt3)
run(m)
check("C3 400 只试 1 次", len(cnt3) == 1, f"实际 {len(cnt3)}")

# C4 离线横幅在最顶部
raise_http(m, 503)
out = run(m)
idx_banner = next((i for i, l in enumerate(out) if "取数失败" in l), -1)
check("C4 离线横幅置顶", idx_banner == 2, f"位置 {idx_banner}")

# C5 缓存过期 → 报错卡片
blob = json.load(open(m.CACHE_FILE))
blob["ts"] = time.time() - 3 * 3600
json.dump(blob, open("/tmp/xy-old-cache.json", "w"))
old_cache = m.CACHE_FILE
m.CACHE_FILE = "/tmp/xy-old-cache.json"
raise_http(m, 500)
out = run(m)
check("C5 缓存超 2h 报错", out[0].startswith(":exclamationmark.triangle.fill:"), out[0])
m.CACHE_FILE = old_cache

# C6 无缓存 → 报错卡片
m.CACHE_FILE = "/tmp/xy-nonexistent.json"
raise_http(m, 500)
out = run(m)
check("C6 无缓存报错", out[0].startswith(":exclamationmark.triangle.fill:"), out[0])
m.CACHE_FILE = old_cache

# C7 业务层 status=failed
serve(m, {"status": "failed", "error": "token is invalid"})
out = run(m)
check("C7 业务层错误用缓存", any("取数失败" in l for l in out))

# C8 error 字段为 null
serve(m, {"status": "failed", "error": None})
out = run(m)
check("C8 error=null 不崩", not any("插件异常" in l for l in out))

# C9 error 字段是 dict
serve(m, {"status": "failed", "error": {"code": 500}})
out = run(m)
check("C9 error=dict 不崩", not any("插件异常" in l for l in out))

# C10 网络异常（非 HTTP）
def boom(url, timeout=None):
    raise OSError("Network is down")
m.urllib.request.urlopen = boom
out = run(m)
check("C10 网络异常不崩", not any("插件异常" in l for l in out))

# C11 token 不回显在错误里
def boom_token(url, timeout=None):
    raise OSError(f"failed connecting to {url}")
m.urllib.request.urlopen = boom_token
m.CACHE_FILE = "/tmp/xy-nonexistent.json"
out = run(m)
check("C11 token 不泄露", not any("mocktoken123" in l for l in out), "\n".join(out))
m.CACHE_FILE = old_cache

# C12 非法 token 格式（含换行）→ 不回显内容
m2 = load()
os.environ["CAIYUN_TOKEN"] = "bad token\nwith newline"
out = run(m2)
check("C12 非法 token 拒绝且不回显",
      "token 格式不对" in out[0] and not any("bad token" in l for l in out), out[0])
os.environ["CAIYUN_TOKEN"] = "mocktoken123"

print()
print("=" * 62)
print("D. 缓存顶班时的时间正确性（server_time 漂移校正）")
print("=" * 62)

m3 = load()
m3.CACHE_FILE = "/tmp/xy-drift-cache.json"
# 造一份 30 分钟前的缓存：分钟级前 40 分钟有雨
p = base()
p["server_time"] = time.time() - 30 * 60
p["result"]["minutely"] = {"status": "ok",
                           "precipitation_2h": [2.0] * 40 + [0.0] * 80,
                           "probability": [0.9, 0.5, 0, 0]}
p["result"]["realtime"]["skycon"] = "LIGHT_RAIN"
json.dump({"ts": time.time() - 30 * 60, "data": p}, open(m3.CACHE_FILE, "w"))
raise_http(m3, 500)
out = run(m3)
# 30 分钟漂移后，原本 40 分钟的雨只剩 10 分钟
check("D1 漂移校正后剩余雨时正确", out[0] == ":cloud.drizzle.fill: 10分停", out[0])
check("D2 离线横幅显示 30 分钟前", any("30 分钟前" in l for l in out),
      next((l for l in out if "取数失败" in l), ""))

print()
print("=" * 62)
print("E. SwiftBar 输出格式合法性")
print("=" * 62)

m4 = load()
# E1 管道符清洗
p = base()
p["result"]["forecast_keypoint"] = "有|管道符\n和换行"
serve(m4, p)
out = run(m4)
kp = out[2]
check("E1 keypoint 清洗管道符", "|管道符" not in kp and "｜管道符" in kp, kp)
check("E2 keypoint 无裸换行", len([l for l in out if "和换行" in l]) == 1)

# E3 地名含管道符
os.environ["VAR_PLACE"] = "徐泾|家"
m5 = load()
serve(m5, base())
out = run(m5)
check("E3 地名清洗", any("徐泾｜家" in l for l in out), next((l for l in out if "徐泾" in l), ""))
del os.environ["VAR_PLACE"]

# E4 预警标题清洗
m6 = load()
p = base()
p["result"]["alert"] = {"content": [{"title": "雷电|黄色预警"}]}
serve(m6, p)
out = run(m6)
check("E4 预警清洗", any("雷电｜黄色预警" in l for l in out))

# E5 第一行永远是菜单栏标题（不含分隔符）
check("E5 首行是标题", out[0] != "---" and out[1] == "---", out[0])

# E6 VAR_LOC 畸形回落
os.environ["VAR_LOC"] = "garbage"
m7 = load()
check("E6 VAR_LOC 畸形回落徐泾", (m7.LON, m7.LAT) == (121.2760, 31.1760), f"{m7.LON},{m7.LAT}")
os.environ["VAR_LOC"] = "121.5,31.2"
m8 = load()
check("E7 VAR_LOC 正常解析", (m8.LON, m8.LAT) == (121.5, 31.2), f"{m8.LON},{m8.LAT}")
del os.environ["VAR_LOC"]

print()
print("=" * 62)
print("F. 纯函数单元测试")
print("=" * 62)

m9 = load()
check("F1 rain_periods 单段", m9.rain_periods([0, 1, 1, 0], 0.5) == [(1, 3)])
check("F2 rain_periods 多段", m9.rain_periods([1, 0, 1, 1, 0, 1], 0.5) == [(0, 1), (2, 4), (5, 6)])
check("F3 rain_periods 开区间", m9.rain_periods([0, 1, 1], 0.5) == [(1, 3)])
check("F4 rain_periods 全干", m9.rain_periods([0, 0], 0.5) == [])
check("F5 分档小雨", m9.precip_sf(1.0)[1] == "小雨")
check("F6 分档中雨", m9.precip_sf(5.0)[1] == "中雨")
check("F7 分档大雨", m9.precip_sf(20.0)[1] == "大雨")
check("F8 分档暴雨", m9.precip_sf(60.0)[1] == "暴雨")
check("F9 雪相态分档", m9.precip_sf(5.0, snow=True)[1] == "中雪")
check("F10 pct01", m9.pct01(0.85) == 85 and m9.pct01(None) is None)
check("F11 pct100 不把 1 变 100", m9.pct100(1) == 1)
check("F12 spark 干湿", m9.spark([0, 1, 5, 20, 60], 0.5) == "▁▂▄▆█", m9.spark([0, 1, 5, 20, 60], 0.5))
check("F13 aqi 分级", m9.aqi_grade(42) == "优" and m9.aqi_grade(120) == "轻度污染")
check("F14 clean 管道符", m9.clean("a|b\nc") == "a｜b c")

print()
print("=" * 62)
print("G. 插件目录卫生（防菜单栏问号）")
print("=" * 62)


def glob_to_regex(pattern):
    """复刻 SwiftBar shouldBeIgnored 的 glob→正则转换（PluginManger.swift v2.1.1）"""
    import re
    p = re.escape(pattern)
    p = p.replace(r"\*\*/", "(.*/)?").replace(r"\*", "[^/]*").replace(r"\?", "[^/]")
    return re.compile(r"^" + p + r"$")


def swiftbar_would_load(root):
    """复刻 SwiftBar 的插件发现：递归、跳过隐藏、排除 .json/空文件、应用 .swiftbarignore"""
    import re
    patterns = []
    ig = os.path.join(root, ".swiftbarignore")
    if os.path.exists(ig):
        patterns = [l.strip() for l in open(ig)
                    if l.strip() and not l.strip().startswith("#")]
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for fn in filenames:
            if fn.startswith("."):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root)
            if fn.lower().endswith(".json") or not os.path.isfile(full) or os.path.getsize(full) == 0:
                continue
            if any(fn == p or rel == p or glob_to_regex(p).match(fn) or glob_to_regex(p).match(rel)
                   for p in patterns):
                continue
            found.append(rel)
    return sorted(found)


# G1 插件目录里除了脚本本身没有别的可执行候选
loaded = swiftbar_would_load(PLUGIN_DIR)
check("G1 插件目录只加载脚本本身", loaded == ["xiayule.5m.py"], f"实际 {loaded}")

# G2 万一 SwiftBar 被指到仓库根目录，也只加载真插件
loaded_root = swiftbar_would_load(REPO)
check("G2 指到仓库根目录也安全", loaded_root == ["plugin/xiayule.5m.py"], f"实际 {loaded_root}")

# G3 常见杂物确实会被排除（含凭据文件——被执行是安全问题）
import tempfile
with tempfile.TemporaryDirectory() as td:
    import shutil
    shutil.copy(os.path.join(PLUGIN_DIR, ".swiftbarignore"), os.path.join(td, ".swiftbarignore"))
    strays = ["__pycache__/x.pyc", "__pycache__/NOTAPYC", "__pycache__/stale.5m.sh",
              "token", "creds.token", "id.pem", "notes.txt", "README.md",
              "x.py~", "x.py.bak", "x.py.orig", "x.py.rej", "x.py.swp", "run.log",
              "build/a/b.sh", "dist/x.sh", "htmlcov/i.html", "test_x.py"]
    for s in strays:
        p = os.path.join(td, s)
        os.makedirs(os.path.dirname(p), exist_ok=True) if os.path.dirname(s) else None
        with open(p, "w") as f:
            f.write("stray\n")
    with open(os.path.join(td, "real.5m.sh"), "w") as f:
        f.write("#!/bin/sh\necho hi\n")
    leaked = swiftbar_would_load(td)
    check("G3 杂物全部被排除，只剩真插件", leaked == ["real.5m.sh"], f"漏网 {leaked}")

# G4 本测试自身不会在插件目录留下字节码
check("G4 测试不写字节码", sys.dont_write_bytecode is True)
check("G5 插件目录无 __pycache__", not os.path.exists(os.path.join(PLUGIN_DIR, "__pycache__")))

print()
print("=" * 62)
for f in ("/tmp/xy-test-cache.json", "/tmp/xy-old-cache.json", "/tmp/xy-drift-cache.json",
          "/tmp/xy-test-errors.log"):
    if os.path.exists(f):
        os.remove(f)
total = PASSED + len(FAILURES)
if FAILURES:
    print(f"结果：{PASSED}/{total} 通过，{len(FAILURES)} 项失败")
    for f in FAILURES:
        print(f"  ✗ {f}")
    sys.exit(1)
print(f"结果：全部 {total} 项通过 ✅")
