# -*- coding: utf-8 -*-
"""无人值守自测：父进程限时，子进程只使用临时存档、固定 API 和静音播放器。"""
import atexit
import faulthandler
import hashlib
import io
import json
import os
from pathlib import Path
import random
import re
import subprocess
import sys
import tempfile
import traceback
from datetime import date as _Date, datetime as _DateTime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

BASE = Path(__file__).resolve().parent
TIMEOUT_SECONDS = 60
sys.dont_write_bytecode = True
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _supervise():
    """超时、崩溃、缺失完成凭据、清理失败均不能成为 pre-commit 的成功。"""
    source = (BASE / "isla_pet.py").read_bytes()
    with tempfile.TemporaryDirectory(prefix="isla-selftest-") as root:
        env = os.environ.copy()
        for key in ("TEMP", "TMP", "APPDATA", "LOCALAPPDATA", "HOME", "USERPROFILE"):
            env[key] = root
        env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
        try:
            child = subprocess.run(
                [sys.executable, "-u", "-B", str(BASE / "selftest.py"),
                 "--selftest-worker", root],
                cwd=root, env=env, timeout=TIMEOUT_SECONDS, check=False)
        except subprocess.TimeoutExpired:
            print("FAIL: 自测超过 %d 秒，已终止子进程" % TIMEOUT_SECONDS, flush=True)
            return 124
        if child.returncode:
            print("FAIL: 自测子进程退出码 %d" % child.returncode, flush=True)
            return child.returncode if 0 < child.returncode < 256 else 1
        try:
            proof = json.loads((Path(root) / "result.json").read_text(encoding="utf-8"))
            assert proof["completed"] is True
            assert proof["total"] > 0 and proof["passed"] == proof["total"]
            assert proof["source"] == hashlib.sha256(source).hexdigest()
            assert (BASE / "isla_pet.py").read_bytes() == source
        except (OSError, ValueError, KeyError, AssertionError) as exc:
            print("FAIL: 完成凭据无效或主程序仍有并行修改: %s" % exc, flush=True)
            return 1
    return 0


# 普通调用永远进入监督进程；内部 worker 不得落回用户目录。
if __name__ == "__main__" and sys.argv[1:2] != ["--selftest-worker"]:
    try:
        sys.exit(_supervise())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
if __name__ != "__main__" or len(sys.argv) != 3:
    raise RuntimeError("请直接运行 selftest.py，不要导入或单独调用 worker")
ROOT = Path(sys.argv[2]).resolve(strict=True)
if ROOT == BASE or Path(os.environ.get("APPDATA", "")).resolve() != ROOT:
    raise RuntimeError("worker 缺少临时目录隔离")
SOURCE_HASH = hashlib.sha256((BASE / "isla_pet.py").read_bytes()).hexdigest()
SAVE_PATH = ROOT / "isla_save.json"
results = []
_violations = []
_current_check = "初始化"
app = pet = None
_cleaned = False
_patches = []
_deferred = []


def _inside_root(path):
    return Path(path).resolve().is_relative_to(ROOT)


def _audit(event, args):
    """防回归：Python 文件写入必须在沙箱内，真实网络一律拒绝。"""
    paths = []
    if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
        path, mode, flags = args
        writing = bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
        if writing or Path(os.fsdecode(path)).name.startswith("isla_save"):
            paths = [path]
    elif event in ("os.rename", "os.replace"):
        paths = args[:2]
    elif event in ("os.remove", "os.rmdir", "os.mkdir"):
        paths = args[:1]
    elif event in ("socket.connect", "socket.getaddrinfo", "socket.bind", "socket.sendto"):
        _violations.append(event)
        raise RuntimeError("自测禁止真实网络: " + event)
    for path in paths:
        if not _inside_root(os.fsdecode(path)):
            _violations.append("%s: %s" % (event, path))
            raise PermissionError("自测禁止访问沙箱外的存档/写入: %s" % (path,))


sys.addaudithook(_audit)
faulthandler.enable()
faulthandler.dump_traceback_later(TIMEOUT_SECONDS - 10, exit=False)

