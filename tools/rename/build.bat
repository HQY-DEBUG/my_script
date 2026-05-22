@echo off
chcp 65001 >nul
echo ============================================
echo  批量重命名工具 - 打包为 EXE
echo ============================================

cd /d "%~dp0"

echo [1/2] 清理旧构建产物...
if exist "dist\batch_rename" rmdir /s /q "dist\batch_rename"
if exist "build\batch_rename" rmdir /s /q "build\batch_rename"
if exist "batch_rename.spec" del "batch_rename.spec"

echo [2/2] 开始打包...
pyinstaller ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name "批量重命名工具" ^
    --icon NONE ^
    batch_rename.py

echo.
if exist "dist\批量重命名工具.exe" (
    echo ============================================
    echo  打包成功！
    echo  输出路径: %~dp0dist\批量重命名工具.exe
    echo ============================================
) else (
    echo [ERROR] 打包失败，请检查上方错误信息
    exit /b 1
)

pause
