#!/bin/bash
cd "$(dirname "$0")"

echo "Starting Taiico CRM..."

# Open Backend in new Terminal window
osascript -e 'tell app "Terminal" to do script "cd \"'$(pwd)'/backend\" && python3 main.py"'

# Open Frontend in new Terminal window
osascript -e 'tell app "Terminal" to do script "cd \"'$(pwd)'\" && npm run dev"'

echo "Waiting for services to start..."
sleep 5

# Open Browser
open http://localhost:3000
