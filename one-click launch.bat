@echo off
:: ---------------------------------------------------------
:: 核心: 强制切换路径 + 修复中文乱码
:: ---------------------------------------------------------
cd /d "%~dp0"
chcp 65001 >nul
title 家校协同系统 - 强力修复版
color 0f
cls

echo =======================================================
echo          正在启动系统 (强力安装模式)...
echo =======================================================
echo.

:: ---------------------------------------------------------
:: 1. 检测 Python
:: ---------------------------------------------------------
echo [1/5] 检测 Python...
python --version >nul 2>&1
if %errorlevel% neq 0 goto ERROR_NO_PYTHON
echo [OK] Python 已就绪。
echo.

:: ---------------------------------------------------------
:: 2. 检测文件
:: ---------------------------------------------------------
echo [2/5] 检测文件完整性...
if not exist config_loader.py goto ERROR_NO_FILE
if not exist app.py goto ERROR_NO_FILE
echo [OK] 文件完整。
echo.

:: ---------------------------------------------------------
:: 3. 强力安装依赖 (核心修改部分)
:: ---------------------------------------------------------
echo [3/5] 正在安装依赖库...
echo 正在尝试方案 A (阿里云高速镜像)...

:: 尝试 A: 阿里云源 + 信任主机 (解决 SSL 问题)
python -m pip install flask flask-cors pyodbc -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com

if %errorlevel% equ 0 goto LIB_SUCCESS

echo.
echo [警告] 方案 A 失败，正在尝试方案 B (官方源)...
echo 这可能需要一点时间，请耐心等待...

:: 尝试 B: 官方源 (慢但稳)
python -m pip install flask flask-cors pyodbc

if %errorlevel% neq 0 goto ERROR_PIP_FAIL

:LIB_SUCCESS
echo [OK] 依赖库安装成功！
echo.

:: ---------------------------------------------------------
:: 4. 锁定路径
:: ---------------------------------------------------------
echo [4/5] 正在配置数据库...
python config_loader.py
if %errorlevel% neq 0 goto ERROR_CONFIG
echo [OK] 配置完成。
echo.

:: ---------------------------------------------------------
:: 5. 启动
:: ---------------------------------------------------------
echo [5/5] 正在启动...
echo.
echo =======================================================
echo    启动成功!
echo    请勿关闭此窗口。
echo =======================================================

timeout /t 3 /nobreak >nul
start "" "index.html"
python app.py
goto END

:: =========================================================
:: 错误处理区
:: =========================================================

:ERROR_NO_PYTHON
color 4f
echo.
echo [错误] 未检测到 Python。
echo 请重新安装 Python 并勾选 "Add to PATH"。
pause
exit

:ERROR_NO_FILE
color 4f
echo.
echo [错误] 文件缺失 (app.py 或 config_loader.py)。
pause
exit

:ERROR_PIP_FAIL
color 4f
echo.
echo =======================================================
echo [严重错误] 无法安装依赖库 (Flask/pyodbc)。
echo =======================================================
echo 可能原因：
echo 1. 你的网络可能有防火墙限制。
echo 2. Python 安装不完整。
echo.
echo 建议解决方法：
echo 请尝试连接手机热点，然后重新运行本程序。
echo =======================================================
pause
exit

:ERROR_CONFIG
color 4f
echo.
echo [错误] 数据库配置失败。请检查 Access 文件是否存在。
pause
exit

:END
pause