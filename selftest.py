# -*- coding: utf-8 -*-
"""对 IslaPet 的新功能做无人值守自测：逐个调用方法并捕获异常。"""
import json
import os
import re
import sys
import traceback
from datetime import datetime, timedelta

from PySide6.QtCore import QEvent, QPoint, QPointF, QTimer, Qt
from PySide6.QtGui import QMouseEvent, QWheelEvent
from PySide6.QtWidgets import QApplication, QInputDialog, QMenu

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import isla_pet

results = []


def _placeholder_problems():
    """台词里的 {xxx} 必须在对应 pick() 调用里传参，否则会原样显示给用户。

    只校验字面量 key 的调用（pick("key", ...)）；通过变量传 key 的动态调用
    无法静态判定，跳过以免误报。
    """
    base = os.path.dirname(os.path.abspath(__file__))
    try:
        bank = json.load(open(os.path.join(base, "dialogues.json"),
                              encoding="utf-8"))
        src = open(os.path.join(base, "isla_pet.py"), encoding="utf-8").read()
    except OSError as exc:
        return ["读取失败: %s" % exc]
    bad = []
    for key, lines in bank.items():
        ph = set()
        for ln in lines:
            ph |= set(re.findall(r"\{(\w+)\}", ln))
        if not ph:
            continue
        calls = re.findall(
            r'pick\(\s*["\']' + re.escape(key) + r'["\']\s*([^)]*)\)', src)
        if not calls:
            continue
        provided = set()
        for rest in calls:
            provided |= set(re.findall(r"(\w+)\s*=", rest))
        missing = ph - provided
        if missing:
            bad.append("%s 缺少 %s" % (key, sorted(missing)))
    return bad


# 代码实际引用的全部台词分类（与 dialogues.json 对照）
REQUIRED_KEYS = [
    "greeting_morning", "greeting_afternoon", "greeting_evening",
    "greeting_late_night", "click_shy", "head_pat", "idle_murmur",
    "tea", "feed", "dice_high", "dice_mid", "dice_low",
    "coin_head", "coin_tail", "dance", "scare", "zoom_up", "zoom_down",
    "double_click", "drag", "drop", "rps_win", "rps_lose", "rps_draw",
    "follow_on", "follow_off", "hourly_chime", "sit_reminder",
    "sleep_reminder", "hidden", "wake_up", "farewell", "initiative",
    "mood_high", "mood_low", "mood_sad_hint", "dnd_off", "pomodoro_start",
    "pomodoro_focus_end", "pomodoro_break_end", "pomodoro_stop",
    "reminder_set", "reminder_fire", "reminder_none", "pc_status_ok",
    "pc_status_busy", "festival", "birthday", "anniversary",
    "anniversary_today", "streak", "streak_back", "achievement",
    "memory_none", "memory_first_pat", "memory_first_tea",
    "memory_first_feed", "memory_first_rps_win", "memory_first_dance",
    "memory_first_fortune", "memory_first_capsule",
    "memory_first_firework", "capsule_set", "capsule_fire",
    "capsule_bad_date", "capsule_past", "fortune_big", "fortune_mid",
    "fortune_small", "fortune_bad", "alarm_set", "alarm_fire",
    "alarm_bad_time", "theme_change", "noise_on", "noise_off", "firework",
    "brief_start", "brief_end", "brief_fail",
]

# 输入框打桩：时间胶囊(文本, 日期) -> 闹钟(时间)
_input_queue = iter(["给未来的信", (datetime.now().date()
                                    + timedelta(days=3)).isoformat(), "08:00"])
QInputDialog.getText = staticmethod(
    lambda *a, **k: (next(_input_queue), True))
QInputDialog.getInt = staticmethod(lambda *a, **k: (25, True))


def check(name, fn):
    print("  RUN  %s" % name, flush=True)   # 进度输出：卡住时能定位到具体项
    try:
        fn()
        results.append((True, name, ""))
    except Exception as exc:
        results.append((False, name, "%s: %s" % (type(exc).__name__, exc)))
        traceback.print_exc()


