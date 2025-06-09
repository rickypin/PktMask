@echo off
:: PktMask 自动化测试脚本 (Windows版本)
:: 用于打包发布前的完整测试验证

setlocal enabledelayedexpansion

:: 设置颜色代码
set "RED=[91m"
set "GREEN=[92m"
set "YELLOW=[93m"
set "BLUE=[94m"
set "NC=[0m"

:: 显示帮助信息
:show_help
echo PktMask 自动化测试脚本 (Windows)
echo.
echo 使用方法:
echo   run_tests.bat [选项]
echo.
echo 选项:
echo   /h, /help          显示此帮助信息
echo   /q, /quick         快速测试(跳过性能测试)
echo   /u, /unit          仅运行单元测试
echo   /i, /integration   仅运行集成测试
echo   /p, /performance   仅运行性能测试
echo   /c, /clean         清理测试报告目录
echo   /o, /output DIR    指定输出目录(默认: test_reports)
echo.
echo 示例:
echo   run_tests.bat              # 运行所有测试
echo   run_tests.bat /quick       # 快速测试
echo   run_tests.bat /unit        # 仅单元测试
echo   run_tests.bat /clean       # 清理报告目录
goto :eof

:: 打印消息函数
:print_message
echo %BLUE%[INFO]%NC% %~1
goto :eof

:print_success
echo %GREEN%[SUCCESS]%NC% %~1
goto :eof

:print_warning
echo %YELLOW%[WARNING]%NC% %~1
goto :eof

:print_error
echo %RED%[ERROR]%NC% %~1
goto :eof

:: 检查Python环境
:check_python_env
call :print_message "检查Python环境..."

python --version >nul 2>&1
if errorlevel 1 (
    call :print_error "未找到 python，请安装Python 3.8+"
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set python_version=%%i
call :print_success "Python版本: !python_version!"

if defined VIRTUAL_ENV (
    call :print_success "使用虚拟环境: %VIRTUAL_ENV%"
) else (
    call :print_warning "未检测到虚拟环境，建议使用虚拟环境"
)
goto :eof

:: 检查依赖
:check_dependencies
call :print_message "检查测试依赖..."

python -c "import pytest" 2>nul
if errorlevel 1 (
    call :print_warning "pytest未安装，正在安装测试依赖..."
    pip install -e ".[dev]"
    if errorlevel 1 (
        call :print_error "依赖安装失败"
        exit /b 1
    )
)

call :print_success "依赖检查完成"
goto :eof

:: 清理报告目录
:clean_reports
set "output_dir=%~1"
if "%output_dir%"=="" set "output_dir=test_reports"

if exist "%output_dir%" (
    call :print_message "清理报告目录: %output_dir%"
    rmdir /s /q "%output_dir%"
    call :print_success "报告目录已清理"
) else (
    call :print_message "报告目录不存在，无需清理"
)
goto :eof

:: 运行测试
:run_tests
set "test_args=%~1"
set "output_dir=%~2"
if "%output_dir%"=="" set "output_dir=test_reports"

call :print_message "开始运行 PktMask 测试套件..."
call :print_message "参数: %test_args%"
call :print_message "输出目录: %output_dir%"

:: 创建输出目录
if not exist "%output_dir%" mkdir "%output_dir%"

:: 运行测试套件
python test_suite.py %test_args% --output "%output_dir%"
if errorlevel 1 (
    call :print_error "测试套件执行失败"
    exit /b 1
)

call :print_success "测试套件执行完成"

:: 查找生成的报告文件
for %%f in ("%output_dir%\test_summary_*.html") do (
    call :print_success "HTML报告: %%f"
    :: 在Windows上自动打开报告
    start "" "%%f"
)

for %%f in ("%output_dir%\test_summary_*.json") do (
    call :print_success "JSON报告: %%f"
)

goto :eof

:: 主函数
:main
set "test_args="
set "output_dir=test_reports"
set "clean_only=false"
set "skip_deps=false"

echo 🧪 PktMask 自动化测试脚本
echo ================================

:: 解析命令行参数
:parse_args
if "%~1"=="" goto :end_parse

if /i "%~1"=="/h" goto :help_exit
if /i "%~1"=="/help" goto :help_exit
if /i "%~1"=="/q" (
    set "test_args=%test_args% --quick"
    shift /1
    goto :parse_args
)
if /i "%~1"=="/quick" (
    set "test_args=%test_args% --quick"
    shift /1
    goto :parse_args
)
if /i "%~1"=="/u" (
    set "test_args=%test_args% --unit"
    shift /1
    goto :parse_args
)
if /i "%~1"=="/unit" (
    set "test_args=%test_args% --unit"
    shift /1
    goto :parse_args
)
if /i "%~1"=="/i" (
    set "test_args=%test_args% --integration"
    shift /1
    goto :parse_args
)
if /i "%~1"=="/integration" (
    set "test_args=%test_args% --integration"
    shift /1
    goto :parse_args
)
if /i "%~1"=="/p" (
    set "test_args=%test_args% --performance"
    shift /1
    goto :parse_args
)
if /i "%~1"=="/performance" (
    set "test_args=%test_args% --performance"
    shift /1
    goto :parse_args
)
if /i "%~1"=="/c" (
    set "clean_only=true"
    shift /1
    goto :parse_args
)
if /i "%~1"=="/clean" (
    set "clean_only=true"
    shift /1
    goto :parse_args
)
if /i "%~1"=="/o" (
    set "output_dir=%~2"
    shift /1
    shift /1
    goto :parse_args
)
if /i "%~1"=="/output" (
    set "output_dir=%~2"
    shift /1
    shift /1
    goto :parse_args
)

call :print_error "未知选项: %~1"
goto :show_help
exit /b 1

:help_exit
call :show_help
exit /b 0

:end_parse

:: 如果只是清理，执行清理后退出
if "%clean_only%"=="true" (
    call :clean_reports "%output_dir%"
    exit /b 0
)

:: 检查环境
call :check_python_env
if errorlevel 1 exit /b 1

if "%skip_deps%" neq "true" (
    call :check_dependencies
    if errorlevel 1 exit /b 1
)

:: 运行测试
call :run_tests "%test_args%" "%output_dir%"
if errorlevel 1 (
    echo.
    call :print_error "❌ 测试失败！"
    exit /b 1
) else (
    echo.
    call :print_success "🎉 测试完成！"
    exit /b 0
)

:: 执行主函数
call :main %* 