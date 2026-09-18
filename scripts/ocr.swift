import AppKit
import Foundation
import Vision

let args = CommandLine.arguments
if args.contains("--crop") {
    guard let idx = args.firstIndex(of: "--crop"),
          args.count > idx + 6,
          let x = Double(args[idx + 3]),
          let y = Double(args[idx + 4]),
          let w = Double(args[idx + 5]),
          let h = Double(args[idx + 6]) else {
        fputs("usage: ocr --crop <src> <dst> <x> <y> <w> <h>\n", stderr)
        exit(1)
    }
    let src = args[idx + 1]
    let dst = args[idx + 2]
    guard FileManager.default.fileExists(atPath: src),
          let image = NSImage(contentsOfFile: src),
          let tiff = image.tiffRepresentation,
          let bitmap = NSBitmapImageRep(data: tiff),
          let cg = bitmap.cgImage else {
        fputs("cannot read image\n", stderr)
        exit(3)
    }
    let W = CGFloat(cg.width)
    let H = CGFloat(cg.height)
    let rect = CGRect(
        x: max(0, x) * W,
        y: max(0, 1 - y - h) * H,
        width: max(1, w) * W,
        height: max(1, h) * H
    ).intersection(CGRect(x: 0, y: 0, width: W, height: H))
    guard let cropped = cg.cropping(to: rect) else {
        fputs("crop failed\n", stderr)
        exit(4)
    }
    let out = NSBitmapImageRep(cgImage: cropped)
    guard let png = out.representation(using: .png, properties: [:]) else {
        fputs("png failed\n", stderr)
        exit(5)
    }
    do {
        try png.write(to: URL(fileURLWithPath: dst))
    } catch {
        fputs("write failed\n", stderr)
        exit(6)
    }
    print("OK")
    exit(0)
}

guard args.count >= 2 else {
    fputs("usage: ocr [--boxes] [--accurate] <image>\n       ocr --crop <src> <dst> <x> <y> <w> <h>\n", stderr)
    exit(1)
}

let boxes = args.contains("--boxes")
let path = args.last ?? ""
guard FileManager.default.fileExists(atPath: path) else {
    fputs("file not found\n", stderr)
    exit(2)
}

guard let image = NSImage(contentsOfFile: path),
      let tiff = image.tiffRepresentation,
      let bitmap = NSBitmapImageRep(data: tiff),
      let cgImage = bitmap.cgImage else {
    fputs("cannot read image\n", stderr)
    exit(3)
}

let request = VNRecognizeTextRequest()
request.recognitionLanguages = ["zh-Hans", "zh-Hant", "en-US"]
request.recognitionLevel = args.contains("--accurate") ? .accurate : .fast
request.usesLanguageCorrection = false

let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
do {
    try handler.perform([request])
} catch {
    fputs("ocr failed: \(error.localizedDescription)\n", stderr)
    exit(4)
}

for item in request.results ?? [] {
    guard let text = item.topCandidates(1).first?.string, !text.isEmpty else {
        continue
    }
    if boxes {
        let r = item.boundingBox
        let x = r.origin.x
        let y = 1 - r.origin.y - r.height
        print("\(text)\t\(x)\t\(y)\t\(r.width)\t\(r.height)")
    } else {
        print(text)
    }
}