from PySide6.QtCore import (QAbstractAnimation, QEvent, QObject, QPoint,
                            QPointF, QRect, QTimer, Qt)
from PySide6.QtGui import QCursor, QMouseEvent, QWheelEvent
from PySide6.QtWidgets import (QApplication, QDialog, QFileDialog, QInputDialog,
                               QMenu, QMessageBox, QSystemTrayIcon)
import shiboken6

sys.path.insert(0, str(BASE))
import isla_pet


class datetime(_DateTime):
    hour_now = 8

    @classmethod
    def now(cls, tz=None):
        value = cls(2026, 9, 11, cls.hour_now, 0, 0)
        return value if tz is None else value.replace(tzinfo=tz)


class _FixedDate(_Date):
    @classmethod
    def today(cls):
        return cls(2026, 9, 11)


class _InlineThread:
    """保留真实 API 解析和 wav 生成路径，不产生竞态或遗留后台线程。"""
    def __init__(self, target, args=(), kwargs=None, **unused):
        self.target, self.args, self.kwargs = target, args, kwargs or {}

    def start(self):
        self.target(*self.args, **self.kwargs)


class _SilentSound:
    Infinite = -2

    def __init__(self):
        self.playing = False

    def setSource(self, source):
        self.source = source

    def setLoopCount(self, count):
        self.loops = count

    def setVolume(self, volume):
        self.volume = volume

    def play(self):
        self.playing = True

    def stop(self):
        self.playing = False


class _HeadlessMenu(QMenu):
    # 子类覆盖避免 PySide 原生方法绑定绕过对 QMenu.exec 的类级替换。
    def exec(self, *args, **kwargs):
        assert self.actions(), "右键菜单未构建"
        return None

    exec_ = exec


class _ModalGuard(QObject):
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Show and isinstance(obj, QDialog) and obj.isModal():
            obj.reject()
        return False


BRIEF_FIXTURE = {"data": {"news": ["固定新闻一", "固定新闻二", "不应播报的第三条"]}}
_api_calls = []
_notifications = []


def _urlopen(request, *args, **kwargs):
    url = getattr(request, "full_url", request)
    if url != isla_pet.BRIEF_API:
        _violations.append("意外 API: %s" % url)
        raise AssertionError("意外 API: %s" % url)
    _api_calls.append(url)
    return io.BytesIO(json.dumps(BRIEF_FIXTURE, ensure_ascii=False).encode("utf-8"))


def _input_text(*args, **kwargs):
    title, prompt = args[1:3]
    if title == "时间胶囊":
        return ((datetime.now().date() + timedelta(days=3)).isoformat()
                if "开启" in prompt else "给未来的信"), True
    if title == "闹钟":
        return "08:00", True
    return "", False                       # 未列出的输入框确定性取消


def _patch(obj, name, replacement):
    item = patch.object(obj, name, replacement)
    item.start()
    _patches.append(item)


def _single_shot(ms, callback):
    # 静态回调由自测显式推进；不让启动 17 秒早报等回调串入后续用例。
    _deferred.append((ms, callback))


def _drain_deferred():
    for _ in range(100):
        if not _deferred:
            return
        pending = sorted(_deferred, key=lambda entry: entry[0])
        _deferred.clear()
        for _, callback in pending:
            callback()
    raise AssertionError("延迟回调未能收敛")


def _stop_qt_activity():
    if app is None:
        return
    for widget in QApplication.topLevelWidgets():
        for timer in widget.findChildren(QTimer):
            timer.stop()
        for anim in widget.findChildren(QAbstractAnimation):
            anim.stop()
    if pet is not None:
        for name in ("wander_anim", "drop_anim"):
            anim = getattr(pet, name, None)
            if anim is not None and shiboken6.isValid(anim):
                anim.stop()


