import Cocoa
import WebKit

class AppDelegate: NSObject, NSApplicationDelegate {
    var window: NSWindow!

    func applicationDidFinishLaunching(_ notification: Notification) {
        guard CommandLine.arguments.count > 1,
              let url = URL(string: CommandLine.arguments[1]) else {
            NSApp.terminate(nil)
            return
        }

        let screen = NSScreen.main?.visibleFrame ?? NSRect(x: 0, y: 0, width: 1440, height: 900)
        let width: CGFloat = 1120
        let height: CGFloat = 740
        let rect = NSRect(
            x: screen.midX - width / 2,
            y: screen.midY - height / 2,
            width: width,
            height: height
        )

        window = NSWindow(
            contentRect: rect,
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )
        window.title = "脚本合集"
        window.minSize = NSSize(width: 960, height: 620)
        window.isReleasedWhenClosed = false

        let config = WKWebViewConfiguration()
        let web = WKWebView(frame: .zero, configuration: config)
        web.allowsBackForwardNavigationGestures = false
        window.contentView = web
        web.load(URLRequest(url: url))
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        return true
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.regular)
app.run()
