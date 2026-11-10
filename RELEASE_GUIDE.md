# ThinkAi PyPI发布指南

## 发布前准备

### 1. 安装必要工具

```bash
pip install build twine
```

### 2. 注册PyPI账号

- 正式PyPI: https://pypi.org/account/register/
- 测试PyPI: https://test.pypi.org/account/register/

### 3. 配置 API Token（凭据规范）

**凭据只允许放在用户主目录 `~/.pypirc` 或环境变量，严禁放入项目目录。**
`.gitignore`、`.git/info/exclude` 与 `.githooks/pre-commit` 三层拦截，确保凭据不会被提交。

- 正式 PyPI：`~/.pypirc` 的 `[pypi]` 段，或环境变量 `PYPI_API_TOKEN`
- 测试 PyPI：环境变量 `TEST_PYPI_API_TOKEN`（TestPyPI 与 PyPI 的 Token 不通用）

```powershell
# Windows PowerShell（当前会话）
$env:PYPI_API_TOKEN = "pypi-xxxxxxxxxxxxx"
$env:TEST_PYPI_API_TOKEN = "pypi-xxxxxxxxxxxxx"

# 或写入用户级环境变量（永久）
[Environment]::SetEnvironmentVariable("PYPI_API_TOKEN", "...", "User")
```

`release.py` 通过子进程环境变量传递 Token，**不会**把 Token 拼进命令行参数。

### 4. 启用提交防护（每个克隆执行一次）

```bash
git config core.hooksPath .githooks
```

## 发布流程

`release.py` 依次执行：凭据检查 → 版本四点一致性 → 工具检查 → 全量测试 → 清理 → 构建 → `twine check` → 上传。任一步失败立即终止。

### 方法1: 使用发布脚本(推荐)

```bash
python release.py --test          # 测试发布到 TestPyPI
python release.py                 # 正式发布到 PyPI
python release.py --yes           # 跳过交互确认(CI)
python release.py --skip-tests    # 已在别处跑过测试时使用
```

### 方法2: 手动发布

```bash
# 1. 清理构建临时目录（不要删除 dist 与 *.egg-info，旧产物应自行归档）
Remove-Item -Recurse -Force build -ErrorAction SilentlyContinue

# 2. 先跑全量测试
python -m pytest -q

# 3. 构建包
python -m build

# 4. 校验（务必指定本次版本，避免 dist 中旧版本被一起上传）
python -m twine check dist/*0.8.0*

# 5. 上传到 TestPyPI / PyPI
python -m twine upload --repository-url https://test.pypi.org/legacy/ dist/*0.8.0*
python -m twine upload dist/*0.8.0*
```

## 版本管理

### 更新版本号

除 `pyproject.toml` 外，还必须同步以下位置，否则会出现版本漂移或测试失败：
- `thinkai/__init__.py` 的 `__version__`
- `tests/test_thinkai.py` 中的 `__version__` 断言
- `README.md` / `QUICKSTART.md` 头部版本号与测试数量

编辑 `pyproject.toml`:

```toml
[project]
version = "0.8.0"  # 修改此字段
```

发布前执行 `python -m pytest` 与 `python -m build`，并确认生成的 `PKG-INFO` 版本一致。

### 版本号规范

遵循语义化版本: `MAJOR.MINOR.PATCH`

- MAJOR: 不兼容的API变更
- MINOR: 向后兼容的功能新增
- PATCH: 向后兼容的bug修复

示例:
- 0.1.0 - 初始版本
- 0.1.1 - bug修复
- 0.2.0 - 新增功能
- 1.0.0 - 稳定版本

## 测试安装

### 从TestPyPI安装

```bash
pip install --index-url https://test.pypi.org/simple/ thinkai-framework
```

### 从PyPI安装

```bash
pip install thinkai-framework
```

## 本地开发安装

```bash
# 开发模式安装(可编辑)
pip install -e .

# 安装所有依赖
pip install -e ".[all]"
```

## 从GitHub安装

```bash
pip install git+https://github.com/yourname/thinkai.git
```

## 常见问题

### Q: 发布时提示"File already exists"

A: 版本号已存在,需要更新版本号后重新发布

### Q: 安装后导入失败

A: 检查是否正确安装:
```bash
pip list | findstr thinkai
python -c "import thinkai; print(thinkai.__version__)"
```

### Q: 如何删除已发布的版本?

A: PyPI不允许删除版本,只能发布新版本

## CI/CD自动发布

### GitHub Actions示例

创建 `.github/workflows/publish.yml`:

```yaml
name: Publish to PyPI

on:
  release:
    types: [published]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.10"
      
      - name: Install dependencies
        run: pip install build twine
      
      - name: Build
        run: python -m build
      
      - name: Publish to PyPI
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
        run: python -m twine upload dist/*
```
