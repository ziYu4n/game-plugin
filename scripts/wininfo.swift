import CoreGraphics
import Foundation

let args = Array(CommandLine.arguments.dropFirst())
let debug = args.contains("--debug")
let asJson = args.contains("--json")
let rest = args.filter { $0 != "--debug" && $0 != "--json" }
let target = rest.first(where: { Int($0) == nil }) ?? "iPhone镜像"
let pids = Set(rest.compactMap { Int($0) })

// iPhone 镜像外层窗口含标题栏；content 用固定 inset 估算，仅日志/兜底。
let titlebarInset: CGFloat = 28
let sideInset: CGFloat = 0
let bottomInset: CGFloat = 0

func windows(onScreenOnly: Bool) -> [[String: Any]] {
    var options: CGWindowListOption = [.excludeDesktopElements]
    if onScreenOnly {
        options.insert(.optionOnScreenOnly)
    } else {
        options.insert(.optionAll)
    }
    let info = CGWindowListCopyWindowInfo(options, kCGNullWindowID)
    return (info as? [[String: Any]]) ?? []
}

func describe(_ win: [String: Any]) -> String {
    let owner = win[kCGWindowOwnerName as String] as? String ?? ""
    let name = win[kCGWindowName as String] as? String ?? ""
    let pid = (win[kCGWindowOwnerPID as String] as? NSNumber)?.intValue ?? 0
    let windowId = (win[kCGWindowNumber as String] as? NSNumber)?.intValue ?? 0
    let layer = (win[kCGWindowLayer as String] as? NSNumber)?.intValue ?? 0
    let bounds = win[kCGWindowBounds as String] as? [String: Any] ?? [:]
    let x = Int((bounds["X"] as? NSNumber)?.doubleValue ?? 0)
    let y = Int((bounds["Y"] as? NSNumber)?.doubleValue ?? 0)
    let w = Int((bounds["Width"] as? NSNumber)?.doubleValue ?? 0)
    let h = Int((bounds["Height"] as? NSNumber)?.doubleValue ?? 0)
    return "pid=\(pid) id=\(windowId) owner=\(owner) name=\(name) layer=\(layer) \(x),\(y),\(w),\(h)"
}

func contentOf(x: Int, y: Int, w: Int, h: Int) -> (Int, Int, Int, Int) {
    let top = Int(titlebarInset)
    let side = Int(sideInset)
    let bottom = Int(bottomInset)
    let cx = x + side
    let cy = y + top
    let cw = max(1, w - side * 2)
    let ch = max(1, h - top - bottom)
    return (cx, cy, cw, ch)
}

struct WinPick {
    let x: Int
    let y: Int
    let w: Int
    let h: Int
    let windowId: UInt32
    let cx: Int
    let cy: Int
    let cw: Int
    let ch: Int

    var csv: String {
        "\(x),\(y),\(w),\(h),\(windowId),\(cx),\(cy),\(cw),\(ch)"
    }

    var jsonObject: [String: Any] {
        [
            "windowId": Int(windowId),
            "outer": ["x": x, "y": y, "w": w, "h": h],
            "content": ["x": cx, "y": cy, "w": cw, "h": ch],
        ]
    }
}

func pick(_ list: [[String: Any]]) -> WinPick? {
    var best: (Int, WinPick)? = nil
    for win in list {
        let owner = win[kCGWindowOwnerName as String] as? String ?? ""
        let pid = (win[kCGWindowOwnerPID as String] as? NSNumber)?.intValue ?? 0
        let ownerMatch = owner == target || owner == "iPhone Mirroring" || owner == "iPhone镜像"
        let pidMatch = pid != 0 && pids.contains(pid)
        if !ownerMatch && !pidMatch {
            continue
        }
        let bounds = win[kCGWindowBounds as String] as? [String: Any] ?? [:]
        let x = Int((bounds["X"] as? NSNumber)?.doubleValue ?? 0)
        let y = Int((bounds["Y"] as? NSNumber)?.doubleValue ?? 0)
        let w = Int((bounds["Width"] as? NSNumber)?.doubleValue ?? 0)
        let h = Int((bounds["Height"] as? NSNumber)?.doubleValue ?? 0)
        if w < 50 || h < 50 {
            continue
        }
        let windowId = (win[kCGWindowNumber as String] as? NSNumber)?.uint32Value ?? 0
        let area = w * h
        let portraitBonus = h > w ? 10_000_000 : 0
        let score = area + portraitBonus
        let (cx, cy, cw, ch) = contentOf(x: x, y: y, w: w, h: h)
        let item = WinPick(x: x, y: y, w: w, h: h, windowId: windowId, cx: cx, cy: cy, cw: cw, ch: ch)
        if best == nil || score > best!.0 {
            best = (score, item)
        }
    }
    return best?.1
}

if debug {
    for win in windows(onScreenOnly: false) {
        print(describe(win))
    }
}

if let found = pick(windows(onScreenOnly: true)) ?? pick(windows(onScreenOnly: false)) {
    if asJson {
        if let data = try? JSONSerialization.data(withJSONObject: found.jsonObject, options: []),
           let text = String(data: data, encoding: .utf8) {
            print(text)
        } else {
            print("{\"error\":\"json\"}")
        }
    } else {
        print(found.csv)
    }
    exit(0)
}

if asJson {
    print("{\"windowId\":0,\"outer\":{\"x\":0,\"y\":0,\"w\":0,\"h\":0},\"content\":{\"x\":0,\"y\":0,\"w\":0,\"h\":0},\"error\":\"none\"}")
} else {
    print("none")
}
