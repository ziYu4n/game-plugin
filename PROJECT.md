# game-plugin 项目文档（方案优化用）

> 用途：给其他 AI / 工程师做方案评审与优化。  
> 仓库：`/Users/ziyuan/code/game-plugin`（远程 `git@github.com:ziYu4n/game-plugin.git`，`main` 可能尚无提交）  
> 环境：macOS Darwin 27（Tahoe），官方 **iPhone 镜像**（`/System/Applications/iPhone Mirroring.app`）  
> 文档日期：2026-09-17

---

## 1. 产品目标

在 Mac 上自动化操作 **iPhone 镜像** 窗口，完成手游脚本（当前主打《燕云十六声》）：

1. 打开 / 保活 iPhone 镜像  
2. OCR 判断锁屏 → 从钥匙串取密码自动解锁（不移动用户鼠标）  
3. 回主屏幕 → Spotlight 搜索 → 打开游戏  
4. **第一次进游戏必须横屏**（同一轮镜像里再开一次会变竖屏）  
5. 识别并点击公告页 **返回图标** → 点「继续游戏」  
6. OCR 识别账号并在 UI 左下角展示  
7. 队列执行、日志可复制、错误暂存可手动清空  

桌面应用名：**脚本合集**。

### 明确不做 / 暂缓

- 星穹铁道：分组已有，脚本未实现  
- 切号 / 多账号切换：配置字段有预留，未做完  
- 不依赖 HID 抢焦点乱点（除 Spotlight 短暂前置）  
- 不写密码进 Git；密码只进本机钥匙串  

---

## 2. 技术栈

| 层 | 技术 | 说明 |
|----|------|------|
| 编排 / 业务 | Python 3.9（CLT 自带） | `mirror_keeper.py` + `gui.py`，无第三方业务依赖（OCR 匹配用到系统自带 **Pillow**） |
| GUI | 本地 HTTP + WKWebView | 不用 Tk（本机 Tk Label/Listbox/Text 空白）；`ui/index.html` + `scripts/appwin` |
| 桌面壳 | Swift + Cocoa | `launcher.swift` → `脚本合集.app`；只负责拉起 `start.command` / `gui.py` |
| 窗口检测 | Swift CoreGraphics | `wininfo.swift` → `CGWindowListCopyWindowInfo` |
| 截图 | `screencapture -l <windowId>` | 对镜像窗口截图；`-R` 区域截图在本机常失败 |
| OCR | Swift Vision | `ocr.swift`，`--boxes` / `--accurate`，中英识别 |
| 点击 / 键鼠 | Swift CoreGraphics | `click.swift`，**`postToPid`** 注入到镜像进程（不抢系统光标） |
| 图标匹配 | Python + Pillow NCC | `scripts/match.py`，模板 `icons/back.png` |
| 校准遮罩 | Swift NSPanel | `overlay.swift`，半透明白层盖住镜像窗口，点击回报归一化坐标 |
| 配置 | JSON | `configs/*.json` |
| 持久化 | 本地文件 | `data/queue.json`、钥匙串、`data/errors.json`、`logs/` |

**系统权限（TCC）依赖：**

- 辅助功能（Accessibility）：注入点击/按键  
- 屏幕录制：截图 OCR  
- 负责进程通常是：**终端 / Python.app / 脚本合集** 之一；重建 `.app` 或 codesign 会重置授权  

---

## 3. 目录结构

