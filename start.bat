@echo off
echo === Lirisense Website Setup ===
echo.
echo Installing dependencies...
py -m pip install -r requirements.txt
echo.
echo Starting server on http://localhost
echo.
echo Default admin: admin / admin
echo.
py app.py
pause
