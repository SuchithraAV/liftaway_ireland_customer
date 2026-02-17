@echo off
REM Build, Tag, and Push Docker Image for Customer Backend
REM User ID: vk141

SET IMAGE_NAME=breakdown-customer-backend
SET USER_ID=vk141
SET VERSION=latest

echo ========================================
echo Building Docker Image...
echo ========================================
docker build -t %IMAGE_NAME%:%VERSION% .

if %ERRORLEVEL% NEQ 0 (
    echo Build failed!
    exit /b 1
)

echo.
echo ========================================
echo Tagging Image with User ID: %USER_ID%
echo ========================================
docker tag %IMAGE_NAME%:%VERSION% %USER_ID%/%IMAGE_NAME%:%VERSION%

echo.
echo ========================================
echo Pushing Image to Registry...
echo ========================================
docker push %USER_ID%/%IMAGE_NAME%:%VERSION%

if %ERRORLEVEL% NEQ 0 (
    echo Push failed! Make sure you're logged in: docker login
    exit /b 1
)

echo.
echo ========================================
echo Success! Image pushed as:
echo %USER_ID%/%IMAGE_NAME%:%VERSION%
echo ========================================
