import Cocoa
import CoreGraphics
import Foundation

// 全局 F12「砸开」热键：任何 App 前台都能抓住。
//   F12 → 立刻恢复鼠标 + 写 pulse（Python 终止脚本）
//   F8  → 手动点完继续
// 需要「辅助功能」权限。用 CGEventTap，比 NSEvent 更硬。

let f12Path = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : ""
let f8Path = CommandLine.arguments.count > 2 ? CommandLine.arguments[2] : ""
let clickBin = CommandLine.arguments.count > 3 ? CommandLine.arguments[3] : ""
let keyF12: Int64 = 111
let keyF8: Int64 = 100

var lastFire: TimeInterval = 0
let lock = NSLock()

func pulse(_ path: String) {
    guard !path.isEmpty else { return }
    let ts = String(format: "%.3f", Date().timeIntervalSince1970)
    try? ts.write(toFile: path, atomically: true, encoding: .utf8)
}

func fixMouseNow() {
    // 第一时间砸开鼠标锁，不等 Python
    CGAssociateMouseAndMouseCursorPosition(1)
    if !clickBin.isEmpty {
        let task = Process()
        task.executableURL = URL(fileURLWithPath: clickBin)
        task.arguments = ["--fix-mouse"]
        task.standardOutput = FileHandle.nullDevice
        task.standardError = FileHandle.nullDevice
        try? task.run()
    }
}

func onHotkey(_ keycode: Int64) -> Bool {
    // 返回 true = 吞掉按键（防止浏览器打开开发者工具等）
    lock.lock()
    defer { lock.unlock() }
    let now = Date().timeIntervalSince1970
    if now - lastFire < 0.35 { return true }
    if keycode == keyF12 {
        lastFire = now
        fixMouseNow()
        pulse(f12Path)
        fputs("F12-SMASH\n", stderr)
        return true
    }
    if keycode == keyF8 {
        lastFire = now
        pulse(f8Path)
        fputs("F8-CONTINUE\n", stderr)
        return true
    }
    return false
}

func tapCallback(
    proxy: CGEventTapProxy,
    type: CGEventType,
    event: CGEvent,
    refcon: UnsafeMutableRawPointer?
) -> Unmanaged<CGEvent>? {
    if type == .tapDisabledByTimeout || type == .tapDisabledByUserInput {
        // 被系统掐掉时尽量重新启用
        return Unmanaged.passUnretained(event)
    }
    if type == .keyDown {
        let keycode = event.getIntegerValueField(.keyboardEventKeycode)
        if onHotkey(keycode) {
            return nil // 吞掉 F12/F8
        }
    }
    return Unmanaged.passUnretained(event)
}

func installTap() -> CFMachPort? {
    let mask = CGEventMask(1 << CGEventType.keyDown.rawValue)
    let places: [CGEventTapLocation] = [.cgSessionEventTap, .cghidEventTap]
    for place in places {
        if let tap = CGEvent.tapCreate(
            tap: place,
            place: .headInsertEventTap,
            options: .defaultTap,
            eventsOfInterest: mask,
            callback: tapCallback,
            userInfo: nil
        ) {
            fputs("OK:tap-\(place == .cgSessionEventTap ? "session" : "hid")\n", stderr)
            return tap
        }
    }
    return nil
}

guard let tap = installTap() else {
    fputs("ERR:无法创建全局键盘监听，请给启动程序开「辅助功能」\n", stderr)
    // 退回 NSEvent（弱一些，但仍可用）
    class AppDelegate: NSObject, NSApplicationDelegate {
        var monitor: Any?
        func applicationDidFinishLaunching(_ notification: Notification) {
            monitor = NSEvent.addGlobalMonitorForEvents(matching: [.keyDown]) { ev in
                _ = onHotkey(Int64(ev.keyCode))
            }
            fputs("OK:fallback-nsevent\n", stderr)
        }
    }
    let app = NSApplication.shared
    let del = AppDelegate()
    app.delegate = del
    app.setActivationPolicy(.accessory)
    app.run()
    exit(1)
}

let source = CFMachPortCreateRunLoopSource(kCFAllocatorDefault, tap, 0)
CFRunLoopAddSource(CFRunLoopGetCurrent(), source, .commonModes)
CGEvent.tapEnable(tap: tap, enable: true)

// 看门狗：tap 被禁用时自动打开
Timer.scheduledTimer(withTimeInterval: 2.0, repeats: true) { _ in
    if !CGEvent.tapIsEnabled(tap: tap) {
        CGEvent.tapEnable(tap: tap, enable: true)
        fputs("WARN:re-enable-tap\n", stderr)
    }
}

CFRunLoopRun()
