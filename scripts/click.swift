import CoreGraphics
import Foundation

/*
 点击注入两种路径（务必别混）：

 1) postToPid(pid, x, y)
    - CGEvent.postToPid：事件只进指定进程，不抢系统光标。
    - 适合 soft / Spotlight；镜像游戏内常被隔离，表现为「预览对了游戏没反应」。

 2) --hid-nowarp <x> <y>  → postClickHidNoWarp
    - CGEvent.post(tap: .cghidEventTap)，事件带绝对屏幕坐标。
    - **不** CGWarpMouseCursorPosition，**不**断开鼠标关联。
    - 用户光标看起来不动，但系统仍可能把「点击」送到坐标处的前台窗口
      （所以校准遮罩必须先藏掉，否则会连环打到遮罩）。
    - 用于：游戏内脚本点击、回放、手校复点。不是「废弃 HID」的反例——
      废弃的是会偷光标的 warp / 断关联那条；nowarp 是折中。

 3) --hid-restore <x> <y>
    - 瞬移光标点一下再移回；仅作 nowarp 失败时的兜底。
    - 绝不断开 CGAssociateMouseAndMouseCursorPosition。

 4) --fix-mouse
    - 强制恢复鼠标↔光标关联（F12 / 异常恢复）。
*/

let digitKeys: [Character: CGKeyCode] = [
    "0": 29, "1": 18, "2": 19, "3": 20, "4": 21,
    "5": 23, "6": 22, "7": 26, "8": 28, "9": 25
]

func currentMouse() -> CGPoint {
    return CGEvent(source: nil)?.location ?? .zero
}

func restoreMouse(_ point: CGPoint) {
    CGWarpMouseCursorPosition(point)
    CGAssociateMouseAndMouseCursorPosition(1)
}

func postToHid(_ event: CGEvent?) {
    event?.post(tap: .cghidEventTap)
}

func postClick(pid: pid_t, x: Double, y: Double) {
    let point = CGPoint(x: x, y: y)
    let src = CGEventSource(stateID: .hidSystemState)
    // 先 mouseMoved，再 down/up，提高 postToPid 命中率
    let move = CGEvent(mouseEventSource: src, mouseType: .mouseMoved, mouseCursorPosition: point, mouseButton: .left)
    let down = CGEvent(mouseEventSource: src, mouseType: .leftMouseDown, mouseCursorPosition: point, mouseButton: .left)
    let up = CGEvent(mouseEventSource: src, mouseType: .leftMouseUp, mouseCursorPosition: point, mouseButton: .left)
    move?.postToPid(pid)
    usleep(20000)
    down?.postToPid(pid)
    usleep(40000)
    up?.postToPid(pid)
}

/// HID 点击：不移动光标，只把带绝对坐标的事件打进系统。
/// 镜像对 postToPid 常隔离；瞬移光标又会「抢鼠标」。这条折中。
func postClickHidNoWarp(x: Double, y: Double) {
    let point = CGPoint(x: x, y: y)
    let src = CGEventSource(stateID: .hidSystemState)
    let move = CGEvent(mouseEventSource: src, mouseType: .mouseMoved, mouseCursorPosition: point, mouseButton: .left)
    let down = CGEvent(mouseEventSource: src, mouseType: .leftMouseDown, mouseCursorPosition: point, mouseButton: .left)
    let up = CGEvent(mouseEventSource: src, mouseType: .leftMouseUp, mouseCursorPosition: point, mouseButton: .left)
    move?.location = point
    down?.location = point
    up?.location = point
    // 标记为「已发生过移动」，提高部分 App 命中率
    move?.flags = []
    down?.flags = []
    up?.flags = []
    postToHid(move)
    usleep(20000)
    postToHid(down)
    usleep(45000)
    postToHid(up)
    usleep(20000)
}

/// HID 点击：瞬移光标点一下再移回。绝不断开鼠标↔光标关联（否则会卡死鼠标）。
func postClickHidRestore(x: Double, y: Double) {
    let old = currentMouse()
    let point = CGPoint(x: x, y: y)
    let src = CGEventSource(stateID: .hidSystemState)
    // 始终保持关联；用 defer 保证异常也能恢复光标位置
    defer {
        CGWarpMouseCursorPosition(old)
        CGAssociateMouseAndMouseCursorPosition(1)
    }
    CGAssociateMouseAndMouseCursorPosition(1)
    CGWarpMouseCursorPosition(point)
    usleep(12000)
    let move = CGEvent(mouseEventSource: src, mouseType: .mouseMoved, mouseCursorPosition: point, mouseButton: .left)
    let down = CGEvent(mouseEventSource: src, mouseType: .leftMouseDown, mouseCursorPosition: point, mouseButton: .left)
    let up = CGEvent(mouseEventSource: src, mouseType: .leftMouseUp, mouseCursorPosition: point, mouseButton: .left)
    postToHid(move)
    usleep(15000)
    postToHid(down)
    usleep(35000)
    postToHid(up)
    usleep(15000)
}

