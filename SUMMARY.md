# 脚本合集 · 当前总结（2026-09-18）

面向日常使用与后续改代码。更早期的架构评审见 `PROJECT.md`。

---

## 1. 是什么

在 Mac 上操作官方 **iPhone 镜像**，用本地 UI「脚本合集」排队跑《燕云十六声》等自动化。

| 入口 | 说明 |
|------|------|
| 桌面 `脚本合集.app` / `start.command` | 拉起 `python3 gui.py` |
| 界面 | `ui/index.html`（WKWebView） |
| 核心 | `mirror_keeper.py`（步骤引擎、OCR、点击） |
| 配置 | `configs/*.json` |

**系统权限（只授一次，勿折腾）：**

- 屏幕录制 → 截图 / OCR  
- 辅助功能 → 点击注入、**全局** F12/F8  

授给实际跑起来的进程（脚本合集 / Python / 终端）。**禁止**启动探针 `screencapture`、禁止无意义重签二进制（会换 CDHash 导致再弹窗）。规则见 `.cursor/rules/no-tcc-spam.mdc`。

### 全局热键（`scripts/hotkey.swift`）

| 键 | 行为 |
|----|------|
| **F12** | 全局砸开：终止任务并 `restore-mouse`；空闲再按可开始 |
| **F8** | 全局：assist 模式「人手点完」后继续 |

与窗口是否聚焦无关；可能与其他 App 的 F12/F8 冲突。

---

## 2. 现有脚本

| ID | 名称 | 说明 |
|----|------|------|
| `yanyun_login` | 登录游戏 | 搜索开游戏 → **关公告** → 继续游戏 |
| `yanyun_moyu` | 日常刷么鱼 | **已在游戏内**；无关公告、无 `use_common` |
| `yanyun_juezhanglin` | 觉樟林 | 旧流程，含关公告 |
| `configs/yanyun/rec_*.json` | 手点录制脚本 | 可删 |

刷么鱼步骤：菜单 → 角色名 → 同游 → 止戈 → 觉障林×2 → 开始匹配 → 杀后台。每步 `calib_key` 优先手校点位。

---

## 3. 手校点位（统一表 + 锚点）

数据：`data/moyu_points.json`（**version 3**）。登录「关公告返回键」已并入同一张表（`key=back_button`, `scope=yanyun_login`），不再单独依赖业务逻辑；旧 `data/back_button.json` 仅作迁移源。

```json
{
  "version": 3,
  "items": [
    {
      "key": "menu",
      "label": "菜单按钮",
      "scope": "yanyun_moyu",
      "portrait": {
        "fx": 0.92, "fy": 0.91,
        "cg_x": 555.0, "cg_y": 940.0,
        "outer": { "x": 100, "y": 50, "w": 400, "h": 900 },
        "updated_at": "..."
      }
    }
  ]
}
```

| 字段 | 作用 |
|------|------|
| `fx/fy` | outer 相对坐标（尺寸变了时的兜底） |
| `cg_x/cg_y` + `outer` | 绝对屏幕点 + 校准时窗口锚点 |
| 回放 | **窗口尺寸不变** → `cg + 位移`；**尺寸变了** → 退回 `fx/fy`（`coords.resolve_screen`） |

方向判定：`current_orientation()` = `outer.w > outer.h ? landscape : portrait`，回放日志带 `orient=`。

### 怎么用

1. **新增** → 选中一行 → **锁定游戏** → 点镜像真实按钮  
2. 记坐标后：勾选「校准后复点」且 key 在白名单 → **复点 1 次并解锁**  
3. 白名单外（自定义危险按钮）只存坐标不复点  
4. ↑↓ / 改 / 清 / 删  

列表里带 ⚓ 表示已存锚点（可跟窗口平移）。

---

## 4. 点击策略（写清边界）

见 `scripts/click.swift` 顶部注释。

| 模式 | 实现 | 何时用 |
|------|------|--------|
| `postToPid` | 事件只进镜像进程，不抢光标 | soft / Spotlight |
| `--hid-nowarp` | `cghidEventTap` + 绝对坐标，**不 warp 光标** | 游戏内脚本、回放、手校复点（镜像里 pid 常无效） |
| `--hid-restore` | 瞬移再移回 | nowarp 失败兜底 |
| `--fix-mouse` | 恢复鼠标关联 | F12 / 异常 |

**不是**「废弃一切 HID」：废弃的是会偷光标 / 断关联的做法；nowarp 是折中。校准遮罩必须先藏再 HID，否则会连环打到遮罩。

---

## 5. 截图与坐标

```bash
screencapture -x -o -l <windowId> <path>
```

**已加 `-o` 去阴影**（`capture_window`）。没有 `-o` 时 `coords.py` 的 shot↔screen 会偏；手校绝对点相对不敏感，但模板/OCR/红点会漂。

`coords.py` 是唯一换算入口：谁在什么场景用哪个函数写在文件头 docstring。

---

## 6. 关键文件

```
mirror_keeper.py     步骤引擎、手校存取、OCR/模板点击
gui.py               HTTP、队列、遮罩/录制、手校 API
ui/index.html        界面（手校列表）
coords.py            outer / screen / shot；resolve_screen 锚点回放
configs/yanyun_moyu.json
configs/yanyun_login.json
data/moyu_points.json   统一手校表（含 back_button）
data/back_button.json   仅迁移兼容
scripts/overlay.swift / clickwatch.swift / click.swift / hotkey.swift
.cursor/rules/no-tcc-spam.mdc
```

---

## 7. 硬约束

1. 不要用 `screencapture` 做权限探针。  
2. 不要每次启动 `codesign --force`；只在真正重编后签一次。  
3. 不要无意义 `touch` Swift 源码触发重编。  
4. 截图失败要冷却。  
5. 刷么鱼 **没有关公告**；关公告用点位 `back_button` + 登录脚本。  

---

## 8. 验证清单

- [ ] 冷启动 → 登录 → 关公告 → 继续游戏  
- [ ] 刷么鱼全链路  
- [ ] 手校：新增 → 锁定 → 点按钮 → 复点 1 次 → 解锁  
- [ ] 手校：窗口平移后回放仍命中（有 ⚓ 时走 cg+delta）  
- [ ] 横竖屏切换读对方向  
- [ ] F12 全局终止并恢复鼠标；F8 继续  
- [ ] 截图 `-o`：预览红点与按钮重合  
- [ ] 冷启动不弹权限窗  
- [ ] `queue.json` 重启仍在  
