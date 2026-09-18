import AppKit
import Foundation

func loadGray(_ path: String) -> (pixels: [Float], width: Int, height: Int)? {
    guard let image = NSImage(contentsOfFile: path),
          let tiff = image.tiffRepresentation,
          let rep = NSBitmapImageRep(data: tiff),
          let cg = rep.cgImage else { return nil }
    let w = cg.width
    let h = cg.height
    var raw = [UInt8](repeating: 0, count: w * h * 4)
    guard let ctx = CGContext(
        data: &raw,
        width: w,
        height: h,
        bitsPerComponent: 8,
        bytesPerRow: w * 4,
        space: CGColorSpaceCreateDeviceRGB(),
        bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
    ) else { return nil }
    ctx.draw(cg, in: CGRect(x: 0, y: 0, width: w, height: h))
    var gray = [Float](repeating: 0, count: w * h)
    for i in 0..<(w * h) {
        let o = i * 4
        gray[i] = Float(raw[o]) * 0.299 + Float(raw[o + 1]) * 0.587 + Float(raw[o + 2]) * 0.114
    }
    return (gray, w, h)
}

func resizeNearest(_ src: [Float], sw: Int, sh: Int, dw: Int, dh: Int) -> [Float] {
    var out = [Float](repeating: 0, count: dw * dh)
    for y in 0..<dh {
        let sy = min(sh - 1, y * sh / dh)
        for x in 0..<dw {
            let sx = min(sw - 1, x * sw / dw)
            out[y * dw + x] = src[sy * sw + sx]
        }
    }
    return out
}

func rotate90CW(_ src: [Float], w: Int, h: Int) -> ([Float], Int, Int) {
    let nw = h
    let nh = w
    var out = [Float](repeating: 0, count: nw * nh)
    for y in 0..<h {
        for x in 0..<w {
            out[x * nw + (h - 1 - y)] = src[y * w + x]
        }
    }
    return (out, nw, nh)
}

func prepareNeedle(_ needle: [Float]) -> (idxs: [Int], vals: [Float], mean: Float, std: Float)? {
    var idxs = [Int]()
    var vals = [Float]()
    for i in 0..<needle.count {
        if needle[i] >= 70 {
            idxs.append(i)
            vals.append(needle[i])
        }
    }
    if idxs.count < 14 { return nil }
    let n = Float(idxs.count)
    let mean = vals.reduce(0, +) / n
    let varSum = vals.reduce(0) { $0 + ($1 - mean) * ($1 - mean) } / n
    let std = sqrt(max(Float(1e-2), varSum))
    return (idxs, vals, mean, std)
}

func ncc(hay: [Float], hw: Int, nw: Int, prep: (idxs: [Int], vals: [Float], mean: Float, std: Float), x: Int, y: Int) -> Float {
    let n = Float(prep.idxs.count)
    var pSum: Float = 0
    var pSum2: Float = 0
    for ti in prep.idxs {
        let tx = ti % nw
        let ty = ti / nw
        let pv = hay[(y + ty) * hw + (x + tx)]
        pSum += pv
        pSum2 += pv * pv
    }
    let pMean = pSum / n
    let pVar = max(Float(1e-2), pSum2 / n - pMean * pMean)
    var cov: Float = 0
    for k in 0..<prep.idxs.count {
        let ti = prep.idxs[k]
        let tx = ti % nw
        let ty = ti / nw
        let pv = hay[(y + ty) * hw + (x + tx)]
        cov += (pv - pMean) * (prep.vals[k] - prep.mean)
    }
    cov /= n
    let score = cov / (sqrt(pVar) * prep.std)
    return max(-1, min(1, score))
}