def _cleanup():
    global _cleaned
    if _cleaned:
        return
    _cleaned = True
    try:
        _deferred.clear()
        _stop_qt_activity()
        if app is not None:
            for widget in QApplication.topLevelWidgets():
                widget.close()
                widget.deleteLater()
            QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            app.quit()
            shiboken6.delete(app)
    except Exception as exc:
        results.append((False, "Qt 清理", repr(exc)))
        traceback.print_exc()
    finally:
        for item in reversed(_patches):
            item.stop()
        faulthandler.cancel_dump_traceback_later()


atexit.register(_cleanup)


def _uncaught(etype, value, tb):
    results.append((False, "Qt 回调异常（%s）" % _current_check, str(value)))
    traceback.print_exception(etype, value, tb)


sys.excepthook = _uncaught
_patch(isla_pet, "data_file", lambda: str(SAVE_PATH))
_patch(isla_pet, "app_dir", lambda: str(ROOT))
_patch(isla_pet, "LOG_DIR", str(ROOT / "logs"))
_patch(isla_pet, "datetime", datetime)
_patch(isla_pet, "date", _FixedDate)
_patch(isla_pet, "time", SimpleNamespace(monotonic=lambda: 1000.0))
_patch(isla_pet, "random", random.Random(20260911))
_patch(isla_pet, "threading", SimpleNamespace(Thread=_InlineThread))
_patch(isla_pet, "QSoundEffect", _SilentSound)
_patch(isla_pet, "_HAS_SOUND", True)
_patch(isla_pet.urllib.request, "urlopen", _urlopen)
_patch(isla_pet, "QMenu", _HeadlessMenu)
_patch(QTimer, "singleShot", staticmethod(_single_shot))
_patch(QInputDialog, "getText", staticmethod(_input_text))
_patch(QInputDialog, "getInt", staticmethod(lambda *a, **k: (25, True)))
for name, value in (("getDouble", (1.0, False)), ("getItem", ("", False)),
                    ("getMultiLineText", ("", False))):
    _patch(QInputDialog, name, staticmethod(lambda *a, _v=value, **k: _v))
for name in ("information", "warning", "critical", "question", "about", "aboutQt"):
    _patch(QMessageBox, name, staticmethod(lambda *a, **k: QMessageBox.Ok))
for name, value in (("getOpenFileName", ("", "")), ("getOpenFileNames", ([], "")),
                    ("getSaveFileName", ("", "")), ("getExistingDirectory", ""),
                    ("getOpenFileUrl", (isla_pet.QUrl(), "")),
                    ("getOpenFileUrls", ([], "")), ("getSaveFileUrl", (isla_pet.QUrl(), "")),
                    ("getExistingDirectoryUrl", isla_pet.QUrl())):
    _patch(QFileDialog, name, staticmethod(lambda *a, _v=value, **k: _v))
for dialog in (QDialog, QInputDialog, QMessageBox, QFileDialog):
    for method in ("exec", "exec_"):
        if hasattr(dialog, method):
            _patch(dialog, method, lambda *a, **k: QDialog.Rejected)
_patch(QSystemTrayIcon, "showMessage", lambda *a, **k: _notifications.append((a, k)))
_patch(QCursor, "pos", staticmethod(lambda: QPoint(400, 300)))
_real_fullscreen = isla_pet.IslaPet._is_foreground_fullscreen
_patch(isla_pet.IslaPet, "_is_foreground_fullscreen", staticmethod(lambda: False))


def _read_saved():
    assert SAVE_PATH.is_file(), "没有生成真实测试存档"
    assert not Path(str(SAVE_PATH) + ".tmp").exists(), "原子写入残留临时文件"
    return json.loads(SAVE_PATH.read_text(encoding="utf-8"))


def _save_roundtrip():
    pet.save_data()
    saved = _read_saved()
    assert saved == pet.save, "磁盘存档与内存状态不一致"
    return saved


def _test_wav():
    import wave
    path = ROOT / "isla_test_rain.wav"
    assert pet._generate_rain_wav(str(path), seconds=1), "wav 生成失败"
    with wave.open(str(path), "rb") as stream:
        assert (stream.getnchannels(), stream.getsampwidth(),
                stream.getframerate(), stream.getnframes()) == (1, 2, 22050, 22050)
        pcm = stream.readframes(stream.getnframes())
        assert len(pcm) == 44100 and any(pcm), "wav 没有有效音频采样"


