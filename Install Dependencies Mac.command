 #!/bin/bash
cd "$(dirname "$0")"
echo "========================================="
echo "   Installing Taiico CRM Dependencies    "
echo "========================================="

echo "[1/2] Installing Backend Dependencies..."
cd backend
pip3 install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "Error installing backend dependencies. Trying with 'pip' instead of 'pip3'..."
    pip install -r requirements.txt
fi
cd ..

echo "[2/2] Installing Frontend Dependencies..."
npm install
npm install recharts

echo "========================================="
echo "        Installation Complete!           "
echo "========================================="
echo "You can now run 'Start CRM Mac.command'"
read -p "Press any key to close..."
