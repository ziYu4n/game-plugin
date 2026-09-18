import Cocoa
import Foundation

// 屏幕红点指示器：读 control 文件 "x,y" 或 "hide"，跟在镜像点击位置上。
// 用法: dotmark /path/to/dot_mark.txt

let controlPath = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : ""

func cocoaPoint(cgX: CGFloat, cgY: CGFloat) -> NSPoint {
    let screen = NSScreen.screens.first { NSMouseInRect(NSPoint(x: cgX, y: ($0.frame.maxY - cgY)), $0.frame, false) }
        ?? NSScreen.main
        ?? NSScreen.screens.first
    let maxY = screen?.frame.maxY ?? 0
    return NSPoint(x: cgX, y: maxY - cgY)
}

class DotView: NSView {
    override func draw(_ dirtyRect: NSRect) {
        let r = bounds.insetBy(dx: 2, dy: 2)
        NSColor.systemRed.setFill()
        let path = NSBezierPath(ovalIn: r)
        path.fill()
        NSColor.white.withAlphaComponent(0.9).setStroke()
        path.lineWidth = 2
        path.stroke()
    }
}

class AppDelegate: NSObject, NSApplicationDelegate {
    var window: NSPanel!
    var lastRaw = ""

    func applicationDidFinishLaunching(_ notification: Notification) {
        let size: CGFloat = 28
        window = NSPanel(
            contentRect: NSRect(x: 0, y: 0, width: size, height: size),
            styleMask: [.borderless, .nonactivatingPanel],
            backing: .buffered,
            defer: false
        )
        window.isOpaque = false
        window.backgroundColor = .clear
        window.hasShadow = true
        window.level = .screenSaver // 比镜像还靠前，保证看得见
        window.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        window.hidesOnDeactivate = false
        window.ignoresMouseEvents = true // 不挡点击
        window.contentView = DotView(frame: NSRect(x: 0, y: 0, width: size, height: size))
        window.orderOut(nil)

        Timer.scheduledTimer(withTimeInterval: 0.05, repeats: true) { [weak self] _ in
            self?.tick()
        }
    }

    func tick() {
        guard !controlPath.isEmpty,
              let raw = try? String(contentsOfFile: controlPath, encoding: .utf8) else {
            window.orderOut(nil)
            return
        }
        let s = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        if s == lastRaw { return }
        lastRaw = s
        if s.isEmpty || s == "hide" || s == "0" {
            window.orderOut(nil)
            return
        }
        let parts = s.split(separator: ",")
        guard parts.count >= 2,
              let x = Double(parts[0]),
              let y = Double(parts[1]) else {
            window.orderOut(nil)
            return
        }
        let p = cocoaPoint(cgX: CGFloat(x), cgY: CGFloat(y))
        let size = window.frame.size
        window.setFrameOrigin(NSPoint(x: p.x - size.width / 2, y: p.y - size.height / 2))
        window.orderFrontRegardless()
    }
}

let app = NSApplication.shared
let del = AppDelegate()
app.delegate = del
app.setActivationPolicy(.accessory)
app.run()
