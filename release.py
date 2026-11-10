"""
ThinkAi PyPI发布脚本

发布前依次执行: 凭据检查 → 版本一致性 → 工具检查 → 全量测试 →
清理构建目录 → 构建 → twine check → 上传。任一步失败立即终止。

用法:
    python release.py --test         # 发布到TestPyPI
    python release.py                # 发布到PyPI
    python release.py --yes          # 跳过交互确认(CI)
    python release.py --skip-tests   # 已在别处跑过测试时使用

凭据规范:
    Token只允许放在用户主目录 ~/.pypirc 或环境变量,严禁放项目目录。
    正式发布: PYPI_API_TOKEN 或 ~/.pypirc 的 [pypi] 段
    测试发布: TEST_PYPI_API_TOKEN (TestPyPI需独立Token)
    Token通过子进程环境变量传递,不出现在命令行参数中。
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CREDENTIAL_NAMES = (".pypirc", ".env", "本地资料.txt")


def run(cmd, env=None):
    """在项目根目录执行命令"""
    return subprocess.run(
        cmd, cwd=str(ROOT), env=env, text=True, capture_output=True
    )


def check_no_credentials():
    """禁止凭据文件进入版本库或留在项目工作区"""
    tracked = run(["git", "ls-files"]).stdout.splitlines()
    # 按文件名精确匹配,避免把 .env.example 之类的示例文件误判为凭据
    bad = [
        p for p in tracked
        if Path(p).name in CREDENTIAL_NAMES or p.endswith((".pem", ".key"))
    ]
    if bad:
        print("✗ 以下凭据文件已被git跟踪,禁止发布:")
        for p in bad:
            print("   ", p)
        print("  处理: git rm --cached <文件> 后重新提交")
        sys.exit(1)

    if (ROOT / ".pypirc").exists():
        print("✗ 项目目录存在 .pypirc,请先移至用户主目录 ~/.pypirc")
        sys.exit(1)

    print("✓ 凭据检查通过(项目目录与索引均无凭据)")


def check_version_consistency():
    """版本号四处一致,避免版本漂移"""
    content = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
    if not match:
        print("✗ 无法从 pyproject.toml 解析版本号")
        sys.exit(1)
    version = match.group(1)

    checks = {
        "thinkai/__init__.py": f'__version__ = "{version}"',
        "tests/test_thinkai.py": f'== "{version}"',
    }
    for rel, needle in checks.items():
        text = (ROOT / rel).read_text(encoding="utf-8")
        if needle not in text:
            print(f"✗ {rel} 的版本与 pyproject.toml({version}) 不一致")
            sys.exit(1)
    for rel in ("README.md", "QUICKSTART.md"):
        head = "\n".join((ROOT / rel).read_text(encoding="utf-8").splitlines()[:8])
        if f"v{version}" not in head:
            print(f"✗ {rel} 头部版本与 {version} 不一致")
            sys.exit(1)
    print(f"✓ 版本一致性通过({version})")
    return version


def check_tools():
    for tool in ("build", "twine"):
        result = run([sys.executable, "-m", tool, "--version"])
        if result.returncode != 0:
            print(f"✗ {tool} 未安装,请先执行: pip install {tool}")
            sys.exit(1)
    print("✓ 构建工具就绪")


def run_tests():
    result = run([sys.executable, "-m", "pytest", "-q"])
    print("\n".join(result.stdout.splitlines()[-8:]))
    if result.returncode != 0:
        print("✗ 测试未全绿,禁止发布")
        sys.exit(1)
    print("✓ 全量测试通过")


def clean(version):
    """清理构建临时目录;dist中旧版本产物归档,避免被误传"""
    for name in ("build", "__pycache__"):
        path = ROOT / name
        if path.is_dir():
            shutil.rmtree(path)

    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    archive = ROOT / ".release-archive"
    moved = 0
    for path in list(dist.glob("*")):
        if path.is_file() and version not in path.name:
            archive.mkdir(exist_ok=True)
            shutil.move(str(path), str(archive / path.name))
            moved += 1
    print(f"✓ 构建目录已清理(旧产物归档{moved}个到 .release-archive/)")


def build():
    result = run([sys.executable, "-m", "build"])
    if result.returncode != 0:
        print("✗ 构建失败:")
        print(result.stderr[-2000:])
        sys.exit(1)
    print("✓ 构建成功")


def twine_check(version):
    """只校验本次版本的产物,避免旧版本文件混入"""
    files = sorted(
        str(p) for p in (ROOT / "dist").glob(f"*{version}*") if p.is_file()
    )
    if len(files) < 2:
        print(f"✗ 构建产物不完整(期望wheel+sdist): {files}")
        sys.exit(1)
    result = run([sys.executable, "-m", "twine", "check", *files])
    if result.returncode != 0:
        print("✗ twine check 未通过:")
        print(result.stdout + result.stderr)
        sys.exit(1)
    print(f"✓ twine check 通过({len(files)}个产物)")
    return files


def upload(files, test=False):
    """上传;Token经环境变量传给子进程,不出现在命令行"""
    env = os.environ.copy()
    cmd = [sys.executable, "-m", "twine", "upload"]

    if test:
        token = os.getenv("TEST_PYPI_API_TOKEN")
        if not token:
            print("✗ 测试发布需要环境变量 TEST_PYPI_API_TOKEN")
            sys.exit(1)
        env["TWINE_USERNAME"] = "__token__"
        env["TWINE_PASSWORD"] = token
        cmd.extend(["--repository-url", "https://test.pypi.org/legacy/"])
        print("上传到TestPyPI(测试)...")
    else:
        token = os.getenv("PYPI_API_TOKEN")
        if token:
            env["TWINE_USERNAME"] = "__token__"
            env["TWINE_PASSWORD"] = token
        # 未设置环境变量时,twine自动读取 ~/.pypirc 的 [pypi] 段
        print("上传到PyPI(正式)...")

    cmd.extend(files)
    result = subprocess.run(
        cmd, cwd=str(ROOT), env=env, text=True, capture_output=True
    )
    if result.returncode != 0:
        print("✗ 上传失败:")
        print(result.stderr[-2000:])
        sys.exit(1)
    print("✓ 上传成功")


def main():
    args = sys.argv[1:]
    test_mode = "--test" in args
    skip_tests = "--skip-tests" in args
    auto_yes = "--yes" in args or "-y" in args

    print("=" * 60)
    print(f"ThinkAi PyPI 发布工具 | {'TestPyPI(测试)' if test_mode else 'PyPI(正式)'}")
    print("=" * 60)

    if not auto_yes:
        confirm = input("\n是否继续?(y/N): ")
        if confirm.lower() != "y":
            print("取消发布")
            return

    check_no_credentials()
    version = check_version_consistency()
    check_tools()
    if not skip_tests:
        run_tests()
    clean(version)
    build()
    files = twine_check(version)
    upload(files, test=test_mode)

    print("\n" + "=" * 60)
    print("发布完成!")
    print("=" * 60)
    if test_mode:
        print("测试安装: pip install --index-url https://test.pypi.org/simple/ thinkai-framework")
    else:
        print("安装: pip install thinkai-framework --upgrade")
    print("注意: 版本号一经上传不可复用,下次发布需先升版本。")


if __name__ == "__main__":
    main()
