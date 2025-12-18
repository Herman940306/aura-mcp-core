@echo off
REM Aura IA Logo Animation Generator
REM Requires Blender 3.x+ to be installed and in PATH
REM
REM Usage: Just run this script from the project root
REM Output: dashboard/assets/auralia_orbit.mp4 and auralia_scene.glb

echo ============================================================
echo  Aura IA Gyroscope Logo Animation Generator
echo ============================================================
echo.

REM Check if Blender is available
where blender >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Blender not found in PATH
    echo Please install Blender 3.x+ and add it to your PATH
    echo Download from: https://www.blender.org/download/
    pause
    exit /b 1
)

echo Found Blender:
blender --version | findstr "Blender"
echo.

echo Starting render... This may take several minutes.
echo.

blender --background --factory-startup --python scripts\auralia_gyro_anim.py

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ============================================================
    echo  SUCCESS! Files generated:
    echo  - dashboard\assets\auralia_orbit.mp4 (video)
    echo  - dashboard\assets\auralia_scene.glb (3D model)
    echo ============================================================
) else (
    echo.
    echo ERROR: Render failed. Check the output above for details.
)

pause
