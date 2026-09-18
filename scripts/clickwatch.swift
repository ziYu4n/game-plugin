import Cocoa
import Foundation

// 无遮罩录制：全局监听鼠标左键，点在 iPhone 镜像窗口内就回报坐标。
// 不拦截点击，游戏能正常收到，页面会变。

let controlPath = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : ""
let callbackURL = CommandLine.arguments.count > 2 ? CommandLine.arguments[2] : ""

func isWatching() -> Bool {
    guard !controlPath.isEmpty,
          let raw = try? String(contentsOfFile: controlPath, encoding: .utf8) else {
        return false
    }
    let s = raw.trimmingCharacters(in: .whitespacesAndNewlines)
    return s == "1" || s.lowercased() == "watch" || s.lowercased() == "on"
}

func mirrorOuterCG() -> (CGFloat, CGFloat, CGFloat, CGFloat)? {
    let info = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID)
    guard let list = info as? [[String: Any]] else { return nil }
    var best: (Int, CGFloat, CGFloat, CGFloat, CGFloat)? = nil
    for win in list {
        let owner = win[kCGWindowOwnerName as String] as? String ?? ""
        if owner != "iPhone镜像" && owner != "iPhone Mirroring" { continue }
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

func postClick(cgX: Double, cgY: Double, ox: Double, oy: Double, ow: Double, oh: Double) {
    guard !callbackURL.isEmpty, let url = URL(string: callbackURL) else { return }
    var req = URLRequest(url: url)
    req.httpMethod = "POST"
    req.setValue("application/json", forHTTPHeaderField: "Content-Type")
    // 只回报屏幕绝对点 + 窗口锚点；fx/fy 由 Python coords 统一换算
    let body: [String: Any] = [
        "cg_x": cgX, "cg_y": cgY,
        "outer": ["x": ox, "y": oy, "w": ow, "h": oh],
        "outer_x": ox, "outer_y": oy, "outer_w": ow, "outer_h": oh,
        "w": ow, "h": oh,
        "space": "outer",
        "source": "clickwatch",
    ]
    req.httpBody = try? JSONSerialization.data(withJSONObject: body)
    let sem = DispatchSemaphore(value: 0)
    URLSession.shared.dataTask(with: req) { _, _, _ in
        sem.signal()
    }.resume()
    _ = sem.wait(timeout: .now() + 1.5)
}

class AppDelegate: NSObject, NSApplicationDelegate {
    var monitor: Any?
    var lastFire: TimeInterval = 0

    func applicationDidFinishLaunching(_ notification: Notification) {
        // 不吃事件，只旁路观察；需要辅助功能权限
        monitor = NSEvent.addGlobalMonitorForEvents(matching: [.leftMouseDown]) { [weak self] ev in
            self?.onClick(ev)
        }
        if monitor == nil {
            fputs("ERR:无法安装全局鼠标监听，请给当前程序开「辅助功能」\n", stderr)
            // 退回本地监听（仅本进程，基本无效，但避免闪退）
            monitor = NSEvent.addLocalMonitorForEvents(matching: [.leftMouseDown]) { [weak self] ev in
                self?.onClick(ev)
                return ev
            }
        }
        print("CLICKWATCH ready")
        fflush(stdout)
        Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { _ in
            // 保活 runloop；控制文件关掉时不退出，由 Python 杀进程
            _ = isWatching()
        }
    }

    func onClick(_ event: NSEvent) {
        guard isWatching() else { return }
        let now = Date().timeIntervalSince1970
        if now - lastFire < 0.45 { return }
        // 优先用事件自带 CG 坐标，避免 handler 晚到时取到错误鼠标位置
        let cg: CGPoint
        if let ev = event.cgEvent {
            cg = ev.location
        } else if let cur = CGEvent(source: nil)?.location {
            cg = cur
        } else {
            return
        }
        guard let g = mirrorOuterCG() else { return }
        let ox = g.0, oy = g.1, ow = g.2, oh = g.3
        // 略扩命中：标题栏/阴影边缘偶发漏记
        let pad: CGFloat = 2
        if cg.x < ox - pad || cg.x > ox + ow + pad || cg.y < oy - pad || cg.y > oy + oh + pad {
            return
        }
        lastFire = now
        print(String(format: "CLICK cg=%.1f,%.1f outer=%.0f,%.0f %.0fx%.0f", cg.x, cg.y, ox, oy, ow, oh))
        fflush(stdout)
        DispatchQueue.global(qos: .userInitiated).async {
            postClick(cgX: Double(cg.x), cgY: Double(cg.y),
                      ox: Double(ox), oy: Double(oy), ow: Double(ow), oh: Double(oh))
        }
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.accessory)
app.run()