app = QApplication(sys.argv)
QMenu.exec = lambda self, *a, **k: None      # 菜单不阻塞，只验证构建
pet = isla_pet.IslaPet()

check("台词库分类齐全（%d 类）" % len(REQUIRED_KEYS),
      lambda: [k for k in REQUIRED_KEYS if k not in pet.bank.data]
      == [] or (_ for _ in ()).throw(
          AssertionError("缺少台词分类")))
check("问候（含深夜段）", pet._greet)
check("每日播报 streak/节日/纪念日", pet._daily_notes)
check("摸头（头部单击）", lambda: (
    setattr(pet, "press_local", QPoint(pet.width() // 2, 10)),
    pet._single_click()))
check("普通单击（身体）", lambda: (
    setattr(pet, "press_local", QPoint(pet.width() // 2, pet.height() - 20)),
    pet._single_click()))
check("爱心粒子生成+更新+绘制", lambda: (
    pet._spawn_hearts(8), pet._update_hearts(), pet.repaint()))
check("投喂点心", pet._feed)
check("泡茶", pet._brew_tea)
for i in range(3):
    check("猜拳出 %s" % isla_pet.RPS[i], lambda k=i: pet._play_rps(k))
check("猜拳结果-她赢", lambda: pet._rps_result("rps_win"))
check("猜拳结果-她输", lambda: pet._rps_result("rps_lose"))
check("跟随鼠标开启+移动一帧", lambda: (
    pet._toggle_follow(True), pet._follow_step()))
check("跟随鼠标关闭", lambda: pet._toggle_follow(False))
check("番茄钟启动", pet._pomo_start)
check("番茄钟剩余时间显示", lambda: pet._pomo_left())
check("番茄钟到点切休息", lambda: (
    setattr(pet, "pomo_end", datetime.now() - timedelta(seconds=1)),
    pet._pomo_check()))
check("休息到点结束", lambda: (
    setattr(pet, "pomo_end", datetime.now() - timedelta(seconds=1)),
    pet._pomo_check()))
check("番茄钟停止", pet._pomo_stop)
check("待办为空提示", pet._show_reminders)
check("提醒到点触发", lambda: (
    pet.reminders.append((datetime.now() - timedelta(seconds=1), "喝水")),
    pet._reminder_check()))
check("待办列表显示", lambda: (
    pet.reminders.append((datetime.now() + timedelta(minutes=9), "开会")),
    pet._show_reminders()))
check("电脑内存占用读取", lambda: (
    pet._memory_percent() > 0 or (_ for _ in ()).throw(
        AssertionError("内存占用读取失败")), pet._pc_status()))
check("纪念日倒数（3天后）", lambda: (
    pet.save.update({"anniv_name": "约定的日子",
                     "anniv_date": (datetime.now().date()
                                    + timedelta(days=3)).isoformat()}),
    pet._anniversary_note() or (_ for _ in ()).throw(
        AssertionError("倒数未生成"))))
check("纪念日当天", lambda: (
    pet.save.update({"anniv_date": datetime.now().date().isoformat()}),
    pet._anniversary_note()[0] == "anniversary_today" or (
        _ for _ in ()).throw(AssertionError("当天分支错误"))))
check("生日祝福分支", lambda: (
    pet.save.update({"birthday": datetime.now().strftime("%m-%d")}),
    pet._daily_notes()))
check("连续登录统计", pet._check_login_streak)
check("心情衰减（15 分钟一档）", lambda: (
    setattr(pet, "mood_decay", 8999), pet._mood_tick()))
check("心情低谷求助提示", lambda: (
    setattr(pet, "_sad_hint_done", False),
    pet.save.update({"mood": 8}), pet._mood_tick(),
    pet._sad_hint_done is True or (_ for _ in ()).throw(
        AssertionError("低谷提示未触发"))))
check("状态行（等级/好感/心情/时长）", lambda: len(pet._status_lines()) == 4 or (
    _ for _ in ()).throw(AssertionError("状态行数量不对")))
check("完整右键菜单构建", lambda: pet._show_menu(QPoint(300, 300)))
check("心跳 tick 连跑 40 帧", lambda: [pet._tick() for _ in range(40)])
check("闲逛启动", lambda: (pet._stop_wander(), pet._start_wander()))
check("尺寸切换", lambda: (pet._apply_size("大 (320px)"),
                       pet._apply_size("中 (260px)")))

# ---- v2.0 新功能 ----
check("掷骰子", pet._roll_dice)
check("抛硬币", pet._flip_coin)
check("硬币结果-正面", lambda: pet._coin_result(True))
check("硬币结果-反面", lambda: pet._coin_result(False))
check("跳舞启动", pet._dance)
check("跳舞步进", lambda: (setattr(pet, "dance_seq", ["shy", "idle"]),
                       pet._dance_step()))
check("中键惊吓", pet._scare)
check("左键按下可拖动（回归）", lambda: (
    setattr(pet, "press_pos", None),
    pet.mousePressEvent(QMouseEvent(
        QEvent.Type.MouseButtonPress, QPointF(50, 50), QPointF(50, 50),
        Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)),
    pet.press_pos is not None or (_ for _ in ()).throw(
        AssertionError("左键按下未记录拖拽起点"))))
check("中键按下触发惊吓（回归）", lambda: (
    setattr(pet, "scare_cd", 0), setattr(pet, "press_pos", None),
    pet.mousePressEvent(QMouseEvent(
        QEvent.Type.MouseButtonPress, QPointF(50, 50), QPointF(50, 50),
        Qt.MiddleButton, Qt.MiddleButton, Qt.NoModifier)),
    pet.press_pos is None or (_ for _ in ()).throw(
        AssertionError("中键不应触发拖拽"))))
check("滚轮放大事件", lambda: (
    setattr(pet, "zoom_cd", 0), pet.wheelEvent(QWheelEvent(
        QPointF(5, 5), QPointF(5, 5), QPoint(0, 0), QPoint(0, 120),
        Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False))))
check("滚轮缩小事件", lambda: (
    setattr(pet, "zoom_cd", 0), pet.wheelEvent(QWheelEvent(
        QPointF(5, 5), QPointF(5, 5), QPoint(0, 0), QPoint(0, -120),
        Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False))))
check("互动统计计数", lambda: (
    pet._bump("dice"), pet._bump("dice"),
    pet.save["stats"].get("dice", 0) >= 3 or (_ for _ in ()).throw(
        AssertionError("dice 计数错误"))))
check("记忆碎片首次记录", lambda: (
    pet._record_memory("pat_1", "memory_first_pat"),
    pet._record_memory("pat_1", "memory_first_pat"),   # 重复应被忽略
    len(pet.save["memories"]) >= 1 or (_ for _ in ()).throw(
        AssertionError("记忆碎片未写入"))))
check("成就检查（静默同步）", lambda: (
    pet.save["stats"].update({"pat": 10, "feed": 5, "tea": 5,
                              "rps_win": 3, "dice": 10}),
    pet._check_achievements(silent=True),
    "pat_10" in pet.save["achievements"] or (_ for _ in ()).throw(
        AssertionError("成就未解锁"))))
check("成就查看", pet._view_achievements)
check("回忆查看", pet._view_memories)
check("统计查看", pet._view_stats)
check("等级称号", lambda: (
    pet.save.update({"streak": 30}),
    pet._level_name() == "家人" or (_ for _ in ()).throw(
        AssertionError("等级称号错误"))))
check("时间胶囊写入", pet._add_capsule)
check("时间胶囊到点触发", lambda: (
    pet.save["capsules"].append(
        [(datetime.now().date() - timedelta(days=1)).isoformat(), "过去的我"]),
    pet._capsule_check(),
    all(c[0] >= datetime.now().date().isoformat()
        for c in pet.save["capsules"]) or (_ for _ in ()).throw(
        AssertionError("过期胶囊未清除"))))
check("每日运势", lambda: (pet._fortune(), pet._fortune()))
check("闹钟设置", pet._set_alarm)
check("闹钟到点触发", lambda: (
    pet.save["alarms"].append(datetime.now().strftime("%H:%M")),
    pet._alarm_check()))
check("闹钟台词无未填充占位符", lambda: (
    "{" not in pet.bank.pick("alarm_fire", time="08:00") or (
        _ for _ in ()).throw(AssertionError("闹钟台词含未填充的 {time}"))))
check("主题换肤", lambda: (
    pet._set_theme("薄荷蓝"),
    pet.save["theme"] == "薄荷蓝" or (_ for _ in ()).throw(
        AssertionError("主题未切换")),
    pet.bubble.theme == "薄荷蓝" or (_ for _ in ()).throw(
        AssertionError("气泡主题未同步")),
    len(pet.hearts) >= 8 or (_ for _ in ()).throw(
        AssertionError("换肤粒子未生成"))))
check("白噪音 wav 生成", lambda: (
    pet._generate_rain_wav(os.path.join(os.environ.get("TEMP", "."),
                                        "isla_test_rain.wav"), seconds=1)
    or (_ for _ in ()).throw(AssertionError("wav 生成失败"))))
check("白噪音加载", lambda: pet._load_noise())
check("全屏烟花", lambda: (
    pet._show_firework(),
    pet.firework is not None and pet.firework.isVisible() or (
        _ for _ in ()).throw(AssertionError("烟花窗口未显示"))))
check("烟花粒子步进", lambda: (
    pet.firework._burst(), pet.firework._step(), pet.firework.repaint()))
check("冷色立绘生成", lambda: (
    len(pet.cold_frames) == len(pet.frames) or (_ for _ in ()).throw(
        AssertionError("冷色帧未生成"))))
check("新台词分类齐全", lambda: [k for k in (
    "dice_high", "coin_head", "dance", "scare", "achievement",
    "capsule_fire", "fortune_big", "alarm_fire", "theme_change",
    "noise_on", "firework", "zoom_up", "memory_first_pat",
    "mood_sad_hint")
    if k not in pet.bank.data] == [] or (_ for _ in ()).throw(
        AssertionError("缺少新台词分类")))
check("提醒持久化到存档", lambda: (
    pet.save_data(),
    isinstance(pet.save.get("reminders"), list)
    and len(pet.save["reminders"]) >= 1 or (_ for _ in ()).throw(
        AssertionError("reminders 未写入存档"))))
_PH_BAD = _placeholder_problems()
check("台词占位符与传参一致", lambda: (
    not _PH_BAD or (_ for _ in ()).throw(
        AssertionError("占位符未传参: " + "; ".join(_PH_BAD)))))
check("全屏检测不抛异常", lambda: (
    isinstance(pet._is_foreground_fullscreen(), bool) or (
        _ for _ in ()).throw(AssertionError("全屏检测返回值异常"))))
check("免打扰状态切换", lambda: (
    setattr(pet, "fullscreen_quiet", False),
    pet.save.update({"dnd_on": True}),
    pet._update_dnd(),
    setattr(pet, "fullscreen_quiet", True), pet._update_dnd(),
    not pet.fullscreen_quiet or (
        _ for _ in ()).throw(AssertionError("退出免打扰失败")),
    setattr(pet, "fullscreen_quiet", False)))
check("免打扰时台词走托盘", lambda: (
    pet.bubble.hide(),                          # 先清掉可能残留的气泡
    setattr(pet, "fullscreen_quiet", True),
    pet.say("测试免打扰"),
    not pet.bubble.isVisible() or (
        _ for _ in ()).throw(AssertionError("免打扰时仍弹了气泡")),
    setattr(pet, "fullscreen_quiet", False)))
check("气泡长内容停留更久", lambda: (
    setattr(pet, "fullscreen_quiet", False),    # 兜底复位，防前项残留
    pet.bubble.hide(), pet.say("短"),
    setattr(pet, "_short_ms", pet.bubble._timer.interval()),
    pet.bubble.hide(), pet.say("很长的一句台词" * 20),
    setattr(pet, "_long_ms", pet.bubble._timer.interval()),
    pet._long_ms > pet._short_ms or (_ for _ in ()).throw(
        AssertionError("长文本未延长: %s -> %s"
                       % (pet._short_ms, pet._long_ms)))))
check("番茄钟存盘与恢复", lambda: (
    pet._pomo_start("focus"),
    pet.save_data(),
    (pet.save.get("pomo") or [None])[0] == "focus" or (
        _ for _ in ()).throw(AssertionError("番茄钟未写入存档"))))

# ---- 每日早报（60s 摘要） ----
check("早报解析与截断", lambda: (
    (lambda items: (len(items) == 2 and items[0].endswith("…")
                    and len(items[0]) <= isla_pet.BRIEF_ITEM_CHARS + 1
                    and items[1] == "短新闻")
     or (_ for _ in ()).throw(AssertionError("解析结果不符")))(
        isla_pet.IslaPet._parse_brief(
            {"data": {"news": ["长" * 100, "短新闻", "第三条"]}}))))
check("早报截断优先断句", lambda: (
    isla_pet.IslaPet._clip_brief(
        "今天天气不错。大家都很开心。" + "尾巴" * 40).endswith("。")
    or (_ for _ in ()).throw(AssertionError("未断在句号处"))))
check("早报播放并落档", lambda: (
    setattr(pet, "_brief_pending", True),
    setattr(pet, "_brief_result", ["测试新闻一", "测试新闻二"]),
    setattr(pet, "_brief_manual", False),
    pet._brief_tick(),
    pet.save.get("brief_date") == datetime.now().date().isoformat()
    or (_ for _ in ()).throw(AssertionError("brief_date 未写入"))))
check("早报失败走兜底台词", lambda: (
    setattr(pet, "_brief_pending", True),
    setattr(pet, "_brief_result", []),
    setattr(pet, "_brief_manual", True),
    pet._brief_tick(),
    pet._brief_pending is False or (_ for _ in ()).throw(
        AssertionError("失败后未复位拉取状态"))))
check("早报当天已读不重复拉取", lambda: (
    setattr(pet, "_brief_pending", False),
    setattr(pet, "_brief_result", None),
    pet.save.update({"brief_date": datetime.now().date().isoformat()}),
    pet._daily_brief(),
    pet._brief_pending is False or (_ for _ in ()).throw(
        AssertionError("当天已读仍在拉取"))))

_real_datetime = isla_pet.datetime


def _patch_hour(h):
    """临时把模块内 datetime.now() 钉到指定小时，测自动触发条件。"""
    class _FakeDT(_real_datetime):
        @classmethod
        def now(cls, tz=None):
            return _real_datetime(2026, 9, 11, h, 0, 0)
    isla_pet.datetime = _FakeDT


def _restore_hour():
    isla_pet.datetime = _real_datetime


check("早报 7 点后未读时自动拉取", lambda: (
    setattr(pet, "pomo_state", None),      # 前项测试开着番茄钟，专注期间早报应静默
    setattr(pet, "_brief_pending", False),
    setattr(pet, "_brief_result", None),
    setattr(pet, "_brief_attempt_day", None),
    pet.save.update({"brief_on": True, "brief_date": None}),
    _patch_hour(8), pet._brief_maybe_auto(), _restore_hour(),
    pet._brief_pending is True or (_ for _ in ()).throw(
        AssertionError("7 点后未触发自动拉取")),
    setattr(pet, "_brief_pending", False),
    setattr(pet, "_brief_result", None)))
check("早报 7 点前不触发", lambda: (
    setattr(pet, "pomo_state", None),
    setattr(pet, "_brief_pending", False),
    setattr(pet, "_brief_result", None),
    setattr(pet, "_brief_attempt_day", None),
    pet.save.update({"brief_on": True, "brief_date": None}),
    _patch_hour(5), pet._brief_maybe_auto(), _restore_hour(),
    pet._brief_pending is False or (_ for _ in ()).throw(
        AssertionError("7 点前不应拉取")),
    setattr(pet, "_brief_result", None)))
check("存档写入", pet.save_data)


def report():
    ok = sum(1 for r in results if r[0])
    print("=" * 56)
    for good, name, err in results:
        print(("  PASS  " if good else "  FAIL  ") + name + ("  " + err if err else ""))
    print("=" * 56)
    print("通过 %d / %d" % (ok, len(results)))
    app.quit()
    sys.exit(0 if ok == len(results) else 1)


QTimer.singleShot(1500, report)
sys.exit(app.exec())