```
game-plugin/
├── coords.py                  # 统一坐标换算（outer/screen/shot）
├── start.command              # 双击入口 → python3 gui.py
├── gui.py                     # HTTP API + 队列 UI 状态 + 遮罩控制
├── mirror_keeper.py           # 核心自动化
├── ui/index.html              # 脚本合集前端
├── configs/
│   ├── catalog.json           # 分组：燕云 / 星穹铁道
│   ├── common.json            # 旧通用前置（ensure/unlock/home/search）
│   ├── yanyun_login.json      # 登录游戏
│   ├── yanyun_juezhanglin.json# 觉樟林
│   ├── yanyun/                # 手点脚本保存目录（燕云）
│   ├── starrail/              # 手点脚本保存目录（星穹铁道）
│   └── keep_alive.json        # 保活（列表隐藏）
├── scripts/
│   ├── launcher.swift         # 桌面 App 启动器（Cocoa NSApp）
│   ├── make-desktop-app.sh    # 编译并复制到 ~/Desktop/脚本合集.app
│   ├── appwin.swift           # WKWebView 窗口
│   ├── wininfo.swift          # 镜像窗口 bounds + windowId
│   ├── ocr.swift              # Vision OCR
│   ├── click.swift            # postToPid 点击/拖/热键/打字
│   ├── overlay.swift          # 校准半透明遮罩
│   ├── clickwatch.swift       # 无遮罩手点录制（全局鼠标监听）
│   ├── match.py / match.swift # 图标模板匹配（现用 match.py）
│   └── mirror.applescript     # 早期 AppleScript（部分仍用 activate）
├── icons/
│   ├── app-icon.jpg           # 桌面图标
│   ├── back.png               # 返回按钮模板（实机裁剪）
│   └── back_alt.png / back_user.png
├── data/                      # gitignore：截图、queue、errors、pid、recordings
└── logs/                      # gitignore：运行日志、shots 校验截图
```

---

## 4. 架构与数据流

```
用户双击 脚本合集.app
    → ScriptBox(launcher) 检测 logs/gui.pid
    → open start.command 或直接 python3 gui.py
        → ThreadingHTTPServer 127.0.0.1:随机端口
        → Popen(appwin, url) 显示 Web UI
            ←→ /api/state|start|queue|overlay|calibrate...

点「开始」
    → run_queue(configs)
        →（可选）kill -9 镜像进程并重开   ← 为了「第一次进游戏横屏」
        → open_game_once()
            → wait_mirror_ready / unlock / 已在游戏则不回桌面
            → 否则 go_home → open_search(cmd-3) → type 中文搜索 → 打开
            → 若竖屏 → recover_landscape（再强制退出镜像，避免第二次打开）
        → run_steps(脚本 steps)
            → wait_screen / close_popups / read_account / ocr_flow
        → watch_loop（可选看守）
```

### 坐标约定（当前实现）

- **统一按 outer（整窗含标题栏）**：`fx, fy ∈ [0,1]`，原点在**外层窗口左上**  
  `point_in_window(fx,fy) = outer_to_screen = (ox + ow*fx, oy + oh*fy)`  
- `wininfo` 同时输出 `content`（假定标题栏 inset=28），但**点击/录制目前不用 content 换算**  
- 校准遮罩 `overlay`、手点监听 `clickwatch` 回报都是 `space=outer`  
- 返回图标识别成功时：横屏实测约 **`(0.866, 0.210)`**（outer）  
- 兜底常量：`BACK_BUTTON` / `BACK_BUTTON_PORT`（outer）  

> ⚠ 文档旧版曾写「fx/fy 相对内容区」——**与现码不一致**。以 `point_in_window` / `clickwatch` 的 outer 为准。  
> 坐标偏移是未闭环问题，见 **§6.6**。

### 点击注入方式（关键）

- **采用**：`CGEvent.postToPid(mirrorPid)` —— 不移动用户鼠标  
- **废弃**：HID `cghidEventTap` 全局点击（会偷光标）；`osascript` keystroke（常报 1002）  
- 热键：`cmd-1` 回主屏、`cmd-3` Spotlight；搜索文字用 unicode `type-text`，**禁止 cmd-v**（镜像里常变成字母 v）  

---

## 5. 核心模块说明

### 5.1 `mirror_keeper.py`

职责：镜像生命周期、OCR、步骤引擎、队列、日志、错误。

