import Cocoa
import Foundation

let controlPath = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : ""
let callbackURL = CommandLine.arguments.count > 2 ? CommandLine.arguments[2] : ""

func mirrorOuter() -> (CGFloat, CGFloat, CGFloat, CGFloat)? {
    let info = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID)
    guard let list = info as? [[String: Any]] else { return nil }
    var best: (Int, CGFloat, CGFloat, CGFloat, CGFloat)? = nil
    for win in list {
        let owner = win[kCGWindowOwnerName as String] as? String ?? ""
        let ownerMatch = owner == "iPhone镜像" || owner == "iPhone Mirroring"
        if !ownerMatch { continue }
        let bounds = win[kCGWindowBounds as String] as? [String: Any] ?? [:]
        let x = CGFloat((bounds["X"] as? NSNumber)?.doubleValue ?? 0)
        let y = CGFloat((bounds["Y"] as? NSNumber)?.doubleValue ?? 0)
        let w = CGFloat((bounds["Width"] as? NSNumber)?.doubleValue ?? 0)
        let h = CGFloat((bounds["Height"] as? NSNumber)?.doubleValue ?? 0)
        if w < 50 || h < 50 { continue }
        let area = Int(w * h)
        let portraitBonus = h > w ? 10_000_000 : 0
        let score = area + portraitBonus
        if best == nil || score > best!.0 {
            best = (score, x, y, w, h)
        }
    }
    guard let b = best else { return nil }
    return (b.1, b.2, b.3, b.4)
}

func cocoaFrame(fromCG x: CGFloat, y: CGFloat, w: CGFloat, h: CGFloat) -> NSRect {
    // 用点击所在屏的坐标系，避免多屏 maxY 算错
    let screen = NSScreen.screens.first { NSMouseInRect(NSPoint(x: x + w/2, y: ($0.frame.maxY - y - h/2)), $0.frame, false) }
        ?? NSScreen.main
        ?? NSScreen.screens.first
    let maxY = screen?.frame.maxY ?? (NSScreen.screens.map { $0.frame.maxY }.max() ?? 0)
    let cocoaY = maxY - y - h
    return NSRect(x: x, y: cocoaY, width: w, height: h)
}

func isLocked() -> Bool {
    guard !controlPath.isEmpty,
          let raw = try? String(contentsOfFile: controlPath, encoding: .utf8) else {
        return false
    }
    let s = raw.trimmingCharacters(in: .whitespacesAndNewlines)
    return s == "1" || s.lowercased() == "lock" || s.lowercased() == "locked"
}

func postClick(cgX: Double, cgY: Double, ox: Double, oy: Double, ow: Double, oh: Double) {
    guard !callbackURL.isEmpty, let url = URL(string: callbackURL) else { return }
    var req = URLRequest(url: url)
    req.httpMethod = "POST"
    req.setValue("application/json", forHTTPHeaderField: "Content-Type")
    // 回报屏幕绝对点 + 窗口锚点；归一化由 Python coords 统一算
    let body: [String: Any] = [
        "cg_x": cgX, "cg_y": cgY,
        "outer": ["x": ox, "y": oy, "w": ow, "h": oh],
        "outer_x": ox, "outer_y": oy, "outer_w": ow, "outer_h": oh,
        "w": ow, "h": oh,
        "space": "outer",
        "source": "overlay",
    ]
    req.httpBody = try? JSONSerialization.data(withJSONObject: body)
    let sem = DispatchSemaphore(value: 0)
    URLSession.shared.dataTask(with: req) { _, _, _ in
        sem.signal()
    }.resume()
    _ = sem.wait(timeout: .now() + 1.5)
}

class OverlayView: NSView {
    var onClick: ((NSPoint) -> Void)?
    let tip = NSTextField(labelWithString: "点这里记录 · 录制时会立刻脚本复点验证")

    override init(frame frameRect: NSRect) {
        super.init(frame: frameRect)
        wantsLayer = true
        layer?.backgroundColor = NSColor(white: 1.0, alpha: 0.45).cgColor
        tip.font = NSFont.systemFont(ofSize: 13, weight: .semibold)
        tip.textColor = NSColor(white: 0.15, alpha: 0.9)
        tip.alignment = .center
        tip.backgroundColor = .clear
        tip.isBordered = false
        tip.isEditable = false
        tip.isSelectable = false
        addSubview(tip)
    }

