@echo off
chcp 65001 >nul
echo ============================================
echo    TRRCMS Server Installation
echo ============================================
echo.

echo Checking Docker...
docker --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker is not installed.
    echo Please install Docker Desktop first: https://www.docker.com/products/docker-desktop/
    pause
    exit /b 1
)

echo Loading database image...
docker load -i images\trrcms-db.tar
if errorlevel 1 (
    echo ERROR: Failed to load database image.
    pause
    exit /b 1
)

echo Loading API image...
docker load -i images\trrcms-api.tar
if errorlevel 1 (
    echo ERROR: Failed to load API image.
    pause
    exit /b 1
)

echo Loading tile server image...
docker load -i images\tileserver.tar
if errorlevel 1 (
    echo ERROR: Failed to load tile server image.
    pause
    exit /b 1
)

echo.
echo All images loaded. Starting services...
docker-compose up -d
if errorlevel 1 (
    echo ERROR: Failed to start services.
    pause
    exit /b 1
)

echo.
echo ============================================
echo    Installation complete!
echo ============================================
echo.
echo Services running:
echo   API:         http://localhost:8080
echo   Database:    localhost:5432
echo   Map Server:  http://localhost:5000
echo.
echo You can now run TRRCMS.exe
echo.
pause
