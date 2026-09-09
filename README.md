# IslaPet · 艾拉桌面宠物

以《可塑性记忆》艾拉（Isla）为灵感的 **原创近似形象** Windows 桌面宠物。
立绘为 AI 生成的原创同风格角色，未使用任何原作版权素材。

![idle](assets/idle.png)

---

## 一、功能一览

| 分类 | 功能 |
| --- | --- |
| 视觉 | 无边框、背景透明、始终置顶、不抢焦点，默认停靠屏幕右下角（任务栏上沿）；**台词气泡排队播放**，多条事件不再互相打断 |
| 动画（6 种状态） | 待机呼吸浮动、随机眨眼、拖拽慌张、点击害羞、闲置 3 分钟回任务栏坐下打瞌睡、泡茶 |
| 自由闲逛 | 没事的时候每隔 8~30 秒在整个屏幕范围慢悠悠游走（约 90px/s），朝移动方向自动镜像，到达后有概率自言自语；可在右键菜单关闭 |
| 互动 | 单击（摸头=头顶、害羞=身体）、双击（慌张→害羞）、拖拽、投喂点心、泡茶、猜拳、**掷骰子、抛硬币、跳舞、中键惊吓彩蛋**、**滚轮快速缩放** |
| 烟花 | **全屏烟花特效**（透明置顶点击穿透窗口，3 波连发约 5 秒），生日/开心时也可触发 |
| 好感度 | 互动累积好感度（单击 +1、拖拽 +1、泡茶 +2、双击 +3、摸头 +2、投喂 +3），达到 30 / 80 / 160 分别解锁 3 条隐藏台词 |
| 心情系统 | 心情 0~100，互动提升、每 5 分钟无互动衰减 1；**心情低落时立绘变冷色调**，高值时随机说开心话 |
| 等级称号 | 按连续陪伴天数自动升级：初识 → 熟络 → 好友 → 挚友 → 家人 → 重要的人 → 相伴一生 |
| **成就系统** | **18 枚成就**（摸头十连、泡茶苦手、猜拳大师、七日之约、满月相伴、烟火人间……），解锁时气泡播报，可查看 |
| **记忆碎片** | 里程碑自动记录（第一次摸头/泡茶/投喂/猜拳赢/跳舞/抽签/放烟花……），「回忆」菜单回看 |
| **时间胶囊** | 写给未来的自己一封信，设定日期，到日子她会在气泡里念给你听 |
| **每日运势** | 大吉 / 中吉 / 小吉 / 末吉 / 凶，按天缓存不重复刷 |
| **闹钟** | 自定义 HH:MM 叫醒，到点慌张跳起 + 播报 |
| **白噪音** | 内置"雨声"白噪音（首次自动生成 wav），右键菜单一键播放/停止，适合专注工作 |
| **主题换肤** | 樱花粉 / 薄荷蓝 / 丁香紫 / 柠檬黄，气泡、爱心、烟花全部跟随换色 |
| 定时提醒 | 整点报时（可关）、久坐 1 小时提醒休息（可关）、每天 23:30 睡觉提醒（可关） |
| 番茄钟 | 专注 25 分钟 → 休息 5 分钟循环（时长可设），专注期间她保持安静 |
| 自定义提醒 | 记 N 分钟后的提醒，到点气泡播报；可查看待办列表 |
| 陪伴统计 | 累计陪伴分钟数、各类互动次数统计，右键菜单随时查看 |
| 登录统计 | 连续登录天数（streak），回归欢迎 + 断签欢迎回来 |
| 节日/纪念日 | 公历节日祝福、生日祝福、纪念日倒数（7 天内每日播报） |
| 电脑状态 | 查看当前内存占用率（ctypes 直调 Win32 API，零额外依赖） |
| 信息面板 | 成就 / 回忆 / 统计改为完整列表面板（点击任意处关闭），不再受气泡 8 行截断 |
| 全屏自动安静 | 检测到前台窗口全屏（游戏/视频/投屏）时自动闭嘴：台词改走托盘通知、停止闲逛与搭话，退出全屏才恢复 |
| 状态持久化 | 自定义提醒、番茄钟进度、白噪音开关、闹钟全部存盘，重启后原样恢复 |
| 稳定性 | **单实例保护**（重复启动只提示不重复开）、存档自动备份损坏原件 + 原子写入防损坏、陪伴时长按真实时间累计（休眠不虚增）、未捕获异常写入日志（崩溃有迹可循） |
| 托盘 | 系统托盘图标：单击显示/隐藏、菜单快速使用（打招呼/投喂/番茄钟/提醒/运势/胶囊/烟花）、退出 |
| 存档 | 退出时自动保存好感度、心情、等级、成就、记忆、胶囊、闹钟、统计、位置、缩放、开关等全部状态 |
| 性能 | 实测空闲内存 ~110MB（<150MB）、空闲 CPU ~1%（<2%） |

