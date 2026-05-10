"""
ThinkAi PyPI发布脚本

使用方法:
1. 更新版本号(在pyproject.toml中)
2. 运行: python release.py
3. 按照提示完成发布

发布前准备:
- 安装工具: pip install build twine
- 注册PyPI账号: https://pypi.org/account/register/
- 配置API Token(推荐)或用户名密码

发布到TestPyPI(测试):
python release.py --test

发布到PyPI(正式):
python release.py
"""
import subprocess
import sys
import os
import shutil
from pathlib import Path


def check_tools():
    """检查必要工具"""
    tools = ["build", "twine"]
    for tool in tools:
        try:
            subprocess.run(
                [sys.executable, "-m", tool, "--version"],
                capture_output=True,
                check=True,
            )
            print(f"✓ {tool} 已安装")
        except subprocess.CalledProcessError:
            print(f"✗ {tool} 未安装")
            print(f"  安装命令: pip install {tool}")
            sys.exit(1)


def clean():
    """清理旧的构建文件"""
    print("\n清理构建文件...")
    dirs_to_clean = ["dist", "build", "*.egg-info", "__pycache__"]
    
    for pattern in dirs_to_clean:
        for path in Path(".").glob(pattern):
            if path.is_dir():
                shutil.rmtree(path)
                print(f"  已删除: {path}")
            else:
                path.unlink()
                print(f"  已删除: {path}")


def build():
    """构建包"""
    print("\n构建包...")
    result = subprocess.run(
        [sys.executable, "-m", "build"],
        capture_output=True,
        text=True,
    )
    
    if result.returncode != 0:
        print("✗ 构建失败:")
        print(result.stderr)
        sys.exit(1)
    
    print("✓ 构建成功")
    
    # 显示构建的文件
    print("\n构建的文件:")
    for path in Path("dist").glob("*"):
        size = path.stat().st_size / 1024
        print(f"  {path.name} ({size:.1f} KB)")


def upload(test=False):
    """上传到PyPI"""
    if test:
        print("\n上传到TestPyPI(测试)...")
        repository = "testpypi"
    else:
        print("\n上传到PyPI(正式)...")
        repository = "pypi"
    
    # 检查是否有API token
    api_token = os.getenv("PYPI_API_TOKEN")
    
    cmd = [
        sys.executable, "-m", "twine", "upload",
        "--repository", repository,
        "dist/*",
    ]
    
    if api_token:
        cmd.extend(["-u", "__token__", "-p", api_token])
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print("✗ 上传失败:")
        print(result.stderr)
        sys.exit(1)
    
    print("✓ 上传成功")


def main():
    """主函数"""
    test_mode = "--test" in sys.argv
    
    print("=" * 60)
    print("ThinkAi PyPI 发布工具")
    print("=" * 60)
    
    if test_mode:
        print("模式: TestPyPI(测试)")
    else:
        print("模式: PyPI(正式)")
    
    # 确认
    confirm = input("\n是否继续?(y/N): ")
    if confirm.lower() != "y":
        print("取消发布")
        return
    
    # 执行发布流程
    check_tools()
    clean()
    build()
    upload(test=test_mode)
    
    print("\n" + "=" * 60)
    print("发布完成!")
    print("=" * 60)
    
    if test_mode:
        print("\n测试安装命令:")
        print("  pip install --index-url https://test.pypi.org/simple/ thinkai")
    else:
        print("\n安装命令:")
        print("  pip install thinkai")
    
    print("\n注意:")
    print("  1. 发布后可能需要几分钟才能在PyPI上显示")
    print("  2. 建议先在TestPyPI测试,确认无误后再发布到PyPI")
    print("  3. 更新版本号后才能再次发布")


if __name__ == "__main__":
    main()
