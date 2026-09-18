#!/bin/bash
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="$ROOT/build"
APP="$BUILD/脚本合集.app"
DESKTOP="$HOME/Desktop/脚本合集.app"
OLD_DESKTOP="$HOME/Desktop/iPhone 自动化.app"
ICON_JPG="$ROOT/icons/app-icon.jpg"

rm -rf "$BUILD"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

sed "s|__PROJECT_ROOT__|$ROOT|g" "$ROOT/scripts/launcher.swift" > "$BUILD/launcher.swift"

swiftc -O -o "$APP/Contents/MacOS/ScriptBox" "$BUILD/launcher.swift" -framework Cocoa
chmod +x "$APP/Contents/MacOS/ScriptBox"

if [ -f "$ICON_JPG" ]; then
  ICONSET="$BUILD/AppIcon.iconset"
  mkdir -p "$ICONSET"
  sips -s format png "$ICON_JPG" --out "$BUILD/app-icon.png" >/dev/null
  sips -z 16 16 "$BUILD/app-icon.png" --out "$ICONSET/icon_16x16.png" >/dev/null
  sips -z 32 32 "$BUILD/app-icon.png" --out "$ICONSET/icon_16x16@2x.png" >/dev/null
  sips -z 32 32 "$BUILD/app-icon.png" --out "$ICONSET/icon_32x32.png" >/dev/null
  sips -z 64 64 "$BUILD/app-icon.png" --out "$ICONSET/icon_32x32@2x.png" >/dev/null
  sips -z 128 128 "$BUILD/app-icon.png" --out "$ICONSET/icon_128x128.png" >/dev/null
  sips -z 256 256 "$BUILD/app-icon.png" --out "$ICONSET/icon_128x128@2x.png" >/dev/null
  sips -z 256 256 "$BUILD/app-icon.png" --out "$ICONSET/icon_256x256.png" >/dev/null
  sips -z 512 512 "$BUILD/app-icon.png" --out "$ICONSET/icon_256x256@2x.png" >/dev/null
  sips -z 512 512 "$BUILD/app-icon.png" --out "$ICONSET/icon_512x512.png" >/dev/null
  sips -z 1024 1024 "$BUILD/app-icon.png" --out "$ICONSET/icon_512x512@2x.png" >/dev/null
  iconutil -c icns -o "$APP/Contents/Resources/AppIcon.icns" "$ICONSET"
fi

cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>
  <string>脚本合集</string>
  <key>CFBundleDisplayName</key>
  <string>脚本合集</string>
  <key>CFBundleIdentifier</key>
  <string>local.game-plugin.scriptbox</string>
  <key>CFBundleVersion</key>
  <string>1.0</string>
  <key>CFBundleShortVersionString</key>
  <string>1.0</string>
  <key>CFBundleExecutable</key>
  <string>ScriptBox</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleIconFile</key>
  <string>AppIcon</string>
  <key>LSMinimumSystemVersion</key>
  <string>14.0</string>
  <key>NSPrincipalClass</key>
  <string>NSApplication</string>
  <key>LSBackgroundOnly</key>
  <false/>
  <key>NSHighResolutionCapable</key>
  <true/>
</dict>
</plist>
PLIST

rm -rf "$DESKTOP" "$OLD_DESKTOP"
cp -R "$APP" "$DESKTOP"
xattr -cr "$DESKTOP" 2>/dev/null || true
xattr -cr "$APP" 2>/dev/null || true

echo "已放到桌面：$DESKTOP"
echo "项目里也有一份：$APP"
