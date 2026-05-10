# ThinkAi PyPI发布指南

## 发布前准备

### 1. 安装必要工具

```bash
pip install build twine
```

### 2. 注册PyPI账号

- 正式PyPI: https://pypi.org/account/register/
- 测试PyPI: https://test.pypi.org/account/register/

### 3. 配置API Token(推荐)

1. 登录PyPI账号
2. 进入 Account settings
3. 点击 "Add API token"
4. 复制生成的token
5. 设置环境变量:

```bash
# Windows PowerShell
$env:PYPI_API_TOKEN="pypi-xxxxxxxxxxxxx"

# 或永久添加到用户环境变量
[Environment]::SetEnvironmentVariable("PYPI_API_TOKEN", "pypi-xxxxxxxxxxxxx", "User")
```

## 发布流程

### 方法1: 使用发布脚本(推荐)

```bash
# 测试发布到TestPyPI
python release.py --test

# 正式发布到PyPI
python release.py
```

### 方法2: 手动发布

```bash
# 1. 清理旧文件
Remove-Item -Recurse -Force dist, build, *.egg-info -ErrorAction SilentlyContinue

# 2. 构建包
python -m build

# 3. 上传到TestPyPI(测试)
python -m twine upload --repository testpypi dist/*

# 4. 上传到PyPI(正式)
python -m twine upload dist/*
```

## 版本管理

### 更新版本号

编辑 `pyproject.toml`:

```toml
[project]
version = "0.1.0"  # 修改此字段
```

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
