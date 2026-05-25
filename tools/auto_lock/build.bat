@echo off
chcp 65001 > nul
echo 正在构建 auto_lock.exe ...

pyinstaller ^
    --onefile ^
    --windowed ^
    --name auto_lock ^
    --distpath ..\..\EXE ^
    --workpath build ^
    --specpath build ^
    auto_lock.py

if %errorlevel% == 0 (
    echo.
    echo 构建成功！输出：..\..\EXE\auto_lock.exe
) else (
    echo.
    echo 构建失败，请检查错误信息。
)
pause