重要能力：

| 函数 | 作用 |
|------|------|
| `quit_mirror_hard` / `restart_mirror` | `kill -9` 等价强制退出，再 `open -a` |
| `capture_window` | `screencapture -x -l windowId` |
| `ocr_items` | Vision boxes，用于识字点击 |
| `open_game_once` | **只打开一次游戏**；已在游戏且横屏则跳过回桌面 |
| `recover_landscape` | 竖屏时强制退镜像重连，避免「第二次打开变竖屏」 |
| `close_popups` | 优先 `find_back_button()` 图标匹配，再 OCR「关闭」，再兜底坐标 |
| `find_back_button` | 调 `scripts/match.py` + `icons/back.png` |
| `wait_mirror_ready` | 等到非「正在连接」再操作 |
| `is_wrong_app` | 识别微信等非目标界面 → 回主屏幕，避免对着聊天死循环 OCR |
| `go_home` | cmd-1 + 上滑 + 确认 home |
| `save_shot` | 每步校验截图存 `logs/shots/<run>/` |

步骤类型（`run_step`）：  
`ensure_mirror` / `restart_mirror` / `unlock_if_needed` / `go_home` / `open_search` / `find_and_open_app` / `wait_screen` / `ocr_flow` / `close_popups` / `read_account` / `tap_point`

### 5.2 `gui.py` + `ui/index.html`

- 左：脚本树（燕云 / 星穹铁道），**双击添加**（只显示功能名）  
- 中：执行队列，**双击取消**，可上下移；**持久化 `data/queue.json`**  
- 右：日志可选中复制 + 「复制全部」；上方显示最新校验截图与红点  
- 下：账号、开关（启动前强制退出镜像 / 窗口丢失停止 / 断线重连）  
- **锁定游戏 / 解锁游戏**：控制校准遮罩；普通脚本开始默认锁定，**纯手点回放不锁遮罩**  

API 摘要：

- `GET /api/state`  
- `POST /api/queue/{add,remove,move,clear}`  
- `POST /api/start|pause|stop|clear-errors`  
- `POST /api/overlay/lock|unlock`  
- `POST /api/calibrate/click`（遮罩点击回调）  
- `GET /api/account.png` / `/api/shot.png`  

### 5.3 桌面 App（`launcher.swift`）

- 必须是真正的 `NSApplication`（否则系统报「没有响应」）  
- **不**内嵌 WKWebView、**不**做 ScreenCaptureKit  
- 用 `logs/gui.pid` 判断 GUI 是否在跑（避免 `ps` 扫进程误判 / 堵主线程）  
- `open start.command`，失败再直接起 `python3 gui.py`  

### 5.4 图标匹配（`match.py`）

- 灰度 NCC，只对亮色像素  
- 横屏：ROI 右上 `(0.72,0.05)-(0.98,0.40)`  
- 竖屏：模板旋转 90°，ROI 偏窗口底部（游戏右侧映射到底部）  
- 输出：`fx\tfy\tscore\tscale` 或 `none\tbestScore`  

---

## 6. 关键业务规则（踩坑沉淀）

### 6.1 横屏 / 竖屏（最高优先级）

**现象：** 同一轮 iPhone 镜像会话里，游戏**第一次打开 → 横屏**；退出再开 → **竖屏**。  
系统「强制退出」镜像后再开，又变「第一次」。

**对策：**

1. 队列开始默认 `kill_mirror=true` → `kill -9` 镜像  
2. `open_game_once`：**禁止**「打开成功后再回桌面搜第二次」  
3. 若已在游戏竖屏 → `recover_landscape`（退镜像重连），不要再点开 App  

### 6.2 返回按钮

- 图标形态：黑底浅色双箭头 `<<` + 短横线/点（见 `icons/back.png`）  
- 固定坐标不可靠（窗口黑边、刘海、竖屏旋转都会偏）  
- 当前方案：模板匹配优先；兜底 `(0.866, 0.210)`  