func postDrag(pid: pid_t, x1: Double, y1: Double, x2: Double, y2: Double) {
    let src = CGEventSource(stateID: .hidSystemState)
    let start = CGPoint(x: x1, y: y1)
    let end = CGPoint(x: x2, y: y2)
    let down = CGEvent(mouseEventSource: src, mouseType: .leftMouseDown, mouseCursorPosition: start, mouseButton: .left)
    down?.postToPid(pid)
    let steps = 18
    for i in 1...steps {
        let t = Double(i) / Double(steps)
        let p = CGPoint(x: x1 + (x2 - x1) * t, y: y1 + (y2 - y1) * t)
        let drag = CGEvent(mouseEventSource: src, mouseType: .leftMouseDragged, mouseCursorPosition: p, mouseButton: .left)
        drag?.postToPid(pid)
        usleep(8000)
    }
    let up = CGEvent(mouseEventSource: src, mouseType: .leftMouseUp, mouseCursorPosition: end, mouseButton: .left)
    up?.postToPid(pid)
}

func postSwipeScroll(x: Double, y: Double, dx: Int32) {
    let point = CGPoint(x: x, y: y)
    let src = CGEventSource(stateID: .hidSystemState)
    for _ in 0..<4 {
        if let ev = CGEvent(scrollWheelEvent2Source: src, units: .pixel, wheelCount: 2, wheel1: 0, wheel2: dx, wheel3: 0) {
            ev.location = point
            ev.flags = CGEventFlags.maskShift
            postToHid(ev)
        }
        usleep(40000)
    }
}

let letterKeys: [Character: CGKeyCode] = [
    "a": 0, "b": 11, "c": 8, "d": 2, "e": 14, "f": 3,
    "g": 5, "h": 4, "i": 34, "j": 38, "k": 40, "l": 37,
    "m": 46, "n": 45, "o": 31, "p": 35, "q": 12, "r": 15,
    "s": 1, "t": 17, "u": 32, "v": 9, "w": 13, "x": 7,
    "y": 16, "z": 6
]

func postKeyEvent(pid: pid_t, code: CGKeyCode, flags: CGEventFlags, unicode: UniChar? = nil, useHid: Bool = false) {
    let src = CGEventSource(stateID: .hidSystemState)
    let down = CGEvent(keyboardEventSource: src, virtualKey: code, keyDown: true)
    let up = CGEvent(keyboardEventSource: src, virtualKey: code, keyDown: false)
    down?.flags = flags
    up?.flags = flags
    if var ch = unicode {
        down?.keyboardSetUnicodeString(stringLength: 1, unicodeString: &ch)
        up?.keyboardSetUnicodeString(stringLength: 1, unicodeString: &ch)
    }
    if useHid {
        postToHid(down)
        usleep(35000)
        postToHid(up)
    } else {
        down?.postToPid(pid)
        usleep(35000)
        up?.postToPid(pid)
    }
}

func postHotkey(pid: pid_t, name: String, useHid: Bool = false) {
    var flags: CGEventFlags = []
    var key = name.lowercased()
    if key.hasPrefix("cmd-") || key.hasPrefix("command-") {
        flags.insert(.maskCommand)
        key = key.replacingOccurrences(of: "cmd-", with: "")
        key = key.replacingOccurrences(of: "command-", with: "")
    }
    var code: CGKeyCode = 0
    if key == "return" || key == "enter" {
        code = 36
    } else if key == "=" || key == "equal" {
        code = 24
    } else if key == "+" || key == "plus" {
        // ⌘+ = View > Larger（= 键 + Shift）
        code = 24
        flags.insert(.maskShift)
    } else if key == "-" || key == "minus" {
        code = 27
    } else if key == "0" {
        code = 29
    } else if key.count == 1, let ch = key.first, let mapped = digitKeys[ch] {
        code = mapped
    } else if key.count == 1, let ch = key.first, let mapped = letterKeys[ch] {
        code = mapped
    }
    let src = CGEventSource(stateID: .hidSystemState)
    if flags.contains(.maskCommand) {
        let cmdDown = CGEvent(keyboardEventSource: src, virtualKey: 55, keyDown: true)
        cmdDown?.flags = .maskCommand
        if useHid {
            postToHid(cmdDown)
        } else {
            cmdDown?.postToPid(pid)
        }
        usleep(25000)
    }
    postKeyEvent(pid: pid, code: code, flags: flags, useHid: useHid)
    if flags.contains(.maskCommand) {
        let cmdUp = CGEvent(keyboardEventSource: src, virtualKey: 55, keyDown: false)
        if useHid {
            postToHid(cmdUp)
        } else {
            cmdUp?.postToPid(pid)
        }
        usleep(25000)
    }
}

func postText(pid: pid_t, text: String) {
    // 直接注入中文，不走粘贴。Command+V 在镜像里经常只变成字母 v
    let src = CGEventSource(stateID: .hidSystemState)
    for ch in text.utf16 {
        var uni = UniChar(ch)
        let down = CGEvent(keyboardEventSource: src, virtualKey: 0xFFFF, keyDown: true)
        let up = CGEvent(keyboardEventSource: src, virtualKey: 0xFFFF, keyDown: false)
        down?.keyboardSetUnicodeString(stringLength: 1, unicodeString: &uni)
        up?.keyboardSetUnicodeString(stringLength: 1, unicodeString: &uni)
        down?.postToPid(pid)
        usleep(25000)
        up?.postToPid(pid)
        usleep(55000)
    }
}

