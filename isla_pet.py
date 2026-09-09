# -*- coding: utf-8 -*-
"""
IslaPet —— 以《可塑性记忆》艾拉为灵感的原创桌面宠物
功能：透明置顶挂机、呼吸/眨眼/拖拽/害羞/瞌睡动画、全屏闲逛、摸头/投喂/猜拳
     等互动、番茄钟与自定义提醒、节日与纪念日祝福、好感度与心情系统、
     骰子/硬币/跳舞/烟花/白噪音/每日运势/时间胶囊/成就/记忆碎片/主题换肤等。
"""
import ctypes
import ctypes.wintypes as wintypes
import json
import logging
import math
import os
import random
import sys
import tempfile
import threading
import time
import wave
from array import array
from copy import deepcopy
from datetime import datetime, date, timedelta

try:                                    # 声音能力非必须，缺失时自动降级
    from PySide6.QtMultimedia import QSoundEffect
    _HAS_SOUND = True
except Exception:
    QSoundEffect = None
    _HAS_SOUND = False

try:                                    # 心情滤镜的冷色调版本需要 PIL（可选）
    from PIL import Image as PILImage
    _HAS_PIL = True
except Exception:
    PILImage = None
    _HAS_PIL = False

from PySide6.QtCore import (Qt, QTimer, QPoint, QRect, QUrl, QEasingCurve,
                            QPropertyAnimation, QAbstractAnimation, QLockFile)
from PySide6.QtGui import (QAction, QColor, QCursor, QFont, QFontMetrics,
                           QGuiApplication, QIcon, QImage, QPainter,
                           QPainterPath, QPen, QPixmap, QRadialGradient)
from PySide6.QtWidgets import (QApplication, QDialog, QInputDialog, QLabel,
                               QMenu, QMessageBox, QSystemTrayIcon,
                               QVBoxLayout, QWidget)

APP_NAME = "IslaPet"
APP_VERSION = "2.1.0"
BASE_HEIGHTS = {"小 (200px)": 200, "中 (260px)": 260, "大 (320px)": 320}
DEFAULT_SIZE = "中 (260px)"

# ---- 日志：写进 %APPDATA%\IslaPet\logs\（失败时降级到控制台） ----
LOG_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"),
                       APP_NAME, "logs")


