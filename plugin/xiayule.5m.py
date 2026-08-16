#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# <xbar.title>下雨了么</xbar.title>
# <xbar.version>v4.0</xbar.version>
# <xbar.author>Davie521</xbar.author>
# <xbar.author.github>Davie521</xbar.author.github>
# <xbar.desc>菜单栏彩云天气：几点下雨、几点雨停一眼看见。实时 + 下雨时段 + 降水 sparkline + 3日预报，SF Symbols 原生图标</xbar.desc>
# <xbar.dependencies>python3</xbar.dependencies>
# <xbar.abouturl>https://github.com/Davie521/xiayule</xbar.abouturl>
# <xbar.var>string(VAR_CAIYUN_TOKEN=""): 彩云 API token（留空则读 ~/.config/caiyun/token）</xbar.var>
# <xbar.var>string(VAR_LOC="121.2760,31.1760"): 位置「经度,纬度」</xbar.var>
# <xbar.var>string(VAR_PLACE="徐泾"): 地点名称</xbar.var>
# <swiftbar.hideAbout>true</swiftbar.hideAbout>
# <swiftbar.hideRunInTerminal>true</swiftbar.hideRunInTerminal>
# <swiftbar.hideLastUpdated>false</swiftbar.hideLastUpdated>
#
# 数据源：彩云天气 v2.6 综合接口（realtime + minutely + hourly + daily + alert 一次拿全）
#   GET https://api.caiyunapp.com/v2.6/{token}/{经度},{纬度}/weather
#   unit=metric:v2 → 降水强度单位 mm/h；分档见 RAIN_TIERS（官方对照表）
#   免费版套餐无 minutely / alert 块 → 自动用小时级兜底
# 注册领 key：https://platform.caiyunapp.com/

import json
import os
import re
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone

# ── 配置（可在 SwiftBar 偏好设置里改 VAR_*，不用动代码）──
_loc = os.environ.get("VAR_LOC", "").strip() or "121.2760,31.1760"
try:
    LON, LAT = (float(x) for x in _loc.split(","))
except ValueError:
    LON, LAT = 121.2760, 31.1760  # VAR_LOC 填错格式时回落徐泾
# 备用坐标：青浦城区 121.1241,31.1512  朱家角 121.0540,31.1110  赵巷 121.1830,31.1330
PLACE = (os.environ.get("VAR_PLACE", "").strip() or "徐泾").replace("|", "｜").replace("\n", " ")
TOKEN_FILE = os.path.expanduser("~/.config/caiyun/token")

MIN_RAIN = 0.08      # 分钟级有降水阈值 mm/h（彩云官方分档）
HOURLY_RAIN = 0.0606 # 小时级有降水阈值 mm/h
SOON_HOURS = 3       # 小时级预报几小时内有雨时，菜单栏也亮伞

# 降水强度分档（唯一出处）：(下限 mm/h, 雨(SF图标,名), 雪(SF图标,名))
RAIN_TIERS = [
    (51.30, ("cloud.bolt.rain.fill", "暴雨"), ("snowflake", "暴雪")),
    (11.33, ("cloud.heavyrain.fill", "大雨"), ("cloud.snow.fill", "大雪")),
    (3.44,  ("cloud.rain.fill", "中雨"),      ("cloud.snow.fill", "中雪")),
    (0.0,   ("cloud.drizzle.fill", "小雨"),   ("cloud.snow.fill", "小雪")),
]

