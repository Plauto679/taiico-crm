#!/usr/bin/env bash
set -euo pipefail

export PATH="/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

APP_NAME="TAIICO CRM"
APP_BUNDLE="dist/$APP_NAME.app"
APP_EXECUTABLE="taiico-crm-launcher"
LOG_HINT="~/Library/Logs/$APP_NAME/launcher.log"
PARENT_APP="$REPO_ROOT/../$APP_NAME.app"

echo "Building $APP_NAME macOS app..."
mkdir -p dist
rm -rf "$APP_BUNDLE"
rm -rf "dist/icon.iconset" "dist/applet.icns" "dist/launcher.applescript"
mkdir -p "$APP_BUNDLE/Contents/MacOS" "$APP_BUNDLE/Contents/Resources"

cat > "$APP_BUNDLE/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>$APP_NAME</string>
    <key>CFBundleDisplayName</key>
    <string>$APP_NAME</string>
    <key>CFBundleIdentifier</key>
    <string>com.taiico.crm.launcher</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleExecutable</key>
    <string>$APP_EXECUTABLE</string>
    <key>CFBundleIconFile</key>
    <string>applet</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.15</string>
</dict>
</plist>
EOF

cat > "$APP_BUNDLE/Contents/MacOS/$APP_EXECUTABLE" <<EOF
#!/usr/bin/env bash
set -u

REPO_ROOT="$REPO_ROOT"
LOG_HINT="$LOG_HINT"

/bin/bash "\$REPO_ROOT/scripts/start-crm.sh"
status=\$?
if [ "\$status" -ne 0 ]; then
    /usr/bin/osascript -l JavaScript -e "const app = Application.currentApplication(); app.includeStandardAdditions = true; app.displayDialog('No se pudo iniciar $APP_NAME.\\\\n\\\\nRevisa los logs en:\\\\n' + '\$LOG_HINT', {withTitle: '$APP_NAME', buttons: ['OK'], defaultButton: 'OK'});" >/dev/null 2>&1 || true
    exit "\$status"
fi
EOF

chmod +x "$APP_BUNDLE/Contents/MacOS/$APP_EXECUTABLE"
printf 'APPL????' > "$APP_BUNDLE/Contents/PkgInfo"

LOGO_PNG="$REPO_ROOT/../Logo Taiico.png"
if [ ! -f "$LOGO_PNG" ]; then
    LOGO_PNG="$REPO_ROOT/public/logo.png"
fi

if [ -f "$LOGO_PNG" ]; then
    ICONSET_DIR="dist/icon.iconset"
    mkdir -p "$ICONSET_DIR"
    sips -z 16 16 "$LOGO_PNG" --out "$ICONSET_DIR/icon_16x16.png" >/dev/null
    sips -z 32 32 "$LOGO_PNG" --out "$ICONSET_DIR/icon_16x16@2x.png" >/dev/null
    sips -z 32 32 "$LOGO_PNG" --out "$ICONSET_DIR/icon_32x32.png" >/dev/null
    sips -z 64 64 "$LOGO_PNG" --out "$ICONSET_DIR/icon_32x32@2x.png" >/dev/null
    sips -z 128 128 "$LOGO_PNG" --out "$ICONSET_DIR/icon_128x128.png" >/dev/null
    sips -z 256 256 "$LOGO_PNG" --out "$ICONSET_DIR/icon_128x128@2x.png" >/dev/null
    sips -z 256 256 "$LOGO_PNG" --out "$ICONSET_DIR/icon_256x256.png" >/dev/null
    sips -z 512 512 "$LOGO_PNG" --out "$ICONSET_DIR/icon_256x256@2x.png" >/dev/null
    sips -z 512 512 "$LOGO_PNG" --out "$ICONSET_DIR/icon_512x512.png" >/dev/null
    sips -z 1024 1024 "$LOGO_PNG" --out "$ICONSET_DIR/icon_512x512@2x.png" >/dev/null
    if ! iconutil -c icns "$ICONSET_DIR" -o "$APP_BUNDLE/Contents/Resources/applet.icns"; then
        echo "Warning: could not generate app icon from $LOGO_PNG. Keeping the default app icon."
    fi
    rm -rf "$ICONSET_DIR"
fi

touch "$APP_BUNDLE"
rm -rf "$PARENT_APP"
cp -R "$APP_BUNDLE" "$PARENT_APP"
touch "$PARENT_APP"

echo "Built $APP_BUNDLE"
echo "Copied launcher to $PARENT_APP"
echo "You can copy either app bundle to /Applications or open it from Finder."