### 6.3 截图 / OCR / TCC

- 在 **Terminal 起的 python** 下，`screencapture -l` 曾成功 OCR 到「更新公告」  
- 把截图逻辑塞进 脚本合集 / ScreenCaptureKit 时，易弹权限或「应用截图失败」  
- `CGWindowListCreateImage` 在新系统不可用 → OCR 不要 `--grab`  
- `screencapture` 可能触发「屏幕与系统音频」授权提示  

### 6.4 焦点与输入

- GUI / 遮罩抢焦点会导致搜索页立刻退出  
- 搜索用 unicode 注入，不用粘贴  
- Spotlight 需要短暂 `bring_front` + `cmd-3`  

### 6.5 错误界面

- 镜像「正在连接」时不要搜索  
- OCR 到微信聊天长文 → `is_wrong_app` → 回主屏幕，禁止死循环识图  

### 6.6 点击偏移 / 预览红点（已按方案落地，待实机验收）

> 方案原则（2026-09-17 实施）：  
> 1) 截图统一 `screencapture -x -o -l` 去阴影  
> 2) 换算只走 `coords.py`  
> 3) 点击最终是屏幕绝对点 + `postToPid`  
> 4) 录制存绝对 CG + 窗口锚点；回放优先 CG+位移  
> 5) UI 红点用 `shot_px/shot_py`  
> 6) content 只日志/兜底，不全链路改  

#### 已实现

| 项 | 状态 |
|----|------|
| `coords.py` | ✅ `outer/screen/shot` 换算 + `build_metrics` + `resolve_screen` |
| `capture_window` | ✅ 仅 `-x -o -l`，截后写 `data/coord_config.json` |
| `wininfo --json` | ✅ `outer`/`content`/`windowId` |
| 手点录制锚点 | ✅ `cg_*` + `outer` + `shot{w,h,scale,origin}` + `shot_px/py` |
| 回放 | ✅ 同尺寸：`cg + Δorigin`；缩放：退回 outer 相对 |
| UI 红点 | ✅ `/api/state` 返回 `shot_w/h` + `shot_px/py` |
| `match.py` | ✅ 仍输出截图归一化；`find_icon` 经 coords → outer |
| 遮罩/clickwatch | ✅ 回调以屏幕绝对点 + outer 锚点为主 |
| 日志格式 | ✅ `metrics ...` + `click source=... outer/screen/shot` |
| 第 0 步验证脚本 | ✅ `python3 scripts/verify_shot_space.py`（需开着镜像） |

#### 验收前请跑

```bash
# 镜像窗口打开时
python3 scripts/verify_shot_space.py
```

期望：`no_shadow` 与 outer 或 content **等比**（如 450×988=outer×2），`shot_space` 不是 `unknown`。

再测：录返回按钮 → 红点在按钮中心 → 窗口不动回放命中 → 移动窗口回放仍命中。

### 6.7 登录能点中 vs 录制/死坐标点不中

**登录脚本真正靠的是识图闭环，不是死坐标：**

| 步骤 | 怎么点 | 为何相对稳 |
|------|--------|------------|
| 关公告 | 图标模板 / OCR「返回」/ 校准坐标，**点完再 OCR 看有没有「继续游戏」**，失败就再点 | 有画面反馈，可重试 |
| 继续游戏 | OCR 找到文字框中心 → `silent_click_at` | 点的是「字在哪」不是「我猜在哪」 |

**录制 / `tap_point` 给坐标：**

- 只发一次 `postToPid`，**不看点完画面变没变**
- 以前配置里的 `tap_point` 还误把整份 step（含旧 `cg_x`）塞进 resolve，和登录路径不一致
- 已改：普通坐标与 `close_popups` 同路；只有带 `outer` 锚点的录制才走 CG+位移