# skycon → (SF Symbol, 中文)。图标族与苹果天气一致
SKYCON = {
    "CLEAR_DAY": ("sun.max.fill", "晴"), "CLEAR_NIGHT": ("moon.stars.fill", "晴"),
    "PARTLY_CLOUDY_DAY": ("cloud.sun.fill", "多云"), "PARTLY_CLOUDY_NIGHT": ("cloud.moon.fill", "多云"),
    "CLOUDY": ("cloud.fill", "阴"),
    "LIGHT_HAZE": ("sun.haze.fill", "轻度雾霾"), "MODERATE_HAZE": ("smoke.fill", "中度雾霾"),
    "HEAVY_HAZE": ("smoke.fill", "重度雾霾"),
    "LIGHT_RAIN": ("cloud.drizzle.fill", "小雨"), "MODERATE_RAIN": ("cloud.rain.fill", "中雨"),
    "HEAVY_RAIN": ("cloud.heavyrain.fill", "大雨"), "STORM_RAIN": ("cloud.bolt.rain.fill", "暴雨"),
    "FOG": ("cloud.fog.fill", "雾"),
    "LIGHT_SNOW": ("cloud.snow.fill", "小雪"), "MODERATE_SNOW": ("cloud.snow.fill", "中雪"),
    "HEAVY_SNOW": ("cloud.snow.fill", "大雪"), "STORM_SNOW": ("snowflake", "暴雪"),
    "DUST": ("sun.dust.fill", "浮尘"), "SAND": ("wind", "沙尘"), "WIND": ("wind", "大风"),
}
WIND_DIRS = ["北", "东北", "东", "东南", "南", "西南", "西", "西北"]


def clean(s):
    """SwiftBar 行格式清洗：| 会截断行吞掉参数，换行会冒出多余菜单行"""
    return str(s).replace("|", "｜").replace("\n", " ")


def precip_sf(mmh, snow=False):
    """按雨强分档 → (SF Symbol, 档位名)；snow=True 走雪相态"""
    for lo, rain_v, snow_v in RAIN_TIERS:
        if mmh >= lo:
            return snow_v if snow else rain_v
    return RAIN_TIERS[-1][2] if snow else RAIN_TIERS[-1][1]


def spark(values, wet_at):
    """降水序列 → Unicode 时间轴。干=▁，柱高按 RAIN_TIERS 分档"""
    bars = "▂▄▆█"

    def bar(v):
        if v < wet_at:
            return "▁"
        return bars[sum(v >= lo for lo, _, _ in RAIN_TIERS[:-1])]
    return "".join(bar(v) for v in values)


def rain_periods(vals, wet_at):
    """降水序列 → 连续有降水区间 [(起始下标, 结束下标exclusive)]"""
    periods, s = [], None
    for i, v in enumerate(vals):
        if v >= wet_at and s is None:
            s = i
        elif v < wet_at and s is not None:
            periods.append((s, i))
            s = None
    if s is not None:
        periods.append((s, len(vals)))
    return periods


def print_periods(vals, wet_at, icon, label, horizon_text, snow, now_at_zero=False):
    """把连续降水区间渲染成「beg–end 档位」行；开区间用 horizon_text"""
    word = "雪" if snow else "雨"
    for a, b in rain_periods(vals, wet_at)[:4]:
        lv = precip_sf(max(vals[a:b]), snow)[1]
        beg = "现在" if (a == 0 and now_at_zero) else label(a)
        if b >= len(vals):
            print(f":{icon}: {beg}起有{word}，{horizon_text}（峰值{lv}）")
        else:
            end = label(b)
            if beg.startswith("明天") and end.startswith("明天"):
                end = end[2:]
            print(f":{icon}: {beg}–{end}  {lv}")


def aqi_grade(aqi):
    for limit, name in ((50, "优"), (100, "良"), (150, "轻度污染"),
                        (200, "中度污染"), (300, "重度污染")):
        if aqi <= limit:
            return name
    return "严重污染"


def pct01(p):
    """0~1 刻度的概率（minutely.probability）→ 整数百分比"""
    return None if p is None else round(p * 100)


def pct100(p):
    """0~100 刻度的概率（hourly/daily probability）→ 整数百分比"""
    return None if p is None else round(p)


def get_token():
    tok = os.environ.get("VAR_CAIYUN_TOKEN", "").strip() or os.environ.get("CAIYUN_TOKEN", "").strip()
    if tok:
        return tok
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            return f.read().strip()
    return ""