func postKey(pid: pid_t, ch: Character) {
    let src = CGEventSource(stateID: .hidSystemState)
    let code = digitKeys[ch] ?? 0
    let down = CGEvent(keyboardEventSource: src, virtualKey: code, keyDown: true)
    let up = CGEvent(keyboardEventSource: src, virtualKey: code, keyDown: false)
    var unichar = UniChar(ch.utf16.first ?? 0)
    down?.keyboardSetUnicodeString(stringLength: 1, unicodeString: &unichar)
    up?.keyboardSetUnicodeString(stringLength: 1, unicodeString: &unichar)
    down?.postToPid(pid)
    usleep(20000)
    up?.postToPid(pid)
}

func keychainPin() -> String {
    let task = Process()
    task.executableURL = URL(fileURLWithPath: "/usr/bin/security")
    let user = NSUserName()
    task.arguments = ["find-generic-password", "-a", user, "-s", "game-plugin.iphone-passcode", "-w"]
    let pipe = Pipe()
    task.standardOutput = pipe
    task.standardError = Pipe()
    do {
        try task.run()
        task.waitUntilExit()
    } catch {
        return ""
    }
    let data = pipe.fileHandleForReading.readDataToEndOfFile()
    return String(data: data, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
}

let args = Array(CommandLine.arguments.dropFirst())
if args.count >= 1 && args[0] == "--fix-mouse" {
    CGAssociateMouseAndMouseCursorPosition(1)
    print("OK")
    exit(0)
}
if args.count < 2 {
    fputs("usage: click <pid> <x> <y>\n       click --hid-nowarp <x> <y>\n       click --hid-restore <x> <y>\n       click --fix-mouse\n       click --drag <pid> <x1> <y1> <x2> <y2>\n       click --swipe <x> <y> <dx>\n       click --hotkey <pid> <cmd-1>\n       click --hotkey-hid <pid> <cmd-1>\n       click --type-text <pid> <text>\n       click --type-pin <pid>\n", stderr)
    exit(1)
}

if args[0] == "--type-pin" {
    guard let pid = Int32(args[1]) else {
        fputs("ERR:bad-pid\n", stderr)
        exit(1)
    }
    let pin = keychainPin()
    if pin.isEmpty {
        fputs("ERR:empty-pin\n", stderr)
        exit(2)
    }
    for ch in pin {
        postKey(pid: pid, ch: ch)
        usleep(80000)
    }
    print("OK")
    exit(0)
}

if args[0] == "--hid-nowarp" {
    guard args.count >= 3,
          let x = Double(args[1]),
          let y = Double(args[2]) else {
        fputs("ERR:bad-args\n", stderr)
        exit(1)
    }
    postClickHidNoWarp(x: x, y: y)
    print("OK")
    exit(0)
}

if args[0] == "--hid-restore" {
    guard args.count >= 3,
          let x = Double(args[1]),
          let y = Double(args[2]) else {
        fputs("ERR:bad-args\n", stderr)
        exit(1)
    }
    postClickHidRestore(x: x, y: y)
    print("OK")
    exit(0)
}

if args[0] == "--drag" {
    guard args.count >= 6,
          let pid = Int32(args[1]),
          let x1 = Double(args[2]),
          let y1 = Double(args[3]),
          let x2 = Double(args[4]),
          let y2 = Double(args[5]) else {
        fputs("ERR:bad-args\n", stderr)
        exit(1)
    }
    postDrag(pid: pid, x1: x1, y1: y1, x2: x2, y2: y2)
    print("OK")
    exit(0)
}

if args[0] == "--swipe" {
    guard args.count >= 4,
          let x = Double(args[1]),
          let y = Double(args[2]),
          let dx = Int32(args[3]) else {
        fputs("ERR:bad-args\n", stderr)
        exit(1)
    }
    postSwipeScroll(x: x, y: y, dx: dx)
    print("OK")
    exit(0)
}

if args[0] == "--hotkey" || args[0] == "--hotkey-hid" {
    guard args.count >= 3, let pid = Int32(args[1]) else {
        fputs("ERR:bad-args\n", stderr)
        exit(1)
    }
    postHotkey(pid: pid, name: args[2], useHid: args[0] == "--hotkey-hid")
    print("OK")
    exit(0)
}

if args[0] == "--type-text" {
    guard args.count >= 3, let pid = Int32(args[1]) else {
        fputs("ERR:bad-args\n", stderr)
        exit(1)
    }
    let text = args[2...].joined(separator: " ")
    postText(pid: pid, text: text)
    print("OK")
    exit(0)
}

guard args.count >= 3,
      let pid = Int32(args[0]),
      let x = Double(args[1]),
      let y = Double(args[2]) else {
    fputs("ERR:bad-args\n", stderr)
    exit(1)
}

postClick(pid: pid, x: x, y: y)
print("OK")
