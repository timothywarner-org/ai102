@echo off

echo.
echo Installing npm packages
echo.
call npm install
if "%errorlevel%" neq "0" (
    echo Failed to install npm packages
    exit /B %errorlevel%
)

echo.
echo Starting server
echo.
start http://127.0.0.1:50505
call npm start
if "%errorlevel%" neq "0" (
    echo Failed to start server
    exit /B %errorlevel%
) 