**结论：** 能稳定复现的交互，优先做成 OCR/图标步骤；死坐标只适合「位置几乎不变」的控件，且仍建议包在 `close_popups` / `ocr_flow` 这种可重试结构里。

---

## 7. 当前进度

### 已完成

- [x] 项目骨架、日志、错误暂存、钥匙串密码  
- [x] 窗口检测、截图、Vision OCR、postToPid 点击  
- [x] Web UI 脚本树 / 队列 / 开始暂停停止  
- [x] 桌面 App「脚本合集」可响应、可拉起 GUI  
- [x] 燕云：登录游戏、觉樟林配置  
- [x] 横屏策略（强制退出镜像 + 只打开一次）  
- [x] 关公告：图标识别 + 校验截图 `logs/shots/`  
- [x] 校准遮罩锁定/解锁 + 坐标回写日志  
- [x] 执行列表本地持久化  
- [x] 窗口可拖拽（普通标题栏）；仅日志可选中  

### 部分完成 / 不稳定

- [~] 竖屏镜像下图标匹配（旋转 ROI，成功率低于横屏）  
- [~] 回主屏幕在复杂 App 内有时需多次 cmd-1  
- [~] 「继续游戏」后进游戏内流程仅做到识别停词  
- [~] 账号 OCR 裁剪展示  

### 未完成

- [ ] 星穹铁道任意脚本  
- [ ] 可靠切号  
- [ ] 游戏内任务链（觉樟林具体玩法步骤）  
- [ ] 权限一劳永逸（重建 app 仍可能丢 TCC）  
- [ ] 自动化测试 / CI  
- [ ] Git 首次正式提交与 README（用户未要求前不要擅自 commit）  

---

## 8. 运行方式

```bash
# 开发
cd /Users/ziyuan/code/game-plugin
./start.command
# 或
/usr/bin/python3 ./gui.py

# 重建桌面图标
bash scripts/make-desktop-app.sh
# 产出：~/Desktop/脚本合集.app 与 build/脚本合集.app
```

**建议权限勾选：** 终端、Python、脚本合集 → 辅助功能 + 屏幕录制。  
**建议开关：** 「启动前强制退出镜像」保持勾选。

CLI 保活（无 UI）：

```bash
python3 mirror_keeper.py
python3 mirror_keeper.py --status
python3 mirror_keeper.py --clear-errors
python3 mirror_keeper.py --set-passcode
python3 mirror_keeper.py --self-test
```

---

## 9. 配置约定

脚本 JSON 字段：

- `id` / `group` / `name` / `order`  
- `search` / `keywords`：Spotlight 搜索  
- `steps[]`：步骤数组  
- `keep_alive` / `watch_only` / `reconnect` / `lost_confirm`  
- `use_common`：默认 true；有 `search` 时实际走 `open_game_once`，不再机械执行旧 common 全流程  

列表展示：`catalog.json` 分组 + 各脚本 `group`；`keep_alive` / `common` 不进可选列表。

---

## 10. 已放弃方案（优化时不要回潮）

1. Tkinter GUI（控件不渲染）  
2. ScriptBox 内嵌 WKWebView + ScreenCaptureKit 截图  
3. `screencapture -R` 区域截图作为主路径  
4. HID 全局点击做游戏内操作  
5. `osascript` System Events keystroke 作为主输入  
6. cmd-v 粘贴搜索词  
7. 无 NSApplication 的 headless 启动器（系统报「没有响应」）  
8. 对桌面 App 反复 `codesign --sign -`（重置 TCC）  
9. 关公告点「屏幕右上角固定 0.94,0.11」而不做识别（竖屏/黑边必偏）  

---

## 11. 已知问题与优化方向（给下一任 AI）

### P0 可靠性

1. **横屏保证**：是否还有更稳的方式（私有 API？旋转手机？只杀游戏进程不杀镜像）？  
   - ✅ 已做：`kill_mirror=auto`（已横屏游戏则不杀；竖屏才 `recover_landscape`）  
