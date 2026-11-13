import Cocoa
import Darwin

let projectRoot = "__PROJECT_ROOT__"
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

func pidAlive(_ pid: Int32) -> Bool {
    guard pid > 1 else { return false }
    if kill(pid, 0) == 0 { return true }
    return errno == EPERM
}

func discoverPythonPid() -> Int32? {
    let task = Process()
    let pipe = Pipe()
    task.executableURL = URL(fileURLWithPath: "/usr/bin/pgrep")
    task.arguments = ["-f", "\(projectRoot)/gui.py"]
    task.standardOutput = pipe
    task.standardError = FileHandle.nullDevice
    do {
        try task.run()
        task.waitUntilExit()
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        let text = String(data: data, encoding: .utf8) ?? ""
        for line in text.split(whereSeparator: { $0.isWhitespace }) {
            if let pid = Int32(line), pidAlive(pid) { return pid }
        }
    } catch {
        appendLog("查找现有 python 失败 \(error.localizedDescription)")
    }
    return nil
}

func pythonRunning() -> Bool {
    if let raw = try? String(contentsOfFile: pidFile, encoding: .utf8),
       let pid = Int32(raw.trimmingCharacters(in: .whitespacesAndNewlines)),
       pidAlive(pid) {
        return true
    }
    if let pid = discoverPythonPid() {
        try? "\(pid)".write(toFile: pidFile, atomically: true, encoding: .utf8)
        appendLog("复用现有 python pid=\(pid)")
        return true
    }
    return false
}

func activateWindow() {
    for app in NSWorkspace.shared.runningApplications {
        let name = app.executableURL?.lastPathComponent ?? ""
        if name == "appwin" {
            _ = app.activate(options: [])
        }
    }
}

func openStart() {
    if pythonRunning() {
        appendLog("界面已在运行")
        DispatchQueue.main.async { activateWindow() }
        return
    }
    appendLog("后台启动 python（不打开终端）")
    let py = Process()
    py.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
    py.arguments = [(projectRoot as NSString).appendingPathComponent("gui.py")]
    py.currentDirectoryURL = URL(fileURLWithPath: projectRoot)
    py.standardOutput = FileHandle.nullDevice
    py.standardError = FileHandle.nullDevice
    var environment = ProcessInfo.processInfo.environment
    environment["PYTHONUNBUFFERED"] = "1"
    py.environment = environment
    do {
        try py.run()
        keptPython = py
        appendLog("python pid=\(py.processIdentifier)")
        usleep(1000000)
        DispatchQueue.main.async { activateWindow() }
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