func matchInROI(hay: [Float], hw: Int, hh: Int, needle: [Float], nw: Int, nh: Int,
                x0: Int, y0: Int, x1: Int, y1: Int, step: Int) -> (Float, Int, Int)? {
    guard let prep = prepareNeedle(needle) else { return nil }
    if nw >= hw || nh >= hh { return nil }
    let xs = max(0, x0)
    let ys = max(0, y0)
    let xe = min(hw - nw, x1)
    let ye = min(hh - nh, y1)
    if xs > xe || ys > ye { return nil }
    var best: Float = -2
    var bx = xs
    var by = ys
    var y = ys
    while y <= ye {
        var x = xs
        while x <= xe {
            let s = ncc(hay: hay, hw: hw, nw: nw, prep: prep, x: x, y: y)
            if s > best {
                best = s
                bx = x
                by = y
            }
            x += step
        }
        y += step
    }
    let rx0 = max(xs, bx - step)
    let ry0 = max(ys, by - step)
    let rx1 = min(xe, bx + step)
    let ry1 = min(ye, by + step)
    for yy in ry0...ry1 {
        for xx in rx0...rx1 {
            let s = ncc(hay: hay, hw: hw, nw: nw, prep: prep, x: xx, y: yy)
            if s > best {
                best = s
                bx = xx
                by = yy
            }
        }
    }
    return (best, bx, by)
}

var args = Array(CommandLine.arguments.dropFirst())
var roi: (Double, Double, Double, Double)? = nil
if let i = args.firstIndex(of: "--roi"), i + 4 < args.count {
    roi = (Double(args[i + 1]) ?? 0, Double(args[i + 2]) ?? 0, Double(args[i + 3]) ?? 1, Double(args[i + 4]) ?? 1)
    args.removeSubrange(i...(i + 4))
}
guard args.count >= 2 else {
    fputs("usage: match <hay.png> <needle.png> [minScore] [--roi x y w h]\n", stderr)
    exit(1)
}
let hayPath = args[0]
let needlePath = args[1]
let minScore = args.count >= 3 ? (Float(args[2]) ?? 0.75) : 0.75

guard let hay = loadGray(hayPath), let needle0 = loadGray(needlePath) else {
    fputs("ERR:cannot-read\n", stderr)
    exit(2)
}

var templates: [([Float], Int, Int)] = [(needle0.pixels, needle0.width, needle0.height)]
var cur = (needle0.pixels, needle0.width, needle0.height)
for _ in 1...3 {
    let r = rotate90CW(cur.0, w: cur.1, h: cur.2)
    templates.append(r)
    cur = r
}

let rx = roi?.0 ?? 0
let ry = roi?.1 ?? 0
let rw = roi?.2 ?? 1
let rh = roi?.3 ?? 1
let x0 = Int(Double(hay.width) * rx)
let y0 = Int(Double(hay.height) * ry)
let x1 = Int(Double(hay.width) * (rx + rw))
let y1 = Int(Double(hay.height) * (ry + rh))

var best: (Float, Double, Double, Double)? = nil
let scales: [Double] = [0.85, 1.0, 1.2, 1.45, 1.7, 2.0, 2.4, 2.9]
for tpl in templates {
    for scale in scales {
        let tw = max(12, Int(Double(tpl.1) * scale))
        let th = max(12, Int(Double(tpl.2) * scale))
        if tw >= hay.width || th >= hay.height { continue }
        let scaled = resizeNearest(tpl.0, sw: tpl.1, sh: tpl.2, dw: tw, dh: th)
        let step = max(1, min(3, max(tw, th) / 10))
        if let hit = matchInROI(hay: hay.pixels, hw: hay.width, hh: hay.height, needle: scaled, nw: tw, nh: th, x0: x0, y0: y0, x1: x1 - tw, y1: y1 - th, step: step) {
            let cx = Double(hit.1) + Double(tw) / 2.0
            let cy = Double(hit.2) + Double(th) / 2.0
            if best == nil || hit.0 > best!.0 {
                best = (hit.0, cx, cy, scale)
            }
        }
    }
}

guard let best = best, best.0 >= minScore else {
    if let best = best {
        print(String(format: "none\t%.3f", best.0))
    } else {
        print("none")
    }
    exit(0)
}

let fx = best.1 / Double(hay.width)
let fy = best.2 / Double(hay.height)
print(String(format: "%.4f\t%.4f\t%.3f\t%.2f", fx, fy, best.0, best.3))
