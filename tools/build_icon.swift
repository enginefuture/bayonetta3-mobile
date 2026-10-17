// Render the project's own vector mark; no game artwork is used.
import AppKit
import Foundation
let root = URL(fileURLWithPath:CommandLine.arguments[1],isDirectory:true)
guard let vector=NSImage(contentsOf:root.appendingPathComponent("assets/AppIcon.svg")) else {fatalError("Cannot load icon SVG")}
let output=root.appendingPathComponent("work/build/icons",isDirectory:true)
try FileManager.default.createDirectory(at:output,withIntermediateDirectories:true)
let iconset=output.appendingPathComponent("AppIcon.iconset",isDirectory:true)
try FileManager.default.createDirectory(at:iconset,withIntermediateDirectories:true)
for size in [16,32,128,256,512] {
 for scale in [1,2] {
  let n=size*scale
  guard let rep=NSBitmapImageRep(bitmapDataPlanes:nil,pixelsWide:n,pixelsHigh:n,bitsPerSample:8,samplesPerPixel:4,hasAlpha:true,isPlanar:false,colorSpaceName:.deviceRGB,bytesPerRow:0,bitsPerPixel:0) else {fatalError("Bitmap")}
  rep.size=NSSize(width:n,height:n)
  NSGraphicsContext.saveGraphicsState();NSGraphicsContext.current=NSGraphicsContext(bitmapImageRep:rep)
  vector.draw(in:NSRect(x:0,y:0,width:n,height:n),from:.zero,operation:.copy,fraction:1)
  NSGraphicsContext.restoreGraphicsState()
  guard let png=rep.representation(using:.png,properties:[:]) else {fatalError("PNG")}
  try png.write(to:iconset.appendingPathComponent("icon_\(size)x\(size)\(scale==2 ? "@2x" : "").png"))
  if n==1024 {try png.write(to:output.appendingPathComponent("AppIcon.png"))}
 }
}
let task=Process();task.executableURL=URL(fileURLWithPath:"/usr/bin/iconutil");task.arguments=["-c","icns",iconset.path,"-o",output.appendingPathComponent("AppIcon.icns").path];try task.run();task.waitUntilExit();exit(task.terminationStatus)
