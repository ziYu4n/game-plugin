import Cocoa
import Darwin

let projectRoot = "__PROJECT_ROOT__"
let startCommand = (projectRoot as NSString).appendingPathComponent("start.command")
let pidFile = (projectRoot as NSString).appendingPathComponent("logs/gui.pid")
let bundleId = "local.game-plugin.scriptbox"

var keptPython: Process?

func appendLog(_ text: String) {
    let logDir = (projectRoot as NSString).appendingPathComponent("logs")
    let logFile = (logDir as NSString).appendingPathComponent("gui-launch.log")
    try? FileManager.default.createDirectory(atPath: logDir, withIntermediateDirectories: true)
    if !FileManager.default.fileExists(atPath: logFile) {
        FileManager.default.createFile(atPath: logFile, contents: nil, attributes: nil)
    }
    guard let handle = FileHandle(forWritingAtPath: logFile) else { return }
    _ = try? handle.seekToEnd()
    if let data = "\(Date()) \(text)\n".data(using: .utf8) {
        try? handle.write(contentsOf: data)
    }
    try? handle.close()
}

func pythonRunning() -> Bool {
    guard let raw = try? String(contentsOfFile: pidFile, encoding: .utf8) else { return false }
    guard let pid = Int32(raw.trimmingCharacters(in: .whitespacesAndNewlines)), pid > 1 else { return false }
    if kill(pid, 0) == 0 { return true }
    return errno == EPERM
}

func activateWindow() {
    for app in NSWorkspace.shared.runningApplications {
        let name = app.executableURL?.lastPathComponent ?? ""
        if name == "appwin" {
            _ = app.activate(options: [.activateIgnoringOtherApps])
        }
    }
}

func openStart() {
    if pythonRunning() {
        appendLog("界面已在运行")
        DispatchQueue.main.async { activateWindow() }
        return
    }
    appendLog("打开 start.command")
    let task = Process()
    task.executableURL = URL(fileURLWithPath: "/usr/bin/open")
    task.arguments = [startCommand]
    task.standardOutput = Pipe()
    task.standardError = Pipe()
    do {
        try task.run()
        task.waitUntilExit()
        appendLog("open 退出码 \(task.terminationStatus)")
    } catch {
        appendLog("open 失败 \(error.localizedDescription)")
    }
    usleep(1200000)
    if pythonRunning() {
        appendLog("界面已起来")
        DispatchQueue.main.async { activateWindow() }
        return
    }
    appendLog("改为直接启动 python")
    let py = Process()
    py.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
    py.arguments = [(projectRoot as NSString).appendingPathComponent("gui.py")]
    py.currentDirectoryURL = URL(fileURLWithPath: projectRoot)
    py.standardOutput = Pipe()
    py.standardError = Pipe()
    do {
        try py.run()
        keptPython = py
        appendLog("python pid=\(py.processIdentifier)")
    } catch {
        appendLog("python 启动失败 \(error.localizedDescription)")
    }
}

class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        let me = ProcessInfo.processInfo.processIdentifier
        for app in NSRunningApplication.runningApplications(withBundleIdentifier: bundleId) {
            if app.processIdentifier != me {
                app.forceTerminate()
            }
        }
        appendLog("脚本合集已启动")
        DispatchQueue.global(qos: .userInitiated).async {
            openStart()
        }
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        DispatchQueue.global(qos: .userInitiated).async {
            openStart()
        }
        return true
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        return false
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.regular)
app.run()