def _test_dnd_switch():
    pet.save["dnd_on"] = True
    with patch.object(pet, "_is_foreground_fullscreen", side_effect=[True, False]):
        pet._update_dnd()
        assert pet.fullscreen_quiet, "进入免打扰失败"
        pet._update_dnd()
        assert not pet.fullscreen_quiet, "退出免打扰失败"


def _test_dnd_silent():
    pet.fullscreen_quiet = True
    before = len(_notifications)
    pet.say("测试免打扰")
    assert not pet.bubble.isVisible(), "免打扰时仍弹了气泡"
    assert not pet.bubble._queue, "免打扰台词不应堆积"
    assert len(_notifications) == before, "普通 say 不应变成系统通知"


def _move_center(dx=0):
    # 避免假设桌面至少有 1000px 宽（offscreen 默认只有 800px）。
    g = pet._screen_geo()
    pet.move(g.center().x() - pet.width() // 2 + dx,
             g.top() + max(200, (g.height() - pet.height()) // 2))


def _placeholder_problems():
    """台词里的 {xxx} 必须在对应 pick() 调用里传参，否则会原样显示给用户。

    只校验字面量 key 的调用（pick("key", ...)）；通过变量传 key 的动态调用
    无法静态判定，跳过以免误报。
    """
    base = os.path.dirname(os.path.abspath(__file__))
    try:
        with open(os.path.join(base, "dialogues.json"), encoding="utf-8") as stream:
            bank = json.load(stream)
        src = (Path(base) / "isla_pet.py").read_text(encoding="utf-8")
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

def check(name, fn):
    global _current_check
    _current_check = name
    print("  RUN  %s" % name, flush=True)
    before = len(results)
    try:
        _stop_qt_activity()
        _deferred.clear()
        datetime.hour_now = 8
        isla_pet.datetime = datetime
        isla_pet.random.seed(20260911)
        pet.fullscreen_quiet = False
        pet.bubble._queue.clear()
        pet.bubble.hide()
        pet._ent_scale = 1.0
        pet.setWindowOpacity(1.0)
        fn()
        _drain_deferred()
        if any(not good for good, _, _ in results[before:]):
            raise AssertionError("本项产生了未捕获 Qt 异常")
        results.append((True, name, ""))
    except Exception as exc:
        results.append((False, name, "%s: %s" % (type(exc).__name__, exc)))
        traceback.print_exc()
    finally:
        datetime.hour_now = 8
        isla_pet.datetime = datetime
        _deferred.clear()
        _stop_qt_activity()


app = QApplication([sys.argv[0]])
app.setQuitOnLastWindowClosed(False)
_modal_guard = _ModalGuard(app)
app.installEventFilter(_modal_guard)
# 首次构造必须看到不存在的测试存档；绝不先构造再替换路径。
assert not SAVE_PATH.exists()
pet = isla_pet.IslaPet()
pet.tray = SimpleNamespace(showMessage=lambda *a, **k: _notifications.append((a, k)))
_stop_qt_activity()
_deferred.clear()                  # 启动问候/早报另有显式测试
pet.show()
app.processEvents()               # offscreen 也先完成首次布局/绘制

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
check("白噪音 wav 生成及文件读回", _test_wav)
check("白噪音加载", lambda: (
    pet._load_noise(),
    isinstance(pet.noise, _SilentSound) and Path(pet.noise.source.toLocalFile()).is_file()
    or (_ for _ in ()).throw(AssertionError("未从真实临时 wav 加载静音播放器"))))
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
    _save_roundtrip(),
    _read_saved()["reminders"] == [[t.isoformat(), text] for t, text in pet.reminders]
    and len(_read_saved()["reminders"]) >= 1 or (_ for _ in ()).throw(
        AssertionError("reminders 未写入磁盘存档"))))