## 二、目录结构

```
IslaPet/
├─ isla_pet.py          # 主程序源码（单文件）
├─ dialogues.json       # 台词库（78 类 224 条，可自行增改）
├─ assets/              # 素材文件夹
│  ├─ raw/sprite_sheet.png   # 原始精灵图（3列x2行）
│  ├─ idle.png / blink.png / shy.png / panic.png / sleep.png / tea.png
│  ├─ icon.png / icon.ico    # 托盘图标
├─ tools/
│  └─ process_assets.py # 素材处理脚本：切图+品红去底+统一画布+生成图标
├─ selftest.py          # 无人值守自测（63 项，全部通过）
└─ dist/
   ├─ IslaPet.exe       # 打包好的单文件 exe，双击即可运行
   └─ dialogues.json    # 外置台词库（优先于内置版本被加载）
```

## 三、直接运行

- **免环境**：双击 `dist\IslaPet.exe` 即可，无需安装 Python。
- **源码运行**（需 Python 3.10+）：

```powershell
pip install pyside6-addons pillow
python isla_pet.py
```

> **依赖注意**：白噪音使用 QtMultimedia（位于 `pyside6-addons`，会自动带上 essentials）；
> 若只装 `pyside6-essentials`，白噪音会静默降级为不可用。
> 烟花等其余新功能同样为可降级设计，缺少 QtMultimedia 或 PIL 时自动禁用对应视觉/音效，不影响主程序。

## 四、打包命令

在项目根目录执行（需 pip install pyinstaller）：

```powershell
python -m PyInstaller --noconfirm --onefile --windowed --name IslaPet `
  --icon assets\icon.ico `
  --add-data "assets\idle.png;assets" `
  --add-data "assets\blink.png;assets" `
  --add-data "assets\shy.png;assets" `
  --add-data "assets\panic.png;assets" `
  --add-data "assets\sleep.png;assets" `
  --add-data "assets\tea.png;assets" `
  --add-data "assets\icon.ico;assets" `
  --add-data "dialogues.json;." `
  isla_pet.py
```

生成结果在 `dist\IslaPet.exe`。重新打包前建议先 `python selftest.py` 跑一遍回归。

## 五、如何替换台词库

台词都在独立的 `dialogues.json` 里，**UTF-8 编码**，随意增删条目即可（每类是一个字符串数组，程序随机抽取）。

- **exe 用户**：把改好的 `dialogues.json` 放在 `IslaPet.exe` 同目录即可，外置文件优先于打包内置的版本，**无需重新打包**。
- 分类键名及用途（v2.1 共 78 类 224 条）：