    required init?(coder: NSCoder) { fatalError() }

    override func layout() {
        super.layout()
        tip.frame = NSRect(x: 8, y: bounds.midY - 12, width: max(0, bounds.width - 16), height: 24)
    }

    override func mouseDown(with event: NSEvent) {
        let p = convert(event.locationInWindow, from: nil)
        onClick?(p)
    }

    func flash(at p: NSPoint, text: String) {
        let mark = NSView(frame: NSRect(x: p.x - 10, y: p.y - 10, width: 20, height: 20))
        mark.wantsLayer = true
        mark.layer?.backgroundColor = NSColor.systemRed.withAlphaComponent(0.75).cgColor
        mark.layer?.cornerRadius = 10
        addSubview(mark)
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.7) {
            mark.removeFromSuperview()
        }
        tip.stringValue = text
    }
}

class AppDelegate: NSObject, NSApplicationDelegate {
    var window: NSPanel!
    var panelView: OverlayView!
    var timer: Timer?
    var lastBounds: NSRect = .zero
    // ox, oy, ow, oh in CG top-left coords
    var lastGeom: (CGFloat, CGFloat, CGFloat, CGFloat)?
    var lastClickAt: TimeInterval = 0

    func applicationDidFinishLaunching(_ notification: Notification) {
        window = NSPanel(
            contentRect: NSRect(x: 0, y: 0, width: 200, height: 200),
            styleMask: [.borderless, .nonactivatingPanel],
            backing: .buffered,
            defer: false
        )
        window.isOpaque = false
        window.backgroundColor = .clear
        window.hasShadow = false
        window.level = .floating
        window.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        window.isMovableByWindowBackground = false
        window.hidesOnDeactivate = false
        window.ignoresMouseEvents = false

        panelView = OverlayView(frame: .zero)
        panelView.onClick = { [weak self] p in
            self?.handleClick(p)
        }
        window.contentView = panelView
        window.orderOut(nil)

        timer = Timer.scheduledTimer(withTimeInterval: 0.25, repeats: true) { [weak self] _ in
            self?.tick()
        }
        tick()
    }

    func handleClick(_ p: NSPoint) {
        // 防抖：HID 复点别再打到遮罩连环触发
        let now = Date().timeIntervalSince1970
        if now - lastClickAt < 1.2 { return }
        lastClickAt = now
        let w = max(panelView.bounds.width, 1)
        let h = max(panelView.bounds.height, 1)
        // 视图 y 自下而上 → 仅用于遮罩提示；真正坐标用 CG 绝对点
        let fxHint = Double(p.x / w)
        let fyHint = Double(1.0 - p.y / h)
        guard let g = lastGeom else { return }
        let ox = Double(g.0), oy = Double(g.1), ow = Double(g.2), oh = Double(g.3)
        let cgX = ox + ow * fxHint
        let cgY = oy + oh * fyHint
        print(String(format: "CLICK cg=%.1f,%.1f outer=%.0f,%.0f %.0fx%.0f", cgX, cgY, ox, oy, ow, oh))
        fflush(stdout)
        panelView.flash(at: p, text: String(format: "已记 screen %.0f,%.0f", cgX, cgY))
        DispatchQueue.global(qos: .utility).async {
            postClick(cgX: cgX, cgY: cgY, ox: ox, oy: oy, ow: ow, oh: oh)
        }
    }

    func tick() {
        let locked = isLocked()
        guard locked else {
            if window.isVisible {
                window.orderOut(nil)
            }
            return
        }
        guard let g = mirrorOuter() else {
            if window.isVisible {
                window.orderOut(nil)
            }
            return
        }
        lastGeom = g
        // 遮罩盖住整窗（含标题栏），与截图/点击同一套 outer 坐标
        let frame = cocoaFrame(fromCG: g.0, y: g.1, w: g.2, h: g.3)
        if frame != lastBounds {
            lastBounds = frame
            window.setFrame(frame, display: true)
            panelView.needsLayout = true
        }
        if !window.isVisible {
            window.orderFrontRegardless()
        }
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.accessory)
app.run()