_PH_BAD = _placeholder_problems()
check("台词占位符与传参一致", lambda: (
    not _PH_BAD or (_ for _ in ()).throw(
        AssertionError("占位符未传参: " + "; ".join(_PH_BAD)))))
check("全屏检测不抛异常", lambda: (
    isinstance(_real_fullscreen(), bool) or (
        _ for _ in ()).throw(AssertionError("全屏检测返回值异常"))))
check("免打扰状态切换", _test_dnd_switch)
check("免打扰时普通台词静默且不通知", _test_dnd_silent)
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
    _save_roundtrip(),
    _read_saved()["pomo"] == ["focus", pet.pomo_end.isoformat()] or (
        _ for _ in ()).throw(AssertionError("番茄钟未写入磁盘存档"))))

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
check("存档写入及完整文件读回", _save_roundtrip)


# ---- v2.2 升级：动画手感 / 性能守卫 / 常量化 ----
def _count_updates(pet, ticks):
    """临时遮蔽 pet.update，统计 ticks 次 _tick 实际触发了几次重绘。"""
    box = [0]
    pet.update = lambda *a, **k: box.__setitem__(0, box[0] + 1)
    try:
        for _ in range(ticks):
            pet._tick()
    finally:
        del pet.update          # 去掉实例遮蔽，恢复类方法
    return box[0]


def _force_wander(pet):
    from PySide6.QtCore import QPropertyAnimation
    a = QPropertyAnimation(pet, b"pos")
    a.setDuration(20000)
    a.setStartValue(pet.pos())
    a.setEndValue(pet.pos() + QPoint(300, 0))
    a.start()
    pet.wander_anim = a


check("v2.2 新常量已定义", lambda: (
    all(hasattr(isla_pet, k) for k in (
        "MOOD_SAD", "MOOD_HIGH", "MOOD_LOW", "INITIATIVE_CD",
        "BLINK_CHANCE", "WALK_BOB", "BREATH_SCALE")) or (
        _ for _ in ()).throw(AssertionError("缺少 v2.2 常量"))))
check("步态相位仅在移动时推进", lambda: (
    setattr(pet, "wander_anim", None), setattr(pet, "walk_phase", 0.0),
    pet._tick(),
    pet.walk_phase == 0.0 or (_ for _ in ()).throw(
        AssertionError("非移动时步态不应推进")),
    _force_wander(pet), [pet._tick() for _ in range(5)],
    pet.walk_phase > 0.0 or (_ for _ in ()).throw(
        AssertionError("移动时步态未推进")),
    pet._stop_wander()))
check("休眠静帧跳过重绘（守卫）", lambda: (
    setattr(pet, "wander_anim", None),
    setattr(pet, "sleeping", True), setattr(pet, "state", "sleep"),
    setattr(pet, "hearts", []), setattr(pet, "hop_ticks", 0),
    setattr(pet, "dragging", False), setattr(pet, "temp_state_ticks", 0),
    setattr(pet, "_last_painted_state", "sleep"),
    _count_updates(pet, 3) == 0 or (_ for _ in ()).throw(
        AssertionError("休眠静帧不应重绘"))))
check("姿势变化强制重绘（守卫）", lambda: (
    setattr(pet, "sleeping", False), setattr(pet, "state", "idle"),
    setattr(pet, "_last_painted_state", "sleep"),
    _count_updates(pet, 1) >= 1 or (_ for _ in ()).throw(
        AssertionError("姿势变化应触发重绘"))))
check("主题光晕按尺寸缓存", lambda: (
    setattr(pet, "_glow_key", None), pet.repaint(),
    pet._glow is not None and pet._glow_key == (
        pet.save.get("theme", "樱花粉"), pet.width(), pet.height()) or (
        _ for _ in ()).throw(AssertionError("光晕缓存键不正确"))))
check("打气互动", lambda: (
    setattr(pet, "hop_ticks", 0), pet._cheer(),
    pet.hop_ticks > 0 or (_ for _ in ()).throw(
        AssertionError("打气未触发加油动作"))))