| 键 | 用途 |
| --- | --- |
| `greeting_morning / afternoon / evening / late_night` | 早 / 午 / 晚 / 深夜问候 |
| `click_shy` / `head_pat` | 单击害羞 / 摸头 |
| `idle_murmur` | 闲置自言自语 |
| `tea` / `feed` | 泡茶 / 投喂点心 |
| `dice_high / mid / low` | 掷骰子大 / 中 / 小，支持 `{num}` |
| `coin_head / coin_tail` | 抛硬币正 / 反，支持 `{side}` |
| `dance` | 跳舞 |
| `scare` | 中键惊吓彩蛋 |
| `zoom_up / zoom_down` | 滚轮放大 / 缩小 |
| `double_click` | 双击专属台词 |
| `drag` / `drop` | 拖起 / 落地 |
| `rps_win / lose / draw` | 猜拳赢 / 输 / 平 |
| `follow_on / off` | 跟随鼠标开 / 关 |
| `hourly_chime` | 整点报时，支持 `{hour}` 占位符 |
| `sit_reminder` / `sleep_reminder` | 久坐 / 睡觉提醒 |
| `hidden` | 好感度解锁的 3 条隐藏台词 |
| `wake_up` / `farewell` | 睡醒 / 退出告别 |
| `bond` | 告别与羁绊主题（致敬原作） |
| `initiative` / `mood_high` / `mood_low` | 主动搭话 / 心情好 / 心情差 |
| `pomodoro_start / focus_end / break_end / stop` | 番茄钟四阶段 |
| `reminder_set / fire / none` | 自定义提醒三态 |
| `pc_status_ok / busy` | 电脑内存状态，支持 `{mem}` |
| `festival` / `birthday` | 节日 / 生日祝福 |
| `anniversary` / `anniversary_today` | 纪念日倒数 / 当天，支持 `{name}` `{days}` |
| `streak` / `streak_back` | 连续登录 / 回归欢迎，支持 `{days}` |
| `achievement` | 成就解锁，支持 `{name}` |
| `memory_none` / `memory_first_*` | 记忆碎片：暂无 / 各类首次里程碑 |
| `capsule_set / fire / bad_date / past` | 时间胶囊四态，支持 `{date}` `{text}` |
| `fortune_big / mid / small / bad` | 每日运势四档，支持 `{rank}` |
| `alarm_set / fire / bad_time` | 闹钟三态，支持 `{time}` |
| `theme_change` | 主题换肤，支持 `{name}` |
| `noise_on / off` | 白噪音开关 |
| `dnd_off` | 退出全屏免打扰时的招呼 |
| `firework` | 放烟花 |

## 六、如何替换立绘

**方式 A（推荐，整套替换）：**
1. 准备一张 **3 列 × 2 行** 精灵图，背景为纯品红 `#FF00FF`，姿势顺序（行优先）为：
   `待机(睁眼) / 眨眼 / 害羞 / 慌张 / 打瞌睡 / 泡茶`
2. 覆盖 `assets/raw/sprite_sheet.png`，然后运行：
   ```powershell
   python tools\process_assets.py
   ```
   自动完成切图、品红去底、统一画布（底部居中对齐）并重新生成托盘图标。
3. 重新打包（见第四节）。

**方式 B（单张替换）：** 直接用同名透明背景 PNG 覆盖 `assets/` 下的
`idle / blink / shy / panic / sleep / tea.png`（建议各帧画布尺寸一致、角色底部对齐），再重新打包。

## 七、存档说明

`isla_save.json` 生成于 exe 同目录（无写权限时自动改存 `%APPDATA%\IslaPet\`）：

```json
{
  "affection": 25,
  "unlocked": 0,
  "pos": [1315, 83],
  "size_key": "中 (260px)",
  "chime_on": true, "sit_on": true, "sleep_on": true,
  "wander_on": true, "follow_on": false, "initiative_on": true,
  "mood": 85, "streak": 1, "last_login": "2026-07-31",
  "birthday": "07-31",
  "anniv_name": "约定的日子", "anniv_date": "2026-07-31",
  "pomo_focus": 25, "pomo_break": 5,
  "theme": "樱花粉",
  "total_seconds": 0,
  "stats": { "pat": 3, "tea": 1 },
  "memories": { "pat_1": "2026-07-31" },
  "achievements": ["first_touch"],
  "capsules": [],
  "alarms": [],
  "noise_on": false,
  "fortune": null,
  "reminders": []
}
```

删除该文件即可重置全部状态。

## 八、版权说明

角色立绘为 AI 生成的"以艾拉为灵感的原创近似形象"，配色与气质致敬原作但并非原作素材；台词为原创撰写。仅供个人学习与使用。