2. **点击命中**：`postToPid` / outer / content / `screencapture -o` 是否同一套坐标？  
   - 🟡 **方案已落地**（`coords.py` + `-o` + CG 锚点 + shot 红点），**待开镜像实机验收** `verify_shot_space.py`  
   - 详见 §6.6  
3. **返回图标**：OpenCV / Vision template / CoreML 小模型是否比 Pillow NCC 更稳？多分辨率模板包？  
   - ✅ 已做：多模板 `back_land/port` + 横竖屏 ROI；失败走 OCR「返回」；兜底坐标最后防线；`max_fail` 防死循环  
4. **TCC**：如何让截图始终走「已授权」进程，避免弹窗与失败？  
   - ✅ 已做：`--self-test` / UI「权限自检」检测辅助功能+屏幕录制，提示勾选哪个进程  

### P1 架构

1. `mirror_keeper.py` 过大，建议拆：capture / input / ocr / steps / yanyun  
2. 步骤引擎与 UI 状态机是否该用显式状态图（connecting / home / search / game / announcement / playing）  
   - 🟡 已有 `app_phase` 粗状态，完整状态机未拆模块  
3. 配置热更新、脚本市场化  

### P2 产品

1. 觉樟林具体步骤录制工具（遮罩点选生成 JSON）  
   - 🟡 已有手点录制/回放；坐标方案落地后重录验收  
2. 失败自动重试策略与人工接管  
3. 性能：OCR/匹配频率、截图缓存  

### 验证清单（优化后必测）

1. 冷启动：强制退镜像 → 搜燕云 → **横屏**公告  
2. 日志出现「点返回图标」且公告关闭  
3. 出现「继续游戏」并可点入  
4. 中途若变微信：回桌面而不是死循环 OCR  
5. 锁定遮罩可点坐标；解锁后脚本可点穿  
6. 重启 App 后执行列表仍在  
7. 「正在连接」时不乱点；竖屏识别失败会超时停止  
8. **坐标**：`verify_shot_space.py` 等比 → 录制红点准 → 移动窗口回放仍命中（§6.6）

---

## 12. 依赖与约束（写方案时必须遵守）

- 目标机：**仅 macOS + 官方 iPhone 镜像**，不是模拟器、不是 USB 投屏第三方  
- Python：**不要强制上 TypeScript**；用户规则偏好纯 JS/无 TS（本项目 GUI 已是 HTML/JS）  
- 尽量**不新增未说明的 pip 依赖**；已有 Pillow 可用  
- 密码、截图、queue、logs **不进 Git**  
- 用户明确要求前：**不要 commit / push**  
- 中文沟通；改动贴合现有结构，避免大厂式过度重构除非方案明确要求  

---

## 13. 一句话现状

> 燕云登录可用；手点可存到 `configs/yanyun|starrail`。  
> 坐标方案已落地：`coords.py` + 截图去阴影 + CG 锚点回放 + shot 像素红点。  
> **请开镜像跑 `python3 scripts/verify_shot_space.py` 并重录一段验收**（旧录制无完整锚点，建议重录）。

---

## 14. 关键文件索引

| 路径 | 角色 |
|------|------|
| `coords.py` | 统一坐标换算 |
| `mirror_keeper.py` | 自动化核心 |
| `gui.py` | UI 服务与持久化 |
| `ui/index.html` | 前端 |
| `scripts/verify_shot_space.py` | 截图等比验收 |
| `scripts/click.swift` | 输入注入 |
| `scripts/clickwatch.swift` | 无遮罩手点监听 |
| `scripts/match.py` | 返回图标识别 |
| `scripts/overlay.swift` | 坐标校准遮罩 |
| `scripts/launcher.swift` | 桌面启动器 |
| `configs/yanyun_login.json` | 登录流程配置 |
| `icons/back.png` | 返回按钮模板 |

（完）