check("深呼吸引导（含防重入）", lambda: (
    setattr(pet, "_relaxing", False), pet._relax(),
    pet._relaxing is True or (_ for _ in ()).throw(
        AssertionError("未进入放松")),
    pet._relax(),                      # 重入应被忽略
    pet._relax_done(),
    pet._relaxing is False or (_ for _ in ()).throw(
        AssertionError("放松未复位"))))
check("v2.2 新台词分类齐全", lambda: (
    all(k in pet.bank.data for k in (
        "cheer", "relax_in", "relax_hold", "relax_out", "relax_done")) or (
        _ for _ in ()).throw(AssertionError("缺少新台词分类"))))
check("气泡跟随角色移动（守卫）", lambda: (
    setattr(pet, "fullscreen_quiet", False),
    pet.bubble.hide(), _move_center(-40), pet.say("跟随测试一下"),
    app.processEvents(),
    _move_center(40), app.processEvents(),   # 靠事件过滤器自动跟随
    abs((pet.bubble.x() + pet.bubble.width() // 2)
        - (pet.x() + pet.width() // 2)) <= 6 or (
        _ for _ in ()).throw(AssertionError("气泡未跟随角色居中")),
    pet.bubble._on_fade_done()))
check("气泡用实时定位（排队回放不脱节）", lambda: (
    _move_center(), app.processEvents(),
    pet.bubble._show("回放台词", QRect(50, 50, 10, 10)), app.processEvents(),
    abs((pet.bubble.x() + pet.bubble.width() // 2)
        - (pet.x() + pet.width() // 2)) <= 6 or (
        _ for _ in ()).throw(AssertionError("气泡未采用角色实时位置")),
    pet.bubble._on_fade_done()))
check("用户互动打断排队（守卫）", lambda: (
    pet.bubble.hide(), pet.say("排队A"), app.processEvents(),
    pet.say("排队B"), app.processEvents(),
    pet.say("打断C", interrupt=True), app.processEvents(),
    (len(pet.bubble._queue) == 0 and "打断C" in pet.bubble._text) or (
        _ for _ in ()).throw(AssertionError("打断未清队列或未立即插播")),
    pet.bubble._on_fade_done()))
check("开机出场动画（守卫）", lambda: (
    pet._play_entrance(),
    pet._ent_scale < 0.5 or (_ for _ in ()).throw(
        AssertionError("出场起始缩放应很小")),
    pet.windowOpacity() < 0.05 or (_ for _ in ()).throw(
        AssertionError("出场应从透明开始")),
    setattr(pet, "_ent_start", isla_pet.time.monotonic() - 5),
    pet._entrance_step(),
    (pet._ent_scale > 0.99 and pet.windowOpacity() > 0.99
     and not pet._ent_timer.isActive()) or (_ for _ in ()).throw(
        AssertionError("出场结束未复位到原大小/不透明"))))


def _test_restore_file():
    pet._pomo_start("focus")
    saved = _save_roundtrip()
    pending = len(_deferred)
    restored = isla_pet.IslaPet()
    try:
        assert restored.save["stats"] == saved["stats"]
        assert restored.save["memories"] == saved["memories"]
        assert restored.save["capsules"] == saved["capsules"]
        assert restored.save["alarms"] == saved["alarms"]
        assert restored.save["theme"] == saved["theme"]
        assert [[t.isoformat(), text] for t, text in restored.reminders] == saved["reminders"]
        assert [restored.pomo_state, restored.pomo_end.isoformat()] == saved["pomo"]
        assert _read_saved() == saved, "重新加载意外覆盖了存档"
    finally:
        del _deferred[pending:]
        restored.bubble.close()
        restored.bubble.deleteLater()
        restored.close()
        restored.deleteLater()
        QApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def _test_api_fixture():
    count = len(_api_calls)
    pet._brief_pending = False
    pet._daily_brief(manual=True)
    assert len(_api_calls) == count + 1, "没有经过真实 API 请求/解析路径"
    assert pet._brief_result == BRIEF_FIXTURE["data"]["news"][:2]
    pet._brief_tick()
    assert not pet._brief_pending
    assert _read_saved()["brief_date"] == datetime.now().date().isoformat()


def _test_api_failure():
    with patch.object(isla_pet.urllib.request, "urlopen", side_effect=OSError("fixture error")):
        pet._fetch_brief_bg()
    assert pet._brief_result == [], "网络失败未转换成空早报"


def _test_silent_audio():
    pet._load_noise()
    pet._toggle_noise(True)
    assert isinstance(pet.noise, _SilentSound) and pet.noise.playing
    assert pet.noise.loops == _SilentSound.Infinite
    assert pet.noise.volume == 0.35
    assert _read_saved()["noise_on"] is True
    pet.noise.stop()
    pet._restore_noise()
    assert pet.noise.playing
    pet._toggle_noise(False)
    assert not pet.noise.playing and _read_saved()["noise_on"] is False


def _test_interaction_timers():
    pet._begin_interaction()
    fired = []
    pet._schedule_interaction(0, lambda: fired.append("first"))
    app.processEvents()
    assert fired == ["first"] and not pet._interaction_timers
    pet._schedule_interaction(0, lambda: fired.append("cancelled"))
    pet._begin_interaction()
    app.processEvents()
    assert fired == ["first"] and not pet._interaction_timers


def _test_interaction_cleanup():
    fired = []
    pet._dance()
    pet._play_entrance()
    pet._schedule_interaction(0, lambda: fired.append("stale"))
    pet.say("旧台词")
    pet.say("旧排队")
    pet._begin_interaction()
    app.processEvents()
    assert not fired and not pet._interaction_timers
    assert not pet.dance_seq and not pet.dance_timer.isActive()
    assert not pet._ent_timer.isActive() and pet._ent_scale == 1.0
    assert pet.windowOpacity() > 0.99
    assert not pet.bubble.isVisible() and not pet.bubble._queue


def _test_say_only_replaces_bubble():
    pet._dance()
    pet._play_entrance()
    pet._schedule_interaction(5000, lambda: None)
    state = (pet.state, pet.hop_ticks, list(pet.hearts), list(pet.dance_seq),
             set(pet._interaction_timers), pet._ent_scale)
    pet.say("替换气泡但保留动作", interrupt=True)
    assert state == (pet.state, pet.hop_ticks, pet.hearts, pet.dance_seq,
                     pet._interaction_timers, pet._ent_scale)
    assert pet.dance_timer.isActive() and pet._ent_timer.isActive()
    assert pet.bubble._text == "替换气泡但保留动作" and not pet.bubble._queue
    pet._begin_interaction()


check("真实临时存档恢复提醒/番茄钟及养成字段", _test_restore_file)
check("API 固定 fixture 请求、解析及落档", _test_api_fixture)
check("API 失败 fixture 无网络兜底", _test_api_failure)
check("白噪音静音替身开关及恢复", _test_silent_audio)
check("互动 QTimer 执行一次及取消", _test_interaction_timers)
check("新互动清理旧回调/舞蹈/出场/气泡", _test_interaction_cleanup)
check("say interrupt 仅替换气泡不清理动作", _test_say_only_replaces_bubble)
check("没有沙箱外写入或真实联网", lambda: (
    not _violations or (_ for _ in ()).throw(AssertionError(str(_violations)))))


def report():
    _cleanup()                           # 完成凭据必须在 Qt 清理之后落盘
    ok = sum(1 for good, _, _ in results if good)
    print("=" * 56)
    for good, name, err in results:
        print(("  PASS  " if good else "  FAIL  ") + name + ("  " + err if err else ""))
    print("=" * 56)
    print("通过 %d / %d" % (ok, len(results)), flush=True)
    (ROOT / "result.json").write_text(json.dumps({
        "completed": True, "passed": ok, "total": len(results), "source": SOURCE_HASH,
    }), encoding="utf-8")
    return 0 if results and ok == len(results) else 1


sys.exit(report())