def _init_logging():
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        logging.basicConfig(
            filename=os.path.join(LOG_DIR, "isla_pet.log"),
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s")
    except OSError:
        logging.basicConfig(level=logging.INFO)


def _install_excepthook():
    """未捕获异常落盘：windowed exe 没有控制台，否则崩溃时桌宠凭空消失、查无痕迹。"""
    def hook(etype, value, tb):
        try:
            logging.critical("未捕获异常，程序即将退出",
                             exc_info=(etype, value, tb))
        except Exception:
            pass
        sys.__excepthook__(etype, value, tb)
    sys.excepthook = hook


# ---- 时序与动画常量（tick = 100ms 心跳一格） ----
TICK_MS = 100
SECOND_CHECK_MS = 5 * 1000
MINUTE_CHECK_MS = 30 * 1000
SLEEP_AFTER_TICKS = 1800            # 3 分钟无操作 -> 坐下打瞌睡
MOOD_DECAY_TICKS = 9000             # 约 15 分钟无互动 -> 心情 -1
WANDER_COOLDOWN = (80, 300)         # 闲逛间隔 8~30 秒（tick）
WANDER_COOLDOWN_NEAR = (30, 100)    # 目标点太近时的短等待（tick）
WANDER_SPEED = 0.09                 # 闲逛速度 px/ms（约 90px/s）
DROP_ANIM_MS = 420                  # 落回任务栏动画时长
SETTLE_ANIM_MS = 320                # 屏幕内归位动画时长
BUBBLE_SHOW_MS = 4000               # 气泡显示时长
BUBBLE_FADE_MS = 600                # 气泡淡出时长
BUBBLE_QUEUE_MAX = 8                # 台词队列上限，防止积压
SCARE_CD_TICKS = 60                 # 中键惊吓冷却
ZOOM_CD_TICKS = 50                  # 滚轮缩放冷却
BREATH_SPEED = 0.055                # 呼吸相位增量
BREATH_AMP = 3.0                    # 呼吸起伏幅度 px
HOP_AMP = 14.0                      # 开心小跳幅度 px
BLINK_TICKS = 2                     # 眨眼 0.2 秒

# 公历固定节日（农历节日需要额外历法表，此处只收公历）
FESTIVALS = {
    "01-01": "元旦", "02-14": "情人节", "03-08": "妇女节", "04-01": "愚人节",
    "05-01": "劳动节", "05-04": "青年节", "06-01": "儿童节", "09-10": "教师节",
    "10-01": "国庆节", "11-11": "单身节", "12-24": "平安夜", "12-25": "圣诞节",
}
RPS = ("石头", "剪刀", "布")

# ---- 主题换肤：气泡 / 粒子 / 烟花主色调 ----
THEMES = {
    "樱花粉":  {"bubble": (225, 120, 130), "particle": (240, 120, 150),
                "spark": (255, 170, 90),   "desc": "樱花粉 · 默认"},
    "薄荷蓝":  {"bubble": (110, 180, 200), "particle": (120, 190, 220),
                "spark": (150, 220, 190),  "desc": "薄荷蓝 · 清爽"},
    "丁香紫":  {"bubble": (170, 140, 210), "particle": (190, 150, 230),
                "spark": (240, 200, 120),  "desc": "丁香紫 · 温柔"},
    "柠檬黄":  {"bubble": (220, 180, 90),  "particle": (240, 200, 110),
                "spark": (255, 140, 120),  "desc": "柠檬黄 · 元气"},
}

# ---- 等级称号：按连续陪伴天数计算 ----
LEVELS = (
    (1, "初识"), (3, "熟络"), (7, "好友"), (14, "挚友"),
    (30, "家人"), (60, "重要的人"), (100, "相伴一生"),
)

# ---- 成就系统：(id, 名称, 描述, 判定函数(save, stats)) ----
def _st(stats, key, default=0):
    return stats.get(key, default) if isinstance(stats, dict) else default


def _def_achievements():
    return [
        ("first_touch", "初次相遇", "完成第一次互动", lambda s, st: s.get("affection", 0) >= 1),
        ("pat_10", "摸头十连", "摸头 10 次", lambda s, st: _st(st, "pat") >= 10),
        ("feed_5", "点心之友", "投喂点心 5 次", lambda s, st: _st(st, "feed") >= 5),
        ("tea_5", "泡茶苦手", "泡茶 5 次", lambda s, st: _st(st, "tea") >= 5),
        ("rps_win_3", "猜拳大师", "猜拳赢 3 次", lambda s, st: _st(st, "rps_win") >= 3),
        ("dice_10", "骰子狂热", "掷骰子 10 次", lambda s, st: _st(st, "dice") >= 10),
        ("dance_1", "翩翩起舞", "一起跳过舞", lambda s, st: _st(st, "dance") >= 1),
        ("fortune_10", "占卜常客", "抽签 10 次", lambda s, st: _st(st, "fortune") >= 10),
        ("capsule_1", "寄往未来", "写下第一枚时间胶囊", lambda s, st: _st(st, "capsule") >= 1),
        ("aff_30", "羁绊萌芽", "好感度达到 30", lambda s, st: s.get("affection", 0) >= 30),
        ("aff_80", "心意相通", "好感度达到 80", lambda s, st: s.get("affection", 0) >= 80),
        ("aff_160", "无可替代", "好感度达到 160", lambda s, st: s.get("affection", 0) >= 160),
        ("streak_7", "七日之约", "连续陪伴 7 天", lambda s, st: s.get("streak", 0) >= 7),
        ("streak_30", "满月相伴", "连续陪伴 30 天", lambda s, st: s.get("streak", 0) >= 30),
        ("mood_100", "心花怒放", "心情达到满值 100", lambda s, st: s.get("mood", 0) >= 100),
        ("play_50", "形影不离", "累计互动 50 次", lambda s, st: sum(
            _st(st, k) for k in ("pat", "feed", "tea", "dice", "coin", "dance",
                                 "fortune", "scare", "rps_win", "rps_lose",
                                 "rps_draw")) >= 50),
        ("firework_1", "烟火人间", "为你放一次烟花", lambda s, st: _st(st, "firework") >= 1),
        ("alarm_1", "人形闹钟", "设置过闹钟", lambda s, st: _st(st, "alarm") >= 1),
    ]


DEFAULT_SAVE = {
    "affection": 0, "unlocked": 0, "pos": None, "size_key": DEFAULT_SIZE,
    "chime_on": True, "sit_on": True, "sleep_on": True, "wander_on": True,
    "follow_on": False, "initiative_on": True,
    "mood": 60,                  # 心情 0~100
    "streak": 0, "last_login": None,
    "birthday": None,            # "MM-DD"
    "anniv_name": None, "anniv_date": None,   # 纪念日名称 / "YYYY-MM-DD"
    "pomo_focus": 25, "pomo_break": 5,
    # ---- 以下为 v2.0 新增 ----
    "theme": "樱花粉",           # 主题换肤
    "total_seconds": 0,          # 累计陪伴秒数
    "stats": {},                 # 互动统计 {互动名: 次数}
    "memories": {},              # 记忆碎片 {key: "YYYY-MM-DD"}
    "achievements": [],          # 已解锁成就 id 列表
    "capsules": [],              # 时间胶囊 [[到期ISO, 内容], ...]
    "alarms": [],                # 闹钟 ["HH:MM", ...]
    "noise_on": False,           # 白噪音开关
    "fortune": None,             # 今日运势 ["YYYY-MM-DD", 等级, 内容]
    "reminders": [],             # 自定义提醒 [[到期ISO时间, 内容], ...]
    "pomo": None,                # 进行中的番茄钟 [阶段, 结束ISO时间]
    "dnd_on": True,              # 前台全屏时自动免打扰（改托盘通知）
}


def res_path(rel):
    """打包后资源在 _MEIPASS 临时目录，开发时在脚本目录。"""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def app_dir():
    """exe / 脚本所在目录（外部台词库、存档优先放这里）。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def data_file():
    d = app_dir()
    if os.access(d, os.W_OK):
        return os.path.join(d, "isla_save.json")
    d = os.path.join(os.environ.get("APPDATA", d), APP_NAME)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "isla_save.json")


class DialogueBank:
    """台词库：优先读 exe 旁的 dialogues.json（方便用户自己加台词），
    否则读打包进 exe 的内置版本。"""

    def __init__(self):
        self.data = {}
        for p in (os.path.join(app_dir(), "dialogues.json"),
                  res_path("dialogues.json")):
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        self.data = json.load(f)
                    break
                except Exception:
                    pass

    def pick(self, key, **fmt):
        lines = self.data.get(key) or ["……"]
        line = random.choice(lines)
        try:
            return line.format(**fmt)
        except Exception:
            return line

class SpeechBubble(QWidget):
    """圆角台词气泡，显示 4 秒后淡出。"""

    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool |
                         Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._text = ""
        self.theme = "樱花粉"          # 主题换肤（由 IslaPet.say 同步）
        self._font = QFont("Microsoft YaHei", 10)
        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(BUBBLE_FADE_MS)
        self._fade.setStartValue(1.0)
        self._fade.setEndValue(0.0)
        self._fade.finished.connect(self._on_fade_done)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fade.start)
        self._queue = []                     # 排队台词 [(text, anchor_rect), ...]

    def popup(self, text, anchor_rect):
        """anchor_rect: 角色的全局矩形，气泡显示在其上方。
        正在显示时新台词进入队列，淡出完毕后依次播放，避免互相覆盖。"""
        if self.isVisible():
            if len(self._queue) < BUBBLE_QUEUE_MAX:
                self._queue.append((text, anchor_rect))
            return
        self._show(text, anchor_rect)

    def _show(self, text, anchor_rect):
        if self._fade.state() == QAbstractAnimation.Running:
            self._fade.stop()
        self._timer.stop()
        self._text = text
        fm = QFontMetrics(self._font)
        max_w = 240
        rect = fm.boundingRect(QRect(0, 0, max_w, 1000),
                               Qt.TextWordWrap, text)
        w, h = rect.width() + 28, rect.height() + 22
        self.resize(w, h + 10)  # +10 给小尾巴留空间
        x = anchor_rect.center().x() - w // 2
        y = anchor_rect.top() - h - 14
        screen = QGuiApplication.screenAt(anchor_rect.center())
        if screen:
            g = screen.availableGeometry()
            x = max(g.left() + 4, min(x, g.right() - w - 4))
            y = max(g.top() + 4, y)
        self.move(x, y)
        self.setWindowOpacity(1.0)
        self.show()
        self.update()
        # 长内容多给点阅读时间：短句 4 秒起步，每行再加约 1.1 秒，最多 14 秒
        extra = 1.1 * (max(1, len(text) // 14) - 1)
        self._timer.start(int(min(BUBBLE_SHOW_MS * 3.5,
                                  BUBBLE_SHOW_MS + extra * 1000)))

    def _on_fade_done(self):
        """淡出完毕后播放下一条排队台词。"""
        self.hide()
        if self._queue:
            text, rect = self._queue.pop(0)
            self._show(text, rect)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height() - 10
        path = QPainterPath()
        path.addRoundedRect(1, 1, w - 2, h - 2, 10, 10)
        # 底部小尾巴
        cx = w // 2
        path.moveTo(cx - 7, h - 1)
        path.lineTo(cx, h + 8)
        path.lineTo(cx + 7, h - 1)
        p.setPen(QPen(QColor(*THEMES.get(
            self.theme, THEMES["樱花粉"])["bubble"]), 1.5))
        p.setBrush(QColor(255, 250, 250, 242))
        p.drawPath(path)
        p.setPen(QColor(90, 70, 75))
        p.setFont(self._font)
        p.drawText(QRect(14, 11, w - 28, h - 22), Qt.TextWordWrap, self._text)

class FireworkOverlay(QWidget):
    """全屏透明烟花特效：点击穿透、不抢焦点，约 5 秒后自动消失。"""

    def __init__(self, parent=None):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool |
                         Qt.WindowStaysOnTopHint |
                         Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setGeometry(QGuiApplication.primaryScreen().virtualGeometry())
        self.particles = []          # [x, y, vx, vy, life, maxlife, (r,g,b)]
        self._timer = QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._step)
        self._launcher = QTimer(self)
        self._launcher.setInterval(380)
        self._launcher.timeout.connect(self._burst)

    def launch(self, waves=3, geo=None):
        """geo: 烟花所在屏幕的完整几何（多显示器时跟随宠物所在屏）。"""
        self.setGeometry(geo or QGuiApplication.primaryScreen().virtualGeometry())
        self.show()
        self.raise_()
        self.particles.clear()
        self._burst()
        self._launcher.start()
        QTimer.singleShot(380 * waves + 900, self._launcher.stop)
        QTimer.singleShot(380 * waves + 2600, self._check_finish)
        if not self._timer.isActive():
            self._timer.start()

    def _burst(self):
        g = self.geometry()
        x = random.uniform(g.left() + 80, g.right() - 80)
        y = random.uniform(g.top() + 80, g.bottom() - 80)
        color = random.choice([
            (255, 90, 110), (255, 200, 80), (120, 220, 160),
            (130, 180, 255), (240, 150, 240), (255, 240, 150)])
        for _ in range(46):
            ang = random.uniform(0, math.tau)
            spd = random.uniform(1.2, 7.0)
            self.particles.append([
                x, y, math.cos(ang) * spd, math.sin(ang) * spd,
                random.uniform(0.55, 1.0), 1.0, color])

    def _step(self):
        alive = []
        for p in self.particles:
            p[0] += p[2]
            p[1] += p[3]
            p[3] += 0.06
            p[2] *= 0.985
            p[4] -= 0.012
            if p[4] > 0:
                alive.append(p)
        self.particles = alive
        self.update()

    def _check_finish(self):
        if not self.particles:
            self.hide()
            self._timer.stop()

    def paintEvent(self, _):
        if not self.particles:
            self.hide()
            self._timer.stop()
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        for x, y, _vx, _vy, life, maxlife, color in self.particles:
            alpha = int(255 * max(0.0, life / maxlife))
            r = 1.5 + 2.5 * (life / maxlife)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(color[0], color[1], color[2], alpha))
            p.drawEllipse(int(x - r), int(y - r), int(r * 2), int(r * 2))

class InfoDialog(QDialog):
    """无边框信息面板：不抢焦点，点击任意处关闭。
    用于完整展示成就 / 回忆 / 统计等长列表（气泡放不下）。"""

    def __init__(self, anchor, title, lines):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool |
                         Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 14)
        lay.setSpacing(6)
        t = QLabel(title)
        tf = QFont("Microsoft YaHei", 10)
        tf.setBold(True)
        t.setFont(tf)
        body = QLabel("\n".join(lines))
        body.setFont(QFont("Microsoft YaHei", 9))
        body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(t)
        lay.addWidget(body)
        self.adjustSize()
        # 显示在角色上方，超出屏幕时回弹
        gr = anchor.frameGeometry()
        screen = QGuiApplication.screenAt(gr.center()) \
            or QGuiApplication.primaryScreen()
        g = screen.availableGeometry()
        x = gr.center().x() - self.width() // 2
        y = gr.top() - self.height() - 10
        x = max(g.left() + 4, min(x, g.right() - self.width() - 4))
        y = max(g.top() + 4, min(y, g.bottom() - self.height() - 4))
        self.move(x, y)
        self.show()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 250, 250, 245))
        p.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 10, 10)

    def mousePressEvent(self, _):
        self.close()


class IslaPet(QWidget):
    STATES = ("idle", "blink", "shy", "panic", "sleep", "tea")

    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool |
                         Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        self.bank = DialogueBank()
        self.save = deepcopy(DEFAULT_SAVE)
        self._load_save()
        # 从存档恢复自定义提醒（防重启丢失）
        self.reminders = []
        for raw, txt in (self.save.get("reminders") or []):
            try:
                self.reminders.append((datetime.fromisoformat(raw), txt))
            except (ValueError, TypeError):
                continue

        # 原始素材
        self.raw = {}
        for name in self.STATES:
            pm = QPixmap(res_path(os.path.join("assets", name + ".png")))
            self.raw[name] = pm
        self.frames = {}
        self._apply_size(self.save.get("size_key", DEFAULT_SIZE), first=True)

        self.bubble = SpeechBubble()

        # ---- 状态机 ----
        self.state = "idle"          # 当前显示的姿势
        self.state_until = 0.0       # 临时状态的结束时刻 (ms tick 计数)
        self.breath_phase = 0.0      # 呼吸相位
        self.dragging = False
        self.drag_offset = QPoint()
        self.sleeping = False
        self.idle_ticks = 0          # 无操作计数（100ms/格）
        self.press_pos = None
        self.press_local = None      # 按下点在窗口内的坐标（区分头/身）
        self.click_timer = QTimer(self)   # 区分单击/双击
        self.click_timer.setSingleShot(True)
        self.click_timer.timeout.connect(self._single_click)

        # 动画心跳：100ms 一帧足够呼吸+眨眼，CPU 占用极低
        self.tick_timer = QTimer(self)
        self.tick_timer.timeout.connect(self._tick)
        self.tick_timer.start(TICK_MS)

        # 分钟级定时器：整点报时 / 久坐 / 睡觉提醒
        self.minute_timer = QTimer(self)
        self.minute_timer.timeout.connect(self._minute_check)
        self.minute_timer.start(MINUTE_CHECK_MS)
        self.last_chimed_hour = datetime.now().hour
        self.sit_start = datetime.now()
        self.sleep_reminded_day = None

        # 秒级定时器：番茄钟阶段切换 / 自定义提醒到点
        self.second_timer = QTimer(self)
        self.second_timer.timeout.connect(self._second_check)
        self.second_timer.start(SECOND_CHECK_MS)
        self._acc_seconds = self.save.get("total_seconds", 0)   # 陪伴累计秒数
        self._last_second = time.monotonic()                    # 上次计时刻度

        self.temp_state_ticks = 0    # 临时姿势剩余 tick 数
        self.drop_anim = None
        self.wander_anim = None      # 闲逛移动动画
        self.facing_left = False     # 移动朝向（镜像绘制）
        self.wander_cooldown = random.randint(*WANDER_COOLDOWN)  # 距下次闲逛的 tick 数

        self.hearts = []             # 通用粒子 [x, y, vx, vy, life, type]
        self.hop_ticks = 0           # 投喂/开心时的小跳剩余 tick
        self.initiative_cd = random.randint(2400, 4800)  # 主动搭话冷却
        self.mood_decay = 0          # 心情衰减计时
        self._sad_hint_done = False  # 心情低谷求助提示（只提示一次）
        self.fullscreen_quiet = False  # 前台全屏中（免打扰）

        # 番茄钟 / 自定义提醒
        self.pomo_state = None       # None / "focus" / "break"
        self.pomo_end = None
        # 恢复上次进行中的番茄钟（已过期的丢弃，不再补播提示）
        pomo = self.save.get("pomo")
        if isinstance(pomo, (list, tuple)) and len(pomo) == 2:
            try:
                end = datetime.fromisoformat(pomo[1])
                if end > datetime.now():
                    self.pomo_state, self.pomo_end = pomo[0], end
                else:
                    self.save["pomo"] = None
            except (ValueError, TypeError):
                self.save["pomo"] = None

        # ---- v2.0 新功能状态 ----
        self.dance_seq = []          # 跳舞姿势序列
        self.dance_timer = QTimer(self)
        self.dance_timer.setSingleShot(True)
        self.dance_timer.timeout.connect(self._dance_step)
        self.scare_cd = 0            # 中键惊吓冷却（tick）
        self.zoom_cd = 0             # 滚轮缩放冷却（tick）
        self.noise = None            # 白噪音播放器
        self._noise_ready = False    # 后台线程生成 wav 完成标志
        self.tray = None             # 系统托盘（由 main 注入，用于气泡通知）
        self.firework = None         # 全屏烟花窗口（懒创建）
        self._load_noise()           # 后台预生成白噪音 wav（失败无害）
        if self.save.get("noise_on"):
            QTimer.singleShot(1500, self._restore_noise)   # 恢复上次的白噪音
        self._check_achievements(silent=True)   # 启动静默同步已满足成就

        self._check_login_streak()

        self._place_initial()
        self.show()
        QTimer.singleShot(600, self._greet)
        QTimer.singleShot(5200, self._daily_notes)

    # ---------- 存档 ----------
    def _load_save(self):
        path = data_file()
        if not os.path.exists(path):
            self._sanitize_save()
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if not isinstance(loaded, dict):
                raise ValueError("存档根节点不是 JSON 对象")
            self.save.update(loaded)
        except Exception as exc:
            logging.warning("存档读取失败，已重置：%s", exc)
            self._backup_corrupt_save(path)   # 损坏原件留底，避免养成数据彻底丢失
        self._sanitize_save()

    def _backup_corrupt_save(self, path):
        try:
            if os.path.exists(path):
                os.replace(path, path + ".bak")
        except OSError:
            pass

    def _sanitize_save(self):
        """校验存档字段类型，手改/损坏时回落默认值，避免运行时崩溃。"""
        s = self.save
        for k in ("stats", "memories"):
            if not isinstance(s.get(k), dict):
                s[k] = {}
        for k in ("achievements", "capsules", "alarms", "reminders"):
            if not isinstance(s.get(k), list):
                s[k] = []
        for k in ("affection", "mood", "streak", "unlocked", "total_seconds",
                  "pomo_focus", "pomo_break"):
            if not isinstance(s.get(k), (int, float)):
                s[k] = DEFAULT_SAVE[k]
        if s.get("theme") not in THEMES:
            s["theme"] = DEFAULT_SAVE["theme"]
        if s.get("size_key") not in BASE_HEIGHTS:
            s["size_key"] = DEFAULT_SAVE["size_key"]
        pos = s.get("pos")
        if not (isinstance(pos, list) and len(pos) == 2
                and all(isinstance(v, (int, float)) for v in pos)):
            s["pos"] = None
        for k, v in DEFAULT_SAVE.items():
            s.setdefault(k, deepcopy(v))

    def save_data(self):
        self.save["pos"] = [self.x(), self.y()]
        self.save["reminders"] = [[t.isoformat(), txt]
                                  for t, txt in self.reminders]
        self.save["total_seconds"] = self._acc_seconds
        # 番茄钟进行中就存下来，重启后接着走（过期的在启动时丢弃）
        self.save["pomo"] = ([self.pomo_state, self.pomo_end.isoformat()]
                             if self.pomo_state and self.pomo_end else None)
        path = data_file()
        tmp = path + ".tmp"
        try:
            # 先写临时文件再原子替换，防止写一半断电损坏存档
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.save, f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
        except Exception as exc:
            logging.warning("存档写入失败：%s", exc)

    def _cold_pixmap(self, pm):
        """心情低落时的冷色调立绘（PIL 快速调色，无 PIL 则原样返回）。"""
        if not _HAS_PIL:
            return pm
        img = pm.toImage().convertToFormat(QImage.Format_ARGB32)
        w, h = img.width(), img.height()
        data = bytes(img.constBits())[:h * img.bytesPerLine()]
        pil = PILImage.frombytes("RGBA", (w, h), data, "raw", "BGRA")
        r, g, b, a = pil.split()
        # 温和的"心情低"偏色：轻微降红提蓝，不再像重滤镜
        r = r.point(lambda v: int(v * 0.78))
        g = g.point(lambda v: int(v * 0.82))
        b = b.point(lambda v: min(255, int(v * 1.06)))
        pil = PILImage.merge("RGBA", (r, g, b, a))
        out = QImage(pil.tobytes("raw", "BGRA"), w, h,
                     img.bytesPerLine(), QImage.Format_ARGB32).copy()
        return QPixmap.fromImage(out)

    # ---------- 尺寸 / 位置 ----------
    def _apply_size(self, key, first=False):
        key = key if key in BASE_HEIGHTS else DEFAULT_SIZE
        self.save["size_key"] = key
        h = BASE_HEIGHTS[key]
        self.frames = {}
        self.cold_frames = {}
        for name, pm in self.raw.items():
            if pm.isNull():
                self.frames[name] = QPixmap()
                self.cold_frames[name] = QPixmap()
                continue
            scaled = pm.scaledToHeight(h, Qt.SmoothTransformation)
            self.frames[name] = scaled
            self.cold_frames[name] = self._cold_pixmap(scaled)
        w = max((p.width() for p in self.frames.values() if not p.isNull()),
                default=200)
        self.setFixedSize(w, h + 8)  # 底部留 8px 呼吸位移余量
        if not first:
            self._stop_wander()
            if self.save.get("wander_on", True):
                self._settle_in_screen()
            else:
                self._snap_to_taskbar()
            self.update()

    def _screen_geo(self):
        s = QGuiApplication.screenAt(self.geometry().center()) \
            or QGuiApplication.primaryScreen()
        return s.availableGeometry()

    def _place_initial(self):
        pos = self.save.get("pos")
        g = self._screen_geo()
        if pos and isinstance(pos, list) and len(pos) == 2:
            x = max(g.left(), min(int(pos[0]), g.right() - self.width()))
            y = max(g.top(), min(int(pos[1]), g.bottom() - self.height()))
            self.move(x, y)
        else:
            # 默认右下角，站在任务栏上沿
            self.move(g.right() - self.width() - 24,
                      g.bottom() - self.height() + 1)

    def _snap_to_taskbar(self):
        """松手后落回任务栏上沿（可用区域底部）。"""
        g = self._screen_geo()
        x = max(g.left(), min(self.x(), g.right() - self.width()))
        target = QPoint(x, g.bottom() - self.height() + 1)
        self.drop_anim = QPropertyAnimation(self, b"pos", self)
        self.drop_anim.setDuration(DROP_ANIM_MS)
        self.drop_anim.setStartValue(self.pos())
        self.drop_anim.setEndValue(target)
        self.drop_anim.setEasingCurve(QEasingCurve.OutBounce)
        self.drop_anim.start()

    def _settle_in_screen(self):
        """闲逛模式下松手：只约束回屏幕内，不强制落回底部。"""
        g = self._screen_geo()
        x = max(g.left(), min(self.x(), g.right() - self.width()))
        y = max(g.top(), min(self.y(), g.bottom() - self.height()))
        if QPoint(x, y) == self.pos():
            return
        self.drop_anim = QPropertyAnimation(self, b"pos", self)
        self.drop_anim.setDuration(SETTLE_ANIM_MS)
        self.drop_anim.setStartValue(self.pos())
        self.drop_anim.setEndValue(QPoint(x, y))
        self.drop_anim.setEasingCurve(QEasingCurve.OutBounce)
        self.drop_anim.start()

    # ---------- 闲逛 ----------
    def _wandering(self):
        return (self.wander_anim is not None and
                self.wander_anim.state() == QAbstractAnimation.Running)

    def _stop_wander(self):
        if self.wander_anim:
            self.wander_anim.stop()
        self.wander_cooldown = random.randint(*WANDER_COOLDOWN)  # 8~30 秒后再逛

    def _start_wander(self):
        g = self._screen_geo()
        tx = random.randint(g.left(), max(g.left(), g.right() - self.width()))
        ty = random.randint(g.top(), max(g.top(), g.bottom() - self.height()))
        dist = math.hypot(tx - self.x(), ty - self.y())
        if dist < 40:  # 目标太近就再等等
            self.wander_cooldown = random.randint(*WANDER_COOLDOWN_NEAR)
            return
        self.facing_left = tx < self.x()
        self.wander_anim = QPropertyAnimation(self, b"pos", self)
        self.wander_anim.setDuration(int(dist / WANDER_SPEED))  # 约 90px/s，慢悠悠地飘
        self.wander_anim.setStartValue(self.pos())
        self.wander_anim.setEndValue(QPoint(tx, ty))
        self.wander_anim.setEasingCurve(QEasingCurve.InOutSine)
        self.wander_anim.finished.connect(self._wander_done)
        self.wander_anim.start()

    def _wander_done(self):
        self.wander_cooldown = random.randint(*WANDER_COOLDOWN)
        if random.random() < 0.35:
            self.say(self.bank.pick("idle_murmur"))

    def _toggle_wander(self, on):
        self.save["wander_on"] = on
        if not on:
            self._stop_wander()
            self._snap_to_taskbar()

    # ---------- 跟随鼠标 ----------
    def _toggle_follow(self, on):
        self.save["follow_on"] = on
        if on:
            self._stop_wander()
            self.say(self.bank.pick("follow_on"))
        else:
            self.say(self.bank.pick("follow_off"))

    def _follow_step(self):
        """每帧朝鼠标缓慢靠近，保持一段距离站在旁边。"""
        c = QCursor.pos()
        # 目标：鼠标左下方一点，避免立绘正好压住光标
        tx = c.x() - self.width() // 2
        ty = c.y() - int(self.height() * 0.55)
        dx, dy = tx - self.x(), ty - self.y()
        dist = math.hypot(dx, dy)
        if dist < 70:            # 已经在身边了就不动
            return
        step = min(12.0, dist * 0.12)   # 越远走越快，上限 12px/帧
        self.facing_left = dx < 0
        g = self._screen_geo()
        nx = int(self.x() + dx / dist * step)
        ny = int(self.y() + dy / dist * step)
        nx = max(g.left(), min(nx, g.right() - self.width()))
        ny = max(g.top(), min(ny, g.bottom() - self.height()))
        self.move(nx, ny)

    # ---------- 粒子系统（爱心/星星/花瓣/火花） ----------
    def _spawn_hearts(self, n=6):
        """向上飘的爱心（旧接口，保留兼容）。"""
        self._spawn_particles(n, "heart", vy=(-1.6, -0.7),
                              spread=0.6, life=(14, 26))

    def _spawn_particles(self, n, ptype, vy=(-1.0, -0.4), spread=0.8,
                         life=(10, 22)):
        """通用粒子：[x, y, vx, vy, life, type]"""
        for _ in range(n):
            self.hearts.append([
                random.uniform(self.width() * 0.3, self.width() * 0.7),
                random.uniform(self.height() * 0.15, self.height() * 0.5),
                random.uniform(-spread, spread),
                random.uniform(*vy),
                random.randint(*life),
                ptype,
            ])

    def _update_hearts(self):
        for h in self.hearts:
            h[0] += h[2]
            h[1] += h[3]
            if h[5] == "petal":            # 花瓣：左右摇摆飘落
                h[2] = math.sin(h[4] * 0.15) * 0.6
                h[3] = min(h[3], 1.2)
            elif h[5] == "spark":          # 火花：减速 + 轻微重力
                h[2] *= 0.90
                h[3] = h[3] * 0.90 + 0.06
            h[4] -= 1
        self.hearts = [h for h in self.hearts if h[4] > 0]

    def _paint_hearts(self, p):
        """按类型绘制粒子，颜色跟随主题，画在立绘后面一层。"""
        th = THEMES.get(self.save.get("theme", "樱花粉"), THEMES["樱花粉"])
        for hx, hy, _vx, _vy, life, ptype in self.hearts:
            alpha = max(0, min(255, int(life * 10)))
            if ptype == "heart":
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(*(th["particle"] + (alpha,))))
                s = 4.0 + life * 0.12
                path = QPainterPath()
                path.moveTo(hx, hy + s)
                path.cubicTo(hx - s * 1.4, hy - s * 0.3,
                             hx - s * 0.4, hy - s * 1.2, hx, hy - s * 0.35)
                path.cubicTo(hx + s * 0.4, hy - s * 1.2,
                             hx + s * 1.4, hy - s * 0.3, hx, hy + s)
                p.drawPath(path)
            elif ptype == "star":          # 五角星（跳舞时的音符）
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(*(th["spark"] + (alpha,))))
                s = 3.0 + life * 0.1
                path = QPainterPath()
                for i in range(10):
                    r = s if i % 2 == 0 else s * 0.45
                    a = math.pi / 5 * i - math.pi / 2
                    xx, yy = hx + r * math.cos(a), hy + r * math.sin(a)
                    if i == 0:
                        path.moveTo(xx, yy)
                    else:
                        path.lineTo(xx, yy)
                path.closeSubpath()
                p.drawPath(path)
            elif ptype == "petal":         # 花瓣：旋转椭圆
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(245, 160, 190, alpha))
                p.save()
                p.translate(hx, hy)
                p.rotate(life * 12)
                p.drawEllipse(-2.5, -1.2, 5, 2.4)
                p.restore()
            else:                          # spark 火花点
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(*(th["spark"] + (alpha,))))
                p.drawEllipse(hx - 1.2, hy - 1.2, 2.4, 2.4)

    # ---------- 动画心跳 ----------
    def _tick(self):
        self.breath_phase = (self.breath_phase + BREATH_SPEED) % (2 * math.pi)
        self.idle_ticks += 1
        if self.scare_cd > 0:
            self.scare_cd -= 1
        if self.zoom_cd > 0:
            self.zoom_cd -= 1
        if self.hearts:
            self._update_hearts()
        if self.hop_ticks > 0:
            self.hop_ticks -= 1
        self._mood_tick()

        if self.temp_state_ticks > 0:
            self.temp_state_ticks -= 1
            if self.temp_state_ticks == 0 and not self.dragging:
                self.state = "sleep" if self.sleeping else "idle"

        if not self.dragging and self.temp_state_ticks == 0:
            # 长时间无操作（3 分钟）-> 回到任务栏上沿坐下打瞌睡
            if not self.sleeping and self.idle_ticks >= SLEEP_AFTER_TICKS \
                    and not self.save.get("follow_on"):
                self.sleeping = True
                self.state = "sleep"
                self._stop_wander()
                self._snap_to_taskbar()
            # 待机时随机眨眼
            if not self.sleeping and self.state == "idle" \
                    and random.random() < 0.03:
                self.state = "blink"
                self.temp_state_ticks = BLINK_TICKS  # 眨眼 0.2 秒
            # 跟随鼠标散步优先于自由闲逛
            if not self.sleeping and self.save.get("follow_on"):
                self._follow_step()
            # 没事的时候在屏幕上闲逛（全屏免打扰时停下来）
            elif not self.sleeping and not self.fullscreen_quiet \
                    and self.save.get("wander_on", True) \
                    and not self._wandering() \
                    and not self.bubble.isVisible():
                self.wander_cooldown -= 1
                if self.wander_cooldown <= 0:
                    self._start_wander()
            # 偶尔主动搭话（番茄钟专注期间、全屏时保持安静）
            if not self.sleeping and not self.fullscreen_quiet \
                    and self.save.get("initiative_on", True) \
                    and self.pomo_state != "focus" \
                    and not self.bubble.isVisible():
                self.initiative_cd -= 1
                if self.initiative_cd <= 0:
                    self.initiative_cd = random.randint(2400, 4800)
                    key = "initiative"
                    if self.save.get("mood", 60) >= 85:
                        key = random.choice(("initiative", "mood_high"))
                    elif self.save.get("mood", 60) <= 25:
                        key = random.choice(("initiative", "mood_low"))
                    self.say(self.bank.pick(key))

        self.update()

    def _mood_tick(self):
        """约每 15 分钟无互动掉 1 点心情，最低 0；跌到低谷时她会开口求助。"""
        self.mood_decay += 1
        if self.mood_decay >= MOOD_DECAY_TICKS:
            self.mood_decay = 0
            self.save["mood"] = max(0, self.save.get("mood", 60) - 1)
        mood = self.save.get("mood", 60)
        if mood <= 10 and not self._sad_hint_done:
            self._sad_hint_done = True
            self.say(self.bank.pick("mood_sad_hint"))
        elif mood > 10 and self._sad_hint_done:
            self._sad_hint_done = False

    def _wake(self):
        self.idle_ticks = 0
        if self.sleeping:
            self.sleeping = False
            self.state = "idle"
            self.say(self.bank.pick("wake_up"))

    def _set_temp_state(self, name, seconds):
        self.state = name
        self.temp_state_ticks = int(seconds * 10)
        self.update()

    # ---------- 绘制 ----------
    def paintEvent(self, _):
        mood = self.save.get("mood", 60)
        pm = self.frames.get(self.state)
        if mood <= 10:                       # 心情跌到低谷：冷色调立绘
            pm = self.cold_frames.get(self.state) or pm
        if pm is None or pm.isNull():
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.setRenderHint(QPainter.Antialiasing)
        # 主题氛围光：柔和光晕铺在立绘身后，让换肤立即可见
        th = THEMES.get(self.save.get("theme", "樱花粉"), THEMES["樱花粉"])
        glow = QRadialGradient(
            self.width() / 2, self.height() - 30,
            max(self.width(), self.height()) * 0.9)
        glow.setColorAt(0, QColor(*(th["particle"] + (66,))))
        glow.setColorAt(1, QColor(*(th["particle"] + (0,))))
        p.save()
        p.setPen(Qt.NoPen)
        p.setBrush(glow)
        p.drawRect(self.rect())
        p.restore()
        if self.hearts:
            self._paint_hearts(p)
        p.save()
        if self.facing_left:  # 朝移动方向镜像
            p.translate(self.width(), 0)
            p.scale(-1, 1)
        # 呼吸：轻微上下浮动 + 极轻微纵向缩放
        dy = 0.0
        if self.state in ("idle", "blink", "tea") and not self.dragging:
            dy = BREATH_AMP * (1 + math.sin(self.breath_phase)) / 2
        if self.hop_ticks > 0:      # 开心时的小跳（半个正弦弧）
            dy -= HOP_AMP * math.sin(math.pi * (self.hop_ticks % 8) / 8)
        x = (self.width() - pm.width()) // 2
        y = self.height() - pm.height() + int(round(dy)) - 4
        p.drawPixmap(x, y, pm)
        p.restore()

    # ---------- 台词 ----------
    def say(self, text, force=False):
        """弹出台词气泡。全屏免打扰时改为托盘通知（force=True 可强制弹窗）。"""
        if self.fullscreen_quiet and not force:
            self._notify("艾拉", text)
            return
        self.bubble.theme = self.save.get("theme", "樱花粉")
        r = QRect(self.mapToGlobal(QPoint(0, 0)), self.size())
        self.bubble.popup(text, r)

    @staticmethod
    def _is_foreground_fullscreen():
        """前台窗口是否占满整屏（全屏游戏/视频/投屏时别去打扰）。"""
        try:
            u32 = ctypes.windll.user32
            hwnd = u32.GetForegroundWindow()
            if not hwnd or hwnd == u32.GetShellWindow():
                return False                       # 无前台窗口 / 桌面
            rect = wintypes.RECT()
            u32.GetWindowRect(hwnd, ctypes.byref(rect))
            if u32.IsIconic(hwnd):                 # 最小化窗口不算
                return False
            return (rect.right - rect.left >= u32.GetSystemMetrics(0) and
                    rect.bottom - rect.top >= u32.GetSystemMetrics(1))
        except Exception:
            return False

    def _update_dnd(self):
        """刷新免打扰状态：进入/退出全屏时各提示一次。"""
        if not self.save.get("dnd_on", True):
            if self.fullscreen_quiet:
                self.fullscreen_quiet = False
            return
        now_full = self._is_foreground_fullscreen()
        if now_full == self.fullscreen_quiet:
            return
        self.fullscreen_quiet = now_full
        if now_full:
            self._stop_wander()
            self._notify("艾拉", "你在忙……我先安静一会儿。")
        else:
            self.say(self.bank.pick("dnd_off"))

    def _greet(self):
        h = datetime.now().hour
        if 0 <= h < 5:
            key = "greeting_late_night"
        elif 5 <= h < 11:
            key = "greeting_morning"
        elif 11 <= h < 18:
            key = "greeting_afternoon"
        else:
            key = "greeting_evening"
        self.say(self.bank.pick(key))

    # ---------- 每日陪伴：登录天数 / 节日 / 纪念日 ----------
    def _check_login_streak(self):
        today = date.today()
        last = self.save.get("last_login")
        try:
            last_day = date.fromisoformat(last) if last else None
        except ValueError:
            last_day = None
        self.streak_msg = None
        if last_day == today:
            return                       # 今天已经打过招呼
        if last_day == today - timedelta(days=1):
            self.save["streak"] = self.save.get("streak", 0) + 1
            self.streak_msg = ("streak", {"days": self.save["streak"]})
        elif last_day is None:
            self.save["streak"] = 1
        else:
            gap = (today - last_day).days
            self.save["streak"] = 1
            if gap >= 3:
                self.streak_msg = ("streak_back", {})
        self.save["last_login"] = today.isoformat()

    def _daily_notes(self):
        """启动问候之后，依次播报连续天数、节日、纪念日倒数。"""
        queue = []
        if getattr(self, "streak_msg", None):
            queue.append(self.streak_msg)
        today = date.today()
        md = today.strftime("%m-%d")
        if self.save.get("birthday") == md:
            queue.append(("birthday", {}))
        elif md in FESTIVALS:
            queue.append(("festival", {"name": FESTIVALS[md]}))
        note = self._anniversary_note()
        if note:
            queue.append(note)
        for i, (key, fmt) in enumerate(queue):
            QTimer.singleShot(i * 5200,
                              lambda k=key, f=fmt: self.say(self.bank.pick(k, **f)))

    def _anniversary_note(self):
        """纪念日：当天报喜，7 天内报倒数。"""
        name = self.save.get("anniv_name")
        raw = self.save.get("anniv_date")
        if not name or not raw:
            return None
        try:
            target = date.fromisoformat(raw)
        except ValueError:
            return None
        days = (target - date.today()).days
        if days == 0:
            return ("anniversary_today", {"name": name})
        if 0 < days <= 7:
            return ("anniversary", {"name": name, "days": days})
        return None

    # ---------- 好感度 ----------
    AFFECTION_THRESHOLDS = (30, 80, 160)  # 每达到一档解锁 1 条隐藏台词

    def add_affection(self, n=1):
        self.save["affection"] = self.save.get("affection", 0) + n
        self.save["mood"] = min(100, self.save.get("mood", 60) + n * 2)
        self.mood_decay = 0
        unlocked = self.save.get("unlocked", 0)
        for i, t in enumerate(self.AFFECTION_THRESHOLDS):
            if self.save["affection"] >= t and unlocked <= i:
                self.save["unlocked"] = i + 1
                hid = self.bank.data.get("hidden") or ["……"]
                QTimer.singleShot(4500, lambda line=hid[min(i, len(hid) - 1)]:
                                  self.say("（悄悄话）" + line))
                break
        self._check_achievements()

    # ---------- 鼠标交互 ----------
    def mousePressEvent(self, e):
        if e.button() == Qt.MiddleButton and self.scare_cd <= 0:
            self._scare()
            e.accept()
            return
        self._wake()
        self._stop_wander()
        if e.button() == Qt.LeftButton:
            self.press_pos = e.globalPosition().toPoint()
            self.press_local = e.position().toPoint()
            self.drag_offset = self.press_pos - self.pos()
            if self.drop_anim:
                self.drop_anim.stop()
        e.accept()

    def mouseMoveEvent(self, e):
        if self.press_pos is None:
            return
        gp = e.globalPosition().toPoint()
        if not self.dragging and \
                (gp - self.press_pos).manhattanLength() > 6:
            self.dragging = True
            self.click_timer.stop()
            self.state = "panic"
            self.say(self.bank.pick("drag"))
        if self.dragging:
            self.move(gp - self.drag_offset)

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        if self.dragging:
            self.dragging = False
            self.state = "idle"
            if self.save.get("wander_on", True):
                self._settle_in_screen()  # 闲逛模式：放哪待哪
            else:
                self._snap_to_taskbar()
            self.say(self.bank.pick("drop"))
            self.add_affection(1)
        else:
            # 等待可能的第二次点击（双击）
            self.click_timer.start(QApplication.doubleClickInterval())
        self.press_pos = None

    def mouseDoubleClickEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        self.click_timer.stop()
        self._wake()
        self._set_temp_state("panic", 1.2)
        QTimer.singleShot(1200, lambda: self._set_temp_state("shy", 2.0))
        self.say(self.bank.pick("double_click"))
        self._spawn_hearts(4)
        self.add_affection(3)

    def _single_click(self):
        # 点头顶 = 摸头（开心 + 爱心），点身体 = 普通害羞
        local = getattr(self, "press_local", None)
        if local is not None and local.y() < self.height() * 0.34:
            self._set_temp_state("shy", 2.4)
            self._spawn_hearts(7)
            self.hop_ticks = 8
            self.say(self.bank.pick("head_pat"))
            self.add_affection(2)
            self._bump("pat")
            self._record_memory("pat_1", "memory_first_pat")
        else:
            self._set_temp_state("shy", 2.0)
            self.say(self.bank.pick("click_shy"))
            self.add_affection(1)
            self._bump("click")

    def contextMenuEvent(self, e):
        self._wake()
        self._show_menu(e.globalPos())

    # ---------- 右键菜单 ----------
    def _show_menu(self, gpos):
        m = QMenu(self)
        m.addAction("打招呼", self._greet)

        play = m.addMenu("陪我玩")
        play.addAction("投喂点心", self._feed)
        play.addAction("泡茶", self._brew_tea)
        play.addAction("掷骰子", self._roll_dice)
        play.addAction("抛硬币", self._flip_coin)
        play.addAction("跳舞", self._dance)
        play.addAction("放烟花", self._show_firework)
        rps = play.addMenu("猜拳")
        for i, name in enumerate(RPS):
            rps.addAction(name, lambda _=False, k=i: self._play_rps(k))

        beh = m.addMenu("行为")
        for key, label, slot in (
                ("wander_on", "自由闲逛", self._toggle_wander),
                ("follow_on", "跟随鼠标散步", self._toggle_follow),
                ("initiative_on", "偶尔主动搭话", self._toggle_initiative)):
            act = QAction(label, beh)
            act.setCheckable(True)
            act.setChecked(bool(self.save.get(key, key != "follow_on")))
            act.toggled.connect(slot)
            beh.addAction(act)
        act = QAction("白噪音（雨声）", beh)
        act.setCheckable(True)
        act.setChecked(bool(self.save.get("noise_on", False)))
        act.toggled.connect(self._toggle_noise)
        beh.addAction(act)
        act = QAction("全屏时自动安静", beh)
        act.setCheckable(True)
        act.setChecked(bool(self.save.get("dnd_on", True)))
        act.toggled.connect(lambda on: self.save.__setitem__("dnd_on", on))
        beh.addAction(act)

        tools = m.addMenu("小工具")
        if self.pomo_state:
            tools.addAction("停止番茄钟（%s）" % self._pomo_left(),
                            self._pomo_stop)
        else:
            tools.addAction("开始番茄钟（%d 分钟）"
                            % self.save.get("pomo_focus", 25), self._pomo_start)
        tools.addAction("记个提醒…", self._add_reminder)
        tools.addAction("查看待办（%d）" % len(self.reminders),
                        self._show_reminders)
        tools.addAction("看看电脑状态", self._pc_status)
        tools.addSeparator()
        tools.addAction("今日运势", self._fortune)
        tools.addAction("写时间胶囊…", self._add_capsule)
        tools.addAction("设置闹钟…", self._set_alarm)
        tools.addSeparator()
        tools.addAction("查看成就", self._view_achievements)
        tools.addAction("查看回忆碎片", self._view_memories)
        tools.addAction("查看互动统计", self._view_stats)

        rem = m.addMenu("提醒设置")
        for key, label in (("chime_on", "整点报时"),
                           ("sit_on", "久坐提醒 (1小时)"),
                           ("sleep_on", "23:30 睡觉提醒")):
            act = QAction(label, rem)
            act.setCheckable(True)
            act.setChecked(bool(self.save.get(key, True)))
            act.toggled.connect(
                lambda on, k=key: self.save.__setitem__(k, on))
            rem.addAction(act)

        pref = m.addMenu("个人设置")
        pref.addAction("设置我的生日…", self._set_birthday)
        pref.addAction("设置纪念日…", self._set_anniversary)
        pref.addAction("番茄钟时长…", self._set_pomodoro)
        th = pref.addMenu("主题换肤")
        for name, t in THEMES.items():
            act = QAction(t["desc"], th)
            act.setCheckable(True)
            act.setChecked(self.save.get("theme") == name)
            act.triggered.connect(lambda _, n=name: self._set_theme(n))
            th.addAction(act)

        sz = m.addMenu("缩放")
        for key in BASE_HEIGHTS:
            act = QAction(key, sz)
            act.setCheckable(True)
            act.setChecked(self.save.get("size_key") == key)
            act.triggered.connect(lambda _, k=key: self._apply_size(k))
            sz.addAction(act)

        m.addSeparator()
        for text in self._status_lines():
            info = QAction(text, m)
            info.setEnabled(False)
            m.addAction(info)
        m.addSeparator()
        m.addAction("关于艾拉…", self._about)
        m.addAction("隐藏到托盘", self.hide)
        m.addAction("退出", self._quit)
        m.exec(gpos)

    def _status_lines(self):
        aff = self.save.get("affection", 0)
        stars = min(5, self.save.get("unlocked", 0) + 1)
        mood = self.save.get("mood", 60)
        face = "◕‿◕" if mood >= 70 else ("・_・" if mood >= 30 else "╥﹏╥")
        return ["等级：%s（连续 %d 天）"
                % (self._level_name(), self.save.get("streak", 1)),
                "好感度：%d  %s" % (aff, "♥" * stars),
                "心情：%d  %s" % (mood, face),
                "共陪伴 %d 分钟" % (self._acc_seconds // 60)]

    def _about(self):
        InfoDialog(self, "关于艾拉", [
            "艾拉 · 桌面宠物  v%s" % APP_VERSION,
            "以《可塑性记忆》艾拉为灵感的原创近似形象。",
            "互动越多，她越喜欢待在你身边。",
            "存档位置：%s" % data_file(),
        ])

    def _toggle_initiative(self, on):
        self.save["initiative_on"] = on

    # ---------- 互动玩法 ----------
    def _brew_tea(self):
        self._set_temp_state("tea", 4.0)
        self.say(self.bank.pick("tea"))
        self.add_affection(2)
        self._bump("tea")
        self._record_memory("tea_1", "memory_first_tea")

    def _feed(self):
        self._set_temp_state("shy", 3.0)
        self.hop_ticks = 16          # 连蹦两下
        self._spawn_hearts(5)
        self.say(self.bank.pick("feed"))
        self.add_affection(3)
        self._bump("feed")
        self._record_memory("feed_1", "memory_first_feed")

    def _play_rps(self, mine):
        """0 石头 1 剪刀 2 布；她随机出拳，先慌张思考再公布结果。"""
        hers = random.randrange(3)
        if hers == mine:
            key = "rps_draw"
        elif (mine - hers) % 3 == 1:   # 玩家赢（石头>剪刀>布>石头）
            key = "rps_lose"           # 她输
        else:
            key = "rps_win"            # 她赢
        self._set_temp_state("panic", 1.0)
        self.say("我出……%s！" % RPS[hers])
        QTimer.singleShot(1400, lambda: self._rps_result(key))
        self.add_affection(1)

    def _rps_result(self, key):
        if key == "rps_win":
            self._set_temp_state("shy", 2.2)
            self.hop_ticks = 8
            self._spawn_hearts(4)
        else:
            self._set_temp_state("shy", 2.2)
        self.say(self.bank.pick(key))
        self._bump(key)
        if key == "rps_win":
            self._record_memory("rps_win_1", "memory_first_rps_win")

    # ---------- 新玩法：骰子 / 硬币 / 跳舞 / 惊吓 ----------
    def _roll_dice(self):
        """掷一个六面骰，点数决定她的反应。"""
        n = random.randint(1, 6)
        self._bump("dice")
        self._set_temp_state("panic", 0.9)
        if n >= 5:
            self.hop_ticks = 8
            self._spawn_hearts(3)
            key = "dice_high"
        elif n <= 2:
            key = "dice_low"
        else:
            key = "dice_mid"
        self.say(self.bank.pick(key, num=n))
        QTimer.singleShot(1300, lambda: self._set_temp_state("idle", 0.4))

    def _flip_coin(self):
        """抛硬币：正面 / 反面。"""
        head = random.random() < 0.5
        self._bump("coin")
        self._set_temp_state("panic", 1.0)
        self.say("抛……！")
        QTimer.singleShot(1200, lambda: self._coin_result(head))

    def _coin_result(self, head):
        self._set_temp_state("shy", 1.8)
        side = "正" if head else "反"
        key = "coin_head" if head else "coin_tail"
        self.say(self.bank.pick(key, side=side))

    def _dance(self):
        """跳舞：随机姿势序列 4 秒 + 星星音符粒子。"""
        self._bump("dance")
        self._record_memory("dance_1", "memory_first_dance")
        self.dance_seq = random.sample(
            ["tea", "shy", "panic", "blink", "idle"], k=4)
        self.say(self.bank.pick("dance"))
        self._dance_step()
        self._spawn_particles(8, "star", vy=(-1.4, -0.5), life=(12, 20))
        self.dance_timer.start(500)

    def _dance_step(self):
        if self.dance_seq:
            self.state = self.dance_seq.pop(0)
            self.update()
            self.dance_timer.start(500)

    def _scare(self):
        """中键单击：吓她一跳（彩蛋）。"""
        self._bump("scare")
        self._set_temp_state("panic", 1.6)
        self.hop_ticks = 10
        self.say(self.bank.pick("scare"))
        self.scare_cd = SCARE_CD_TICKS

    def wheelEvent(self, e):
        """滚轮：临时三档缩放预览（上放大 / 下缩小，带冷却）。"""
        if self.zoom_cd > 0:
            e.ignore()
            return
        self.zoom_cd = ZOOM_CD_TICKS
        sizes = list(BASE_HEIGHTS)
        cur_key = self.save.get("size_key", DEFAULT_SIZE)
        cur = sizes.index(cur_key) if cur_key in sizes \
            else sizes.index(DEFAULT_SIZE)
        if e.angleDelta().y() > 0:
            nxt = min(len(sizes) - 1, cur + 1)
            self.say(self.bank.pick("zoom_up"))
        else:
            nxt = max(0, cur - 1)
            self.say(self.bank.pick("zoom_down"))
        self._apply_size(sizes[nxt])
        e.accept()

    # ---------- 互动统计 / 记忆碎片 ----------
    def _bump(self, key):
        """互动计数 +1，随后顺带检查成就。"""
        st = self.save.setdefault("stats", {})
        st[key] = st.get(key, 0) + 1
        self._check_achievements()

    def _record_memory(self, key, line_key=None):
        """记忆碎片：每个里程碑只记一次，首次触发时播报。"""
        mem = self.save.setdefault("memories", {})
        if key in mem:
            return
        mem[key] = date.today().isoformat()
        if line_key:
            QTimer.singleShot(4600,
                              lambda: self.say(self.bank.pick(line_key)))
        self.save_data()

    # ---------- 成就系统 ----------
    def _check_achievements(self, silent=False):
        """遍历成就表，把已满足的成就写入存档；silent 时不播报。"""
        got = set(self.save.get("achievements") or [])
        st = self.save.get("stats") or {}
        for aid, name, _desc, cond in _def_achievements():
            if aid in got:
                continue
            try:
                ok = cond(self.save, st)
            except Exception:
                ok = False
            if ok:
                got.add(aid)
                if not silent:
                    QTimer.singleShot(3600, lambda n=name: self.say(
                        self.bank.pick("achievement", name=n)))
        self.save["achievements"] = sorted(got)

    def _view_achievements(self):
        got = set(self.save.get("achievements") or [])
        total = len(_def_achievements())
        lines = ["%s %s" % ("◆" if aid in got else "◇", name)
                 for aid, name, _d, _c in _def_achievements()]
        InfoDialog(self, "成就 %d / %d" % (len(got), total), lines)

    def _view_memories(self):
        mem = self.save.get("memories") or {}
        if not mem:
            self.say(self.bank.pick("memory_none"))
            return
        names = dict((aid, name) for aid, name, _d, _c in _def_achievements())
        lines = ["%s · %s" % (day, names.get(key, key))
                 for key, day in sorted(mem.items())]
        InfoDialog(self, "回忆碎片 %d 枚" % len(mem), lines)

    def _view_stats(self):
        st = self.save.get("stats") or {}
        total = sum(st.values())
        lines = ["%s × %d" % (label, st[key])
                 for key, label in (("pat", "摸头"), ("feed", "投喂"),
                                    ("tea", "泡茶"), ("dice", "骰子"),
                                    ("coin", "硬币"), ("dance", "跳舞"),
                                    ("fortune", "抽签"), ("scare", "惊吓"),
                                    ("rps_win", "猜拳赢"),
                                    ("rps_lose", "猜拳输"),
                                    ("rps_draw", "猜拳平"))
                 if st.get(key)]
        lines.append("共陪伴 %d 分钟" % (self._acc_seconds // 60))
        InfoDialog(self, "互动总计 %d 次" % total, lines)

    def _level_name(self):
        """按连续陪伴天数查等级称号。"""
        streak = self.save.get("streak", 0)
        name = "初识"
        for days, title in LEVELS:
            if streak >= days:
                name = title
        return name

    # ---------- 时间胶囊（写给未来） ----------
    def _add_capsule(self):
        text, ok = QInputDialog.getText(
            None, "时间胶囊", "写给未来的话（到日子她会念给你听）：")
        if not ok or not text.strip():
            return
        raw, ok = QInputDialog.getText(
            None, "时间胶囊", "什么时候开启？（格式 YYYY-MM-DD，今天即可）：",
            text=date.today().isoformat())
        if not ok:
            return
        try:
            target = date.fromisoformat(raw.strip())
        except ValueError:
            self.say(self.bank.pick("capsule_bad_date"))
            return
        if target < date.today():
            self.say(self.bank.pick("capsule_past"))
            return
        self.save.setdefault("capsules", []).append(
            [target.isoformat(), text.strip()])
        self._bump("capsule")
        self._record_memory("capsule_1", "memory_first_capsule")
        self.say(self.bank.pick("capsule_set",
                                date=target.strftime("%m月%d日")))
        self.save_data()

    def _capsule_check(self):
        caps = self.save.get("capsules") or []
        if not caps:
            return
        today = date.today().isoformat()
        due = [c for c in caps if c[0] <= today]
        if not due:
            return
        self.save["capsules"] = [c for c in caps if c[0] > today]
        for i, (_d, txt) in enumerate(due):
            QTimer.singleShot(i * 6000,
                              lambda s=txt: self.say(
                                  self.bank.pick("capsule_fire", text=s)))
        self._notify("时间胶囊", "过去的你寄来的信，到了。")
        self._spawn_hearts(6)
        self.save_data()

    # ---------- 每日运势 ----------
    FORTUNES = (("大吉", "fortune_big"), ("中吉", "fortune_mid"),
                ("小吉", "fortune_small"), ("末吉", "fortune_mid"),
                ("凶", "fortune_bad"), ("大吉", "fortune_big"))

    def _fortune(self):
        today = date.today().isoformat()
        cur = self.save.get("fortune")
        if cur and cur[0] == today:
            rank, key = cur[1], cur[2]
        else:
            rank, key = random.choice(self.FORTUNES)
            self.save["fortune"] = [today, rank, key]
        self._bump("fortune")
        self._record_memory("fortune_1", "memory_first_fortune")
        self.say(self.bank.pick(key, rank=rank))
        self.save_data()

    # ---------- 闹钟 ----------
    def _set_alarm(self):
        text, ok = QInputDialog.getText(
            None, "闹钟", "几点叫醒你？（格式 HH:MM，24 小时制）：",
            text=datetime.now().strftime("%H:%M"))
        if not ok:
            return
        text = text.strip()
        try:
            datetime.strptime(text, "%H:%M")
        except ValueError:
            self.say(self.bank.pick("alarm_bad_time"))
            return
        if text not in (self.save.get("alarms") or []):
            self.save.setdefault("alarms", []).append(text)
        self._bump("alarm")
        self.say(self.bank.pick("alarm_set", time=text))
        self.save_data()

    def _alarm_check(self):
        alarms = self.save.get("alarms") or []
        if not alarms:
            return
        hm = datetime.now().strftime("%H:%M")
        if hm not in alarms:
            return
        self.save["alarms"] = [a for a in alarms if a != hm]
        self._set_temp_state("panic", 1.8)
        self.hop_ticks = 12
        self._spawn_hearts(5)
        self.say(self.bank.pick("alarm_fire", time=hm))
        self._notify("闹钟", "到点了，起来活动一下吧！")
        self.save_data()

    # ---------- 主题换肤 ----------
    def _set_theme(self, name):
        self.save["theme"] = name
        self.say(self.bank.pick("theme_change", name=name))
        self.bubble.update()                       # 正在显示的气泡立即换色
        self._spawn_particles(8, "star", vy=(-1.3, -0.5),
                              life=(14, 26))       # 撒一撮新主题色星星，立即可见
        self.hop_ticks = 8
        self.save_data()
        self.update()

    # ---------- 白噪音（雨声，自动生成 wav） ----------
    def _noise_path(self):
        d = os.path.join(os.environ.get("TEMP", "."), "isla_pet_sound")
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, "rain.wav")

    def _generate_rain_wav(self, path, seconds=12):
        """用标准库生成一段粉噪声雨声 wav（失败时返回 False）。"""
        rate = 22050
        frames = int(rate * seconds)
        buf = array("h")
        last = 0.0
        for i in range(frames):
            white = random.uniform(-1.0, 1.0)
            last = last * 0.94 + white * 0.06      # 一阶低通 -> 粉噪
            amp = 4200 + 2600 * math.sin(2 * math.pi * i / rate * 0.9)
            v = int(max(-32767, min(32767, last * amp)))
            buf.append(v)
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(rate)
            wf.writeframes(buf.tobytes())
        return True

    def _load_noise(self):
        """wav 不存在时丢给后台线程生成，避免启动主线程卡顿。"""
        if not _HAS_SOUND:
            return
        path = self._noise_path()
        if os.path.exists(path):
            self._setup_noise(path)
            return
        threading.Thread(target=self._gen_noise_bg, args=(path,),
                         daemon=True).start()

    def _gen_noise_bg(self, path):
        try:
            self._generate_rain_wav(path)
        except Exception:
            return
        self._noise_ready = True

    def _setup_noise(self, path):
        try:
            self.noise = QSoundEffect()
            self.noise.setSource(QUrl.fromLocalFile(path))
            self.noise.setLoopCount(QSoundEffect.Infinite)
            self.noise.setVolume(0.35)
        except Exception:
            self.noise = None

    def _toggle_noise(self, on):
        self.save["noise_on"] = bool(on)
        if not self.noise and self._noise_ready:   # 文件刚好生成完，补一次加载
            self._setup_noise(self._noise_path())
        if not self.noise:
            self.say("唔……现在放不了声音。")
            self.save["noise_on"] = False
            return
        if on:
            self.noise.play()
            self.say(self.bank.pick("noise_on"))
        else:
            self.noise.stop()
            self.say(self.bank.pick("noise_off"))
        self.save_data()

    def _restore_noise(self):
        """启动时恢复上次开启的白噪音（wav 可能还在后台线程生成）。"""
        if not self.save.get("noise_on"):
            return
        if not self.noise and self._noise_ready:
            self._setup_noise(self._noise_path())
        if self.noise:
            self.noise.play()
            return
        self._noise_retry = getattr(self, "_noise_retry", 0) + 1
        if self._noise_retry <= 5:               # 最多再等 15 秒
            QTimer.singleShot(3000, self._restore_noise)
        else:
            self.save["noise_on"] = False        # 始终不可用则复位开关，避免菜单勾选误导

    # ---------- 全屏烟花 ----------
    def _show_firework(self):
        self._bump("firework")
        self._record_memory("firework_1", "memory_first_firework")
        if self.firework is None:
            self.firework = FireworkOverlay(self)
        # 烟花打在宠物所在的屏幕（多显示器支持）
        screen = QGuiApplication.screenAt(self.geometry().center()) \
            or QGuiApplication.primaryScreen()
        self.firework.launch(geo=screen.geometry())
        self.say(self.bank.pick("firework"))

    # ---------- 托盘通知 ----------
    def _notify(self, title, body):
        """系统托盘气泡通知（托盘未就绪时静默）。"""
        if self.tray is not None:
            try:
                self.tray.showMessage(title, body,
                                      QSystemTrayIcon.Information, 5000)
            except Exception:
                pass

    # ---------- 小工具 ----------
    def _pomo_left(self):
        if not self.pomo_end:
            return "--:--"
        left = max(0, int((self.pomo_end - datetime.now()).total_seconds()))
        return "%02d:%02d" % (left // 60, left % 60)

    def _pomo_start(self, phase="focus"):
        mins = self.save.get("pomo_focus", 25) if phase == "focus" \
            else self.save.get("pomo_break", 5)
        self.pomo_state = phase
        self.pomo_end = datetime.now() + timedelta(minutes=mins)
        if phase == "focus":
            self.say(self.bank.pick("pomodoro_start", minutes=mins))
            self._set_temp_state("tea", 2.5)
        self.add_affection(1)

    def _pomo_stop(self):
        self.pomo_state = None
        self.pomo_end = None
        self.say(self.bank.pick("pomodoro_stop"))

    def _pomo_check(self):
        if not self.pomo_state or datetime.now() < self.pomo_end:
            return
        if self.pomo_state == "focus":
            brk = self.save.get("pomo_break", 5)
            self.say(self.bank.pick("pomodoro_focus_end", minutes=brk))
            self._notify("番茄钟", "专注时间到，休息一下吧")
            self._spawn_hearts(5)
            self.hop_ticks = 8
            self._pomo_start("break")
        else:
            self.pomo_state = None
            self.pomo_end = None
            self.say(self.bank.pick("pomodoro_break_end"))
            self._notify("番茄钟", "休息结束，继续加油")

    def _add_reminder(self):
        text, ok = QInputDialog.getText(None, "记个提醒", "要提醒你什么？")
        if not ok or not text.strip():
            return
        mins, ok = QInputDialog.getInt(None, "记个提醒",
                                       "多少分钟后提醒？", 30, 1, 1440)
        if not ok:
            return
        self.reminders.append(
            (datetime.now() + timedelta(minutes=mins), text.strip()))
        self.say(self.bank.pick("reminder_set", minutes=mins))
        self.add_affection(1)

    def _show_reminders(self):
        if not self.reminders:
            self.say(self.bank.pick("reminder_none"))
            return
        items = ["%s · %s" % (t.strftime("%H:%M"), txt)
                 for t, txt in sorted(self.reminders)]
        self.say("待办：\n" + "\n".join(items[:4]))

    def _reminder_check(self):
        now = datetime.now()
        due = [r for r in self.reminders if r[0] <= now]
        if not due:
            return
        self.reminders = [r for r in self.reminders if r[0] > now]
        for i, (_t, txt) in enumerate(due):
            QTimer.singleShot(i * 5000, lambda s=txt: self.say(
                self.bank.pick("reminder_fire", text=s)))
            if i == 0:
                self._notify("提醒", txt)

    def _pc_status(self):
        pct = self._memory_percent()
        key = "pc_status_busy" if pct >= 75 else "pc_status_ok"
        self.say(self.bank.pick(key, mem=pct))

    @staticmethod
    def _memory_percent():
        """用 Win32 GlobalMemoryStatusEx 读内存占用率，避免引入 psutil。"""
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong),
                        ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        try:
            st = MEMORYSTATUSEX()
            st.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
            return int(st.dwMemoryLoad)
        except Exception:
            return 0

    # ---------- 个人设置 ----------
    def _set_birthday(self):
        cur = self.save.get("birthday") or ""
        text, ok = QInputDialog.getText(None, "设置生日", "生日（格式 MM-DD，如 07-31）：", text=cur)
        if not ok:
            return
        text = text.strip()
        if not text:
            self.save["birthday"] = None
            self.say("生日……我先忘掉了。")
            return
        try:
            datetime.strptime(text, "%m-%d")
        except ValueError:
            self.say("唔……格式好像不对。请写成 MM-DD……")
            return
        self.save["birthday"] = text
        self.say("记住了……%s 是你的生日。我不会忘的。" % text)

    def _set_anniversary(self):
        name, ok = QInputDialog.getText(None, "设置纪念日", "纪念日的名字：",
            text=self.save.get("anniv_name") or "")
        if not ok:
            return
        name = name.strip()
        if not name:
            self.save["anniv_name"] = None
            self.save["anniv_date"] = None
            self.say("纪念日……清空了。")
            return
        raw, ok = QInputDialog.getText(None, "设置纪念日", "日期（格式 YYYY-MM-DD）：",
            text=self.save.get("anniv_date") or date.today().isoformat())
        if not ok:
            return
        try:
            date.fromisoformat(raw.strip())
        except ValueError:
            self.say("唔……日期格式不对。请写成 YYYY-MM-DD……")
            return
        self.save["anniv_name"] = name
        self.save["anniv_date"] = raw.strip()
        note = self._anniversary_note()
        if note:
            self.say(self.bank.pick(note[0], **note[1]))
        else:
            days = (date.fromisoformat(raw.strip()) - date.today()).days
            self.say("记下了……距离%s还有 %d 天。" % (name, days))

    def _set_pomodoro(self):
        focus, ok = QInputDialog.getInt(None, "番茄钟", "专注时长（分钟）：",
                                       self.save.get("pomo_focus", 25), 1, 180)
        if not ok:
            return
        brk, ok = QInputDialog.getInt(None, "番茄钟", "休息时长（分钟）：",
                                      self.save.get("pomo_break", 5), 1, 60)
        if not ok:
            return
        self.save["pomo_focus"] = focus
        self.save["pomo_break"] = brk
        self.say("好的……专注 %d 分钟，休息 %d 分钟。" % (focus, brk))

    def _quit(self):
        self.say(self.bank.pick("farewell"))
        self.save_data()
        QTimer.singleShot(900, QApplication.quit)

    # ---------- 定时检查 ----------
    def _second_check(self):
        now = time.monotonic()
        # 按真实经过时间累计；休眠/卡顿恢复后只算一档，防止虚增
        self._acc_seconds += int(min(now - self._last_second, 5.0))
        self._last_second = now
        self.save["total_seconds"] = self._acc_seconds
        self._pomo_check()
        self._reminder_check()
        self._capsule_check()
        self._alarm_check()
        self._update_dnd()
        if not self.noise and self._noise_ready:   # 白噪音文件后台生成完毕
            self._setup_noise(self._noise_path())

    def _minute_check(self):
        now = datetime.now()
        # 番茄钟专注期间不打扰
        quiet = self.pomo_state == "focus"
        # 整点报时
        if self.save.get("chime_on", True) and now.minute == 0 \
                and now.hour != self.last_chimed_hour:
            self.last_chimed_hour = now.hour
            if not quiet:
                self.say(self.bank.pick("hourly_chime", hour=now.hour))
        # 久坐提醒：程序运行满 1 小时提醒一次并重新计时
        if self.save.get("sit_on", True) and \
                (now - self.sit_start).total_seconds() >= 3600:
            self.sit_start = now
            if not quiet:
                self.say(self.bank.pick("sit_reminder"))
        # 每天 23:30 睡觉提醒
        if self.save.get("sleep_on", True) and now.hour == 23 \
                and now.minute >= 30 and self.sleep_reminded_day != date.today():
            self.sleep_reminded_day = date.today()
            self.say(self.bank.pick("sleep_reminder"))


def main():
    _init_logging()
    _install_excepthook()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName(APP_NAME)

    # 单实例：重复启动时提示后退出，防止两个实例互相覆盖存档
    lock = QLockFile(os.path.join(tempfile.gettempdir(), APP_NAME + ".lock"))
    if not lock.tryLock(100):
        QMessageBox.information(None, "艾拉",
                                "艾拉已经在运行啦……不用再叫一次。")
        return

    pet = IslaPet()

    # ---- 系统托盘 ----
    tray = QSystemTrayIcon(QIcon(res_path(os.path.join("assets", "icon.ico"))))
    tray.setToolTip("艾拉 · 桌面宠物")
    pet.tray = tray                 # 供闹钟/提醒/番茄钟等弹托盘通知
    tm = QMenu()
    tm.addAction("显示 / 隐藏",
                 lambda: pet.setVisible(not pet.isVisible()))
    tm.addAction("打招呼", lambda: (pet.show(), pet._greet()))
    tm.addAction("投喂点心", lambda: (pet.show(), pet._feed()))
    tm.addAction("开始 / 停止番茄钟",
                 lambda: (pet.show(),
                          pet._pomo_stop() if pet.pomo_state
                          else pet._pomo_start()))
    tm.addAction("记个提醒…", lambda: (pet.show(), pet._add_reminder()))
    tm.addAction("看看电脑状态", lambda: (pet.show(), pet._pc_status()))
    tm.addSeparator()
    tm.addAction("今日运势", lambda: (pet.show(), pet._fortune()))
    tm.addAction("写时间胶囊…", lambda: (pet.show(), pet._add_capsule()))
    tm.addAction("放烟花", lambda: (pet.show(), pet._show_firework()))
    tm.addSeparator()
    tm.addAction("退出", pet._quit)
    tray.setContextMenu(tm)
    tray.activated.connect(
        lambda r: pet.setVisible(not pet.isVisible())
        if r == QSystemTrayIcon.Trigger else None)
    tray.show()

    app.aboutToQuit.connect(pet.save_data)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
