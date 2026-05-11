@echo off
chcp 65001 >nul
echo ========================================
echo    ThinkAi FastAPI 服务启动脚本
echo ========================================
echo.

REM 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到Python,请先安装Python!
    pause
    exit /b 1
)

echo [1/3] 检查Python环境...
python --version
echo.

REM 检查并安装依赖
echo [2/3] 检查依赖包...
pip show fastapi >nul 2>&1
if errorlevel 1 (
    echo 正在安装依赖包(首次运行可能需要几分钟)...
    pip install fastapi uvicorn pydantic pydantic-settings httpx pyyaml python-dotenv tenacity
) else (
    echo ✓ 依赖包已安装
)
echo.

REM 启动FastAPI服务
echo [3/3] 启动ThinkAI服务...
echo.
echo 服务地址: http://localhost:8000
echo API文档: http://localhost:8000/docs
echo.
echo 按 Ctrl+C 停止服务
echo.

cd /d "%~dp0"
python -m uvicorn examples.fastapi_demo:app --host 0.0.0.0 --port 8000 --reload

pause