def need_token():
    # 先把 token 文件建出来，方便菜单里一键打开填写
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    if not os.path.exists(TOKEN_FILE):
        open(TOKEN_FILE, "w").close()
    try:
        os.chmod(TOKEN_FILE, 0o600)
    except OSError:
        pass
    print(":key.fill: 彩云token")
    print("---")
    print("三步启用：")
    print(":1.circle: 注册领 API token | href=https://platform.caiyunapp.com/")
    print(f':2.circle: 打开 token 文件粘贴进去 | bash=/usr/bin/open param1=-t param2="{TOKEN_FILE}" terminal=false')
    print(":3.circle: 点这里刷新 | refresh=true")


def fail(title, detail):
    print(f":exclamationmark.triangle.fill: {title}")
    print("---")
    print(clean(detail))
    print(":arrow.clockwise: 刷新 | refresh=true")


def main():
    token = get_token()
    if not token:
        need_token()
        return
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,}", token):
        # 不回显 token 本身，避免异常格式的 key 泄露到菜单/截图里
        fail("token 格式不对", f"token 应为一行字母数字（当前 {len(token)} 字符，含空格/换行或非法字符），"
                              f"重新粘贴到 {TOKEN_FILE}")
        return

    url = (f"https://api.caiyunapp.com/v2.6/{token}/{LON},{LAT}/weather"
           f"?alert=true&dailysteps=3&hourlysteps=24&unit=metric:v2")
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        try:
            err = json.load(e).get("error", "")
        except Exception:
            err = ""
        fail("彩云请求失败", f"HTTP {e.code}: {err if isinstance(err, str) else json.dumps(err, ensure_ascii=False)}")
        return
    except Exception as e:
        fail("彩云网络错误", f"{type(e).__name__}: {str(e).replace(token, '***')}")
        return

    if data.get("status") != "ok":
        err = data.get("error") or "未知错误"
        if not isinstance(err, str):
            err = json.dumps(err, ensure_ascii=False)
        hint = "（token 无效或额度用完，去控制台看看） | href=https://platform.caiyunapp.com/" \
            if ("token" in err or "quota" in err) else ""
        fail("彩云接口报错", f"{err} {hint}")
        return

    tz = timezone(timedelta(seconds=data.get("tzshift") or 28800))  # 分钟级钟点按位置时区算
    r = data["result"]
    rt = r.get("realtime", {})
    minutely = r.get("minutely") or {}
    hourly = r.get("hourly") or {}
    daily = r.get("daily") or {}
    keypoint = r.get("forecast_keypoint", "")

    temp = rt.get("temperature")
    apparent = rt.get("apparent_temperature")
    humidity = rt.get("humidity")
    skycon = rt.get("skycon", "")
    sky_sf, sky_cn = SKYCON.get(skycon, ("thermometer.medium", clean(skycon)))
    precip = rt.get("precipitation", {})
    local_mmh = (precip.get("local") or {}).get("intensity", 0) or 0
    nearest = precip.get("nearest") or {}
    wind = rt.get("wind") or {}
    aq = rt.get("air_quality", {})
    aqi = (aq.get("aqi") or {}).get("chn")

    snowing = "SNOW" in skycon
    wet_now = local_mmh >= MIN_RAIN or "RAIN" in skycon or snowing
    word = "雪" if snowing else "雨"

    # ── 降水时间线：分钟级优先，免费版无 minutely 时用小时级 ──
    p2h = minutely.get("precipitation_2h") or []
    start_min = stop_min = None
    if p2h:
        if wet_now:
            stop_min = next((i for i, v in enumerate(p2h) if v < MIN_RAIN), None)
        else:
            start_min = next((i for i, v in enumerate(p2h) if v >= MIN_RAIN), None)
    has_2h_rain = any(v >= MIN_RAIN for v in p2h)

    h_precip = hourly.get("precipitation") or []
    h_vals = [(h.get("value") or 0) for h in h_precip]
    hp = rain_periods(h_vals, HOURLY_RAIN)  # 24h 内连续有雨区间

    def hhour(i):
        """第 i 小时的钟点数字（int），datetime 缺失/畸形时返回 None"""
        d = h_precip[i].get("datetime") or ""
        try:
            return int(d[-11:-9])
        except (ValueError, IndexError):
            return None

    # 在下时的停雨钟点：仅当小时级也认为「现在在下」（hp[0] 从 0 开始）才可信，
    # 否则会把已经过去的整点当停雨时间显示
    h_stop_hh = None
    if wet_now and hp and hp[0][0] == 0 and hp[0][1] < len(h_vals):
        h_stop_hh = hhour(hp[0][1])

    # ── 菜单栏标题（图标承载状态，文字只留关键数字）──
    title = None
    if wet_now:
        r_sf, r_label = precip_sf(local_mmh, snowing)
        if stop_min is not None:
            title = f":{r_sf}: {max(stop_min, 1)}分停"
        elif h_stop_hh is not None:
            title = f":{r_sf}: {h_stop_hh}时停"
        else:
            title = f":{r_sf}: {r_label}"
    elif start_min is not None:
        title = f":umbrella.fill: {start_min}分后{word}"
    elif hp and hp[0][0] <= SOON_HOURS and (not p2h or hp[0][0] >= 2):
        # 有分钟级时，2 小时内的雨已由 start_min 分支负责；
        # 这里只补分钟级视界(2h)之外、SOON_HOURS 之内的雨
        a, b = hp[0]
        ha = hhour(a)
        hb = hhour(b) if b < len(h_vals) else None
        if ha is not None:
            title = f":umbrella.fill: {ha}-{hb}时{word}" if hb is not None else f":umbrella.fill: {ha}时起{word}"
    if title is None:
        title = f":{sky_sf}: {round(temp)}°" if temp is not None else f":{sky_sf}: {PLACE}"
    print(title)

    # ── 下拉：预报关键句置顶 ──
    print("---")
    if keypoint:
        print(f"{clean(keypoint)} | size=13")
        print("---")

    # ── 实况区（字段可能为 null：缺哪段省哪段，不硬凑）──
    parts = []
    if temp is not None:
        seg = f"{PLACE} {round(temp)}°"
        if apparent is not None:
            seg += f"（体感 {round(apparent)}°）"
        parts.append(seg)
    if humidity is not None:
        parts.append(f":humidity.fill: {round(humidity * 100)}%")
    if sky_cn:
        parts.append(sky_cn)
    if parts:
        print(":thermometer.medium: " + "  ".join(parts))
    if wind.get("speed") is not None:
        wd = WIND_DIRS[round((wind.get("direction") or 0) / 45) % 8]
        print(f":wind: {wd}风 {round(wind['speed'])} km/h")
    if local_mmh >= MIN_RAIN:  # 雷达强度未跟上时（skycon 在下、强度 0）不显示自相矛盾的 0.00
        p_sf, p_label = precip_sf(local_mmh, snowing)
        print(f":{p_sf}: 当前{'雪' if snowing else '雨'}强 {local_mmh:.2f} mm/h（{p_label}）")
    if nearest.get("distance") is not None:
        d = nearest["distance"]
        if d < 0.5:
            print(":location.fill: 降水带就在头顶")
        elif d < 100:
            ni = nearest.get("intensity", 0) or 0
            tag = f"，强度 {ni:.2f} mm/h" if ni >= MIN_RAIN else ""
            print(f":location.fill: 最近降水带 {d:.1f} km 外{tag}")
    if aqi is not None:
        print(f":aqi.medium: AQI {aqi}（{aqi_grade(aqi)}）")

    # ── 短临区：下雨时段列表（分钟级精确到分，免费版用小时级）──
    print("---")
    if p2h:
        now = datetime.now(tz)

        def mlabel(i):
            return (now + timedelta(minutes=i)).strftime("%H:%M")

        print_periods(p2h, MIN_RAIN, "umbrella.fill", mlabel, "2小时内不停", snowing, now_at_zero=True)
        if has_2h_rain:
            buckets = [max(p2h[i:i + 5]) for i in range(0, len(p2h), 5)]  # 取每 5 分钟峰值，别漏短阵雨
            print(f":chart.bar.fill: 未来2小时 {spark(buckets, MIN_RAIN)} | font=Menlo size=12")
        prob = minutely.get("probability") or []
        if len(prob) == 4:
            segs = "  ".join(f"{lo}-{hi}′ {pct01(p)}%"
                             for (lo, hi), p in zip(((0, 30), (30, 60), (60, 90), (90, 120)), prob))
            print(f"降水概率：{segs} | font=Menlo size=11")

    # 24小时内的有雨时段（小时级，跨天标「明天」）
    day0 = h_precip[0].get("datetime", "")[8:10] if h_precip else ""

    def hlabel(i):
        d = h_precip[i].get("datetime") or ""
        if len(d) < 11:
            return "?"
        return ("明天" if d[8:10] != day0 else "") + d[-11:-6]

    period_icon = "cloud.snow.fill" if snowing else "cloud.rain.fill"
    print_periods(h_vals, HOURLY_RAIN, period_icon, hlabel, "24小时内不停", snowing, now_at_zero=wet_now)
    if not hp and not has_2h_rain:
        print(f":clock.fill: 未来24小时无{word}")

    # 24h 降水时间轴 sparkline（有雨才画）+ 逐2小时明细收进子菜单
    h_temp = hourly.get("temperature") or []
    h_sky = hourly.get("skycon") or []
    if h_vals and any(v >= HOURLY_RAIN for v in h_vals):
        print(f":chart.bar.fill: 24小时降水 {spark(h_vals, HOURLY_RAIN)} | font=Menlo size=12")
    if h_temp and h_sky:
        print("未来24小时…")
        for i in range(0, min(len(h_temp), len(h_sky), 24), 2):
            tv = h_temp[i].get("value")
            if tv is None:
                continue
            d = h_temp[i].get("datetime") or ""
            hh = d[-11:-9] if len(d) >= 11 else "--"
            ssf = SKYCON.get(h_sky[i].get("value", ""), ("thermometer.medium", ""))[0]
            rain_tag = ""
            if i < len(h_precip) and h_vals[i] >= HOURLY_RAIN:
                pr = pct100(h_precip[i].get("probability"))
                if pr:
                    rain_tag = f"  ☂{pr}%"
            print(f"--{hh}时  :{ssf}: {round(tv)}°{rain_tag} | font=Menlo size=12")

    # ── 3 日预报区 ──
    d_temp = daily.get("temperature") or []
    d_sky = daily.get("skycon") or []
    d_prec = daily.get("precipitation") or []
    if d_temp and d_sky:
        rows = []
        names = ("今天", "明天", "后天")
        for i in range(min(3, len(d_temp), len(d_sky))):
            tmin, tmax = d_temp[i].get("min"), d_temp[i].get("max")
            if tmin is None or tmax is None:
                continue
            dsf, dcn = SKYCON.get(d_sky[i].get("value", ""), ("thermometer.medium", ""))
            pr = pct100((d_prec[i] or {}).get("probability")) if i < len(d_prec) else None
            tag = f"  ☂{pr}%" if pr else ""
            rows.append(f"{names[i]}  :{dsf}: {round(tmin)}–{round(tmax)}°  {dcn}{tag} | font=Menlo size=12")
        if rows:
            print("---")
            for row in rows:
                print(row)

    # ── 预警 ──
    alerts = (r.get("alert") or {}).get("content") or []
    if alerts:
        print("---")
        for a in alerts[:5]:
            print(f":exclamationmark.triangle.fill: {clean(a.get('title', '气象预警'))} | color=orange")

    # ── 操作区 ──
    print("---")
    print(":map.fill: 打开彩云雷达图 | href=https://caiyunapp.com/map/")
    print(":arrow.clockwise: 刷新 | refresh=true")
    note = " · 时段为小时级精度（分钟级未开通）" if not minutely else ""
    print(f"更新于 {datetime.now().strftime('%H:%M')}{note} | size=11 color=gray")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        fail("插件异常", f"{type(e).__name__}: {e}")
