#!/bin/bash
set -euo pipefail
repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
worker_dir="$repo_root/.runtime/mesa-ocr"
mkdir -p "$worker_dir"
/usr/bin/swiftc -O "$repo_root/backend/ocr/recognize.swift" -o "$worker_dir/recognize.next"
chmod 700 "$worker_dir/recognize.next"
mv "$worker_dir/recognize.next" "$worker_dir/recognize"
