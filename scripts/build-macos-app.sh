#!/usr/bin/env bash
# ==============================================================================
# TAIICO CRM macOS App Builder
# ==============================================================================
# This script compiles the AppleScript launcher wrapper into a macOS Application
# bundle (TAIICO CRM.app), places it in the dist/ folder, and generates/applies
# the custom icon using the company logo if present.
# ==============================================================================

set -euo pipefail

# Add common path locations
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

# Resolve repo root
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "=========================================================================="
echo "Building TAIICO CRM macOS App Bundle"
echo "=========================================================================="

# 1. Prepare output folder
mkdir -p dist
rm -rf "dist/TAIICO CRM.app"

# 2. Write AppleScript launcher to a temp file
APPLESCRIPT_SOURCE="dist/launcher.applescript"
cat << 'EOF' > "$APPLESCRIPT_SOURCE"
set appPath to POSIX path of (path to me)

try
	do shell script "bash -c '
		APP_DIR=\"" & appPath & "\"
		
		# Method 1: Check relative to app bundle location (if running inside dist/ folder of the repo)
		REPO_ROOT=$(cd \"$APP_DIR/../..\" && pwd)
		
		if [ ! -f \"$REPO_ROOT/scripts/start-crm.sh\" ]; then
			# Method 1.5: Check if running from Google Drive root directory (parent of repo)
			REPO_ROOT_TRY=$(cd \"$APP_DIR/../taiico-crm\" && pwd 2>/dev/null || true)
			if [ -f \"$REPO_ROOT_TRY/scripts/start-crm.sh\" ]; then
				REPO_ROOT=\"$REPO_ROOT_TRY\"
			fi
		fi
		
		if [ ! -f \"$REPO_ROOT/scripts/start-crm.sh\" ]; then
			# Method 2: Search in user Google Drive CloudStorage folders (if running from /Applications)
			FOUND_REPO=\"\"
			CLOUD_STORAGE_DIR=\"$HOME/Library/CloudStorage\"
			for dir in \"$CLOUD_STORAGE_DIR\"/GoogleDrive-*/\"Shared drives/Administrativos/2025 - Antigravity CRM/taiico-crm\"; do
				if [ -d \"$dir\" ]; then
					FOUND_REPO=\"$dir\"
					break
				fi
			done
			
			if [ -n \"$FOUND_REPO\" ]; then
				REPO_ROOT=\"$FOUND_REPO\"
			else
				echo \"Error: Could not locate the TAIICO CRM repository directory.\" >&2
				echo \"Please verify the repository is placed in: Google Drive/Shared drives/Administrativos/2025 - Antigravity CRM/taiico-crm\" >&2
				exit 1
			fi
		fi
		
		# Execute the startup script in background
		bash \"$REPO_ROOT/scripts/start-crm.sh\"
	'"
on error errMsg number errNum
	display dialog "Error starting TAIICO CRM:\n\n" & errMsg & "\n\nFor more details, please check the log file:\n~/Library/Logs/TAIICO CRM/launcher.log" buttons {"OK"} default button "OK" with icon stop
end try
EOF

# 3. Compile the AppleScript source into a macOS application bundle (.app)
echo "Compiling AppleScript launcher..."
osacompile -o "dist/TAIICO CRM.app" "$APPLESCRIPT_SOURCE"
rm "$APPLESCRIPT_SOURCE"
echo "Application compiled: dist/TAIICO CRM.app"

# 4. Generate custom application icon from logo if available
LOGO_PNG="$REPO_ROOT/../Logo Taiico.png"
if [ -f "$LOGO_PNG" ]; then
    echo "Found logo at $LOGO_PNG. Generating custom iconset..."
    ICONSET_DIR="dist/icon.iconset"
    mkdir -p "$ICONSET_DIR"
    
    # Generate standard macOS icon sizes
    sips -z 16 16     "$LOGO_PNG" --out "$ICONSET_DIR/icon_16x16.png" &>/dev/null
    sips -z 32 32     "$LOGO_PNG" --out "$ICONSET_DIR/icon_16x16@2x.png" &>/dev/null
    sips -z 32 32     "$LOGO_PNG" --out "$ICONSET_DIR/icon_32x32.png" &>/dev/null
    sips -z 64 64     "$LOGO_PNG" --out "$ICONSET_DIR/icon_32x32@2x.png" &>/dev/null
    sips -z 128 128   "$LOGO_PNG" --out "$ICONSET_DIR/icon_128x128.png" &>/dev/null
    sips -z 256 256   "$LOGO_PNG" --out "$ICONSET_DIR/icon_128x128@2x.png" &>/dev/null
    sips -z 256 256   "$LOGO_PNG" --out "$ICONSET_DIR/icon_256x256.png" &>/dev/null
    sips -z 512 512   "$LOGO_PNG" --out "$ICONSET_DIR/icon_256x256@2x.png" &>/dev/null
    sips -z 512 512   "$LOGO_PNG" --out "$ICONSET_DIR/icon_512x512.png" &>/dev/null
    sips -z 1024 1024 "$LOGO_PNG" --out "$ICONSET_DIR/icon_512x512@2x.png" &>/dev/null
    
    # Convert iconset folder to .icns format
    iconutil -c icns "$ICONSET_DIR" -o "dist/applet.icns"
    rm -rf "$ICONSET_DIR"
    
    # Copy generated icon into the app bundle resources
    cp "dist/applet.icns" "dist/TAIICO CRM.app/Contents/Resources/applet.icns"
    rm "dist/applet.icns"
    
    # Refresh Finder icon cache for the newly compiled bundle
    touch "dist/TAIICO CRM.app"
    echo "Custom application icon generated and applied successfully."
else
    echo "Warning: Logo file not found at $LOGO_PNG. Using default system icon instead."
fi

# 5. Copy the app to the Google Drive root folder (workspace root)
echo "Copying TAIICO CRM.app to Google Drive root folder..."
rm -rf "$REPO_ROOT/../TAIICO CRM.app"
cp -R "dist/TAIICO CRM.app" "$REPO_ROOT/../TAIICO CRM.app"
touch "$REPO_ROOT/../TAIICO CRM.app"

echo "=========================================================================="
echo "TAIICO CRM App Built Successfully at: $REPO_ROOT/dist/TAIICO CRM.app"
echo "and copied to Google Drive root folder at: $REPO_ROOT/../TAIICO CRM.app"
echo "=========================================================================="
