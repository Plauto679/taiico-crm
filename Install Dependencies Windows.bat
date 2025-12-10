@echo off
echo =========================================
echo    Installing Taiico CRM Dependencies    
echo =========================================

echo [1/2] Installing Backend Dependencies...
cd backend
pip install -r requirements.txt
cd ..

echo [2/2] Installing Frontend Dependencies...
call npm install

echo =========================================
echo         Installation Complete!           
echo =========================================
echo You can now run 'Start CRM Windows.bat'
pause
