# MCP-PM 开发者指南

> **项目**: mcp-pm (Model Context Protocol Package Manager)
> **定位**: "Homebrew for MCP Servers" — 统一的 MCP 服务器包管理器
> **技术栈**: Python 3.11+, Click, Rich, FastAPI+HTMX, httpx, Pydantic, asyncio
> **作者**: Davey Wong <wgwcko@gmail.com>
> **协议**: MIT

---

## 目录

1. [环境要求](#1-环境要求)
2. [本地开发环境搭建](#2-本地开发环境搭建)
3. [运行测试](#3-运行测试)
4. [代码规范](#4-代码规范)
5. [Git 工作流](#5-git-工作流)
6. [模块开发指南](#6-模块开发指南)
7. [添加新 MCP 服务器支持](#7-添加新-mcp-服务器支持)
8. [调试技巧](#8-调试技巧)
9. [构建和发布](#9-构建和发布)
10. [常见问题](#10-常见问题)

---

## 1. 环境要求

### 系统要求

| 项目 | 最低版本 | 推荐版本 |
|------|---------|---------|
| Python | 3.11 | 3.12+ |
| pip | 23.0 | 24.0+ |
| OS | Linux / macOS / Windows | Linux (Ubuntu 22.04+) |
| Git | 2.30 | 2.40+ |

### 推荐安装工具

- **pipx** — 安装和运行 Python 应用的首选工具
- **uv** — 更快的 pip 替代品，开发时推荐
- **just** — 命令运行器（可选，用于便捷命令）
- **pre-commit** — Git hooks 管理

```bash
# 安装 pipx
python3 -m pip install --user pipx
python3 -m pipx ensurepath

# 安装 uv (可选但推荐)
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## 2. 本地开发环境搭建

### 2.1 克隆仓库

```bash
git clone https://github.com/<your-org>/mcp-pm.git
cd mcp-pm
```

### 2.2 创建虚拟环境

```bash
# 使用 venv
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 或使用 uv (更快)
uv venv
source .venv/bin/activate
```

### 2.3 安装依赖

```bash
# 开发模式安装 (推荐)
pip install -e ".[dev]"

# 或使用 uv
uv pip install -e ".[dev]"

# 验证安装
mcp-pm --help
```

### 2.4 安装 pre-commit hooks

```bash
pre-commit install
pre-commit run --all-files  # 验证所有文件
```

### 2.5 环境配置

创建本地开发配置文件:

```yaml
# ~/.config/mcp-pm/config.yaml
registry:
  url: https://registry.mcp-pm.dev  # 或本地 registry
  api_key: "dev-key"

profiles:
  default:
    servers: {}
```

---

## 3. 运行测试

### 3.1 运行全部测试

```bash
pytest
```

### 3.2 运行特定测试

```bash
# 按模块
pytest tests/test_installer.py

# 按测试名称
pytest -k "test_install"

# 带详细输出
pytest -v

# 并行运行
pytest -n auto

# 带覆盖率
pytest --cov=src/mcp_pm --cov-report=term-missing
```

### 3.3 测试结构

```
tests/
  ├── conftest.py              # 共享 fixtures
  ├── test_cli.py              # CLI 命令测试
  ├── test_registry.py         # 注册中心客户端测试
  ├── test_installer.py        # 安装器测试
  ├── test_client.py           # MCP 客户端测试
  ├── test_config.py           # 配置管理测试
  ├── test_server.py           # HTTP 代理测试
  ├── test_sandbox.py          # 沙箱测试
  ├── test_webui.py            # Web UI 测试
  └── fixtures/                # 测试数据
      ├── mock_registry.py
      └── sample_servers/
```

### 3.4 测试要求

- 新功能必须有对应的单元测试
- CLI 命令测试需要 mock 后端模块
- 集成测试应在 CI 中运行
- 测试覆盖率目标: ≥ 80%

---

## 4. 代码规范

### 4.1 格式化与检查

项目使用 **Ruff** 作为 linter 和 formatter，**mypy** 作为静态类型检查器。

```bash
# 代码格式化
ruff format src/mcp_pm tests

# Lint 检查
ruff check src/mcp_pm tests

# 类型检查
mypy src/mcp_pm
```

### 4.2 配置文件

- `pyproject.toml` — 集中管理所有工具配置
- Ruff lint 规则: 基于 `RUF` + 额外规则
- mypy 严格模式

**`pyproject.toml` 关键配置**:

```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "SIM", "RUF"]

[tool.mypy]
strict = true
python_version = "3.11"
```

### 4.3 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 模块 | 小写+下划线 | `installer.py`, `registry.py` |
| 类 | PascalCase | `MCPClient`, `RegistryClient` |
| 函数/方法 | snake_case | `install_package()`, `list_tools()` |
| 变量 | snake_case | `server_name`, `installed_servers` |
| 常量 | UPPER_CASE | `DEFAULT_REGISTRY_URL`, `MAX_RETRIES` |
| 私有 | 前缀 `_` | `_validate_config()`, `_cache` |

### 4.4 类型注解

所有函数必须包含类型注解:

```python
# ✅ 正确
async def install(
    self,
    name: str,
    version: str | None = None,
    force: bool = False,
) -> InstallResult:
    ...

# ❌ 错误
def install(name, version=None):
    ...
```

### 4.5 文档字符串

使用 Google 风格的 docstring:

```python
def search(query: str, limit: int = 20) -> list[PackageInfo]:
    """搜索注册中心中的 MCP 服务器包。

    Args:
        query: 搜索关键词，支持模糊匹配。
        limit: 最大返回数量，范围 1-100，默认 20。

    Returns:
        匹配的包信息列表。

    Raises:
        RegistryError: 注册中心不可用时抛出。
    """
```

---

## 5. Git 工作流

### 5.1 分支策略

采用 **GitHub Flow**:

```
main ──┬── feature/installer-v2 ──→ PR ──→ main
       ├── fix/registry-timeout ──→ PR ──→ main
       └── docs/webui-usage ─────→ PR ──→ main
```

- `main` — 稳定分支，始终可部署
- `feature/*` — 新功能开发
- `fix/*` — Bug 修复
- `docs/*` — 文档更新
- `chore/*` — 杂项（依赖升级、CI 配置等）

### 5.2 Commit 规范

使用 **Conventional Commits** 格式:

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**类型**:

| 类型 | 用途 | 版本影响 |
|------|------|---------|
| `feat` | 新功能 | MINOR |
| `fix` | Bug 修复 | PATCH |
| `docs` | 文档更新 | - |
| `style` | 代码格式 | - |
| `refactor` | 重构 | - |
| `test` | 测试相关 | - |
| `chore` | 杂项 | - |
| `perf` | 性能优化 | PATCH |

**示例**:

```
feat(installer): 添加并行下载支持

为安装器实现并行下载功能，提升大型 MCP 服务器的安装速度。

Closes #42
```

```
fix(client): 修复 stdio 传输模式下的超时处理

当 MCP 服务器启动缓慢时，客户端现在会等待最多 30 秒。
之前默认超时为 5 秒，导致频繁连接失败。

Fixes #18
```

### 5.3 PR 规范

- PR 标题遵循 Conventional Commits
- 描述应包含: 背景、变更内容、测试方法
- 关联 Issue 和 Milestone
- 至少 1 个 reviewer 批准后方可合并
- 合并方式: Squash and Merge

---

## 6. 模块开发指南

### 6.1 添加新命令

在 `cli.py` 中使用 Click 添加新命令:

```python
import click
from rich.console import Console

console = Console()

@click.group()
def cli():
    """MCP Package Manager - Homebrew for MCP Servers"""
    pass

@cli.command()
@click.argument("name")
@click.option("--version", "-v", help="指定版本")
@click.option("--force", is_flag=True, help="强制安装")
def install(name: str, version: str | None, force: bool):
    """安装 MCP 服务器"""
    # 1. 解析参数
    # 2. 调用业务逻辑
    # 3. 输出结果
```

### 6.2 添加注册中心 API

在 `registry.py` 中添加新 API 调用:

```python
from httpx import AsyncClient, HTTPError
from pydantic import TypeAdapter

class RegistryClient:
    def __init__(self, base_url: str, api_key: str | None = None):
        self._client = AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
        )

    async def get_package_stats(self, name: str) -> PackageStats:
        """获取包的下载统计信息。"""
        try:
            response = await self._client.get(f"/packages/{name}/stats")
            response.raise_for_status()
            return PackageStats(**response.json())
        except HTTPError as e:
            raise RegistryError(f"获取统计信息失败: {e}") from e
```

### 6.3 实现新的传输协议

在 `client.py` 中添加新的传输实现:

```python
from abc import ABC, abstractmethod

class Transport(ABC):
    """MCP 传输层抽象"""

    @abstractmethod
    async def send(self, message: dict) -> dict:
        """发送 JSON-RPC 消息并等待响应。"""
        ...

    @abstractmethod
    async def close(self):
        """关闭传输连接。"""
        ...

class StdioTransport(Transport):
    def __init__(self, command: list[str]):
        self._process = None
        self._command = command

    async def send(self, message: dict) -> dict:
        # 通过 stdin/stdout 发送 JSON-RPC
        ...

class HTTPTransport(Transport):
    def __init__(self, url: str):
        self._client = AsyncClient()
        self._url = url

    async def send(self, message: dict) -> dict:
        # 通过 HTTP POST 发送 JSON-RPC
        ...
```

### 6.4 添加新的沙箱策略

在 `sandbox.py` 中注册新的隔离策略:

```python
from abc import ABC, abstractmethod

class SandboxStrategy(ABC):
    """沙箱隔离策略抽象"""

    @abstractmethod
    async def create(
        self, server_name: str, spec: PackageInfo
    ) -> SandboxEnv:
        ...

    @abstractmethod
    async def destroy(self, env: SandboxEnv):
        ...

class DockerSandbox(SandboxStrategy):
    """基于 Docker 容器的隔离"""

    async def create(self, server_name: str, spec: PackageInfo) -> SandboxEnv:
        image = f"mcp-server/{server_name}:{spec.version}"
        # docker pull, docker create
        ...

    async def destroy(self, env: SandboxEnv):
        # docker stop, docker rm
        ...
```

---

## 7. 添加新 MCP 服务器支持

### 7.1 标准接入流程

1. **验证服务器兼容性**

```bash
# 克隆服务器仓库
git clone https://github.com/org/new-mcp-server
cd new-mcp-server

# 本地运行验证
python -m new_mcp_server
# 检查其是否实现 MCP 协议
```

2. **创建包清单**

```yaml
# new-mcp-server.yaml
name: "@org/new-mcp-server"
version: "1.0.0"
description: "A new MCP server that does X"
author: "org"
repository: "https://github.com/org/new-mcp-server"
tools:
  - name: my_tool
    description: "Does something useful"
    input_schema:
      type: object
      properties:
        param1:
          type: string
transport:
  - stdio
```

3. **测试安装**

```bash
mcp-pm install ./new-mcp-server.yaml
mcp-pm run @org/new-mcp-server
```

4. **提交到注册中心**

```bash
mcp-pm publish ./new-mcp-server.yaml
```

### 7.2 服务器清单 Schema

```yaml
name: string           # 必填。完整包名
version: string        # 必填。语义化版本号
description: string    # 必填。简短描述
author: string         # 必填。作者或组织
license: string        # 推荐。开源协议
repository: string     # 推荐。源码仓库
homepage: string       # 可选。项目首页
tags: string[]         # 可选。分类标签
tools:                 # 必填。工具声明列表
  - name: string
    description: string
    input_schema: object
transport: ["stdio"]   # 必填。支持的传输协议
```

---

## 8. 调试技巧

### 8.1 启用调试日志

```bash
# 环境变量方式
MCP_PM_DEBUG=1 mcp-pm install @org/server

# CLI 选项方式
mcp-pm --verbose install @org/server
mcp-pm --debug install @org/server

# 查看详细 API 请求
mcp-pm --log-level DEBUG search calculator
```

### 8.2 使用 Rich Inspector

```python
from rich import inspect

# 在代码中查看任意对象
inspect(registry_client)
inspect(installed_package, methods=True)
```

### 8.3 开发服务器模式

```bash
# 使用本地 MCP 服务器进行测试
mcp-pm run --dev ./my-server.py

# 或指定自定义命令
mcp-pm run --dev --cmd "python -m my_server"
```

### 8.4 常见调试场景

**场景 1: 安装失败**

```bash
# 开启详细日志
mcp-pm --debug install @org/server

# 查看配置状态
mcp-pm doctor

# 手动检查日志
tail -f ~/.local/share/mcp-pm/logs/mcp-pm.log
```

**场景 2: 运行时连接失败**

```bash
# 测试连接
mcp-pm run --test @org/server

# 查看进程状态
ps aux | grep mcp-server

# 检查端口占用
lsof -i :<port>
```

**场景 3: 配置问题**

```bash
# 验证配置文件
mcp-pm config validate

# 查看当前配置
mcp-pm config show

# 重置配置
mcp-pm config reset
```

### 8.5 VS Code 调试配置

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Debug CLI",
      "type": "debugpy",
      "request": "launch",
      "module": "mcp_pm",
      "args": ["install", "@org/server"],
      "console": "integratedTerminal",
      "justMyCode": true
    },
    {
      "name": "Debug Web UI",
      "type": "debugpy",
      "request": "launch",
      "module": "uvicorn",
      "args": [
        "mcp_pm.webui:app",
        "--reload",
        "--port", "8000"
      ],
      "console": "integratedTerminal"
    }
  ]
}
```

---

## 9. 构建和发布

### 9.1 构建

```bash
# 安装构建工具
pip install build

# 构建 wheel 和 sdist
python -m build

# 产物在 dist/ 目录
ls dist/
# mcp-pm-1.0.0.tar.gz
# mcp_pm-1.0.0-py3-none-any.whl
```

### 9.2 发布到 PyPI

```bash
# 安装 twine
pip install twine

# 上传到 TestPyPI (先验证)
twine upload --repository testpypi dist/*

# 上传到正式 PyPI
twine upload dist/*
```

### 9.3 版本管理

遵循 **SemVer** 规范:

- `MAJOR`: 不兼容的 API 变更
- `MINOR`: 向下兼容的新功能
- `PATCH`: 向下兼容的 Bug 修复

使用 `tbump` 或 `bumpversion` 管理版本:

```bash
# 使用 bump-my-version (推荐)
pip install bump-my-version
bump-my-version bump patch  # 1.0.0 → 1.0.1
bump-my-version bump minor  # 1.0.0 → 1.1.0
bump-my-version bump major  # 1.0.0 → 2.0.0
```

### 9.4 发布流程

```bash
# 1. 确保 main 分支通过所有测试
git checkout main
git pull
pytest

# 2. 更新版本号
bump-my-version bump minor
git push --tags

# 3. 构建
rm -rf dist/
python -m build

# 4. 发布
twine upload dist/*

# 5. 创建 GitHub Release
gh release create v$(python -c "import mcp_pm; print(mcp_pm.__version__)") \
  --title "v$(python -c "import mcp_pm; print(mcp_pm.__version__)")" \
  --notes "Release notes here"
```

---

## 10. 常见问题

### Q: pip install -e ".[dev]" 失败怎么办？

**原因**: 通常是因为 setuptools 版本过低或缺少编译依赖。

**解决**:

```bash
pip install --upgrade pip setuptools wheel
pip install -e ".[dev]"
```

### Q: Ruff 报错太多怎么办？

**解决**:

```bash
# 自动修复
ruff check --fix src/mcp_pm

# 查看具体规则说明
ruff rule <rule-code>
```

### Q: mypy 类型检查过不了？

**常见场景**:

1. 三方库缺少类型 stub:

```bash
pip install types-requests types-click
```

2. 动态类型:

```python
# 使用 typing.cast 或 assert
from typing import cast, TYPE_CHECKING

result = cast(InstallResult, response)
```

### Q: 如何在 CI 中运行测试？

**.github/workflows/ci.yml**:

```yaml
name: CI
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -e ".[dev]"
      - run: ruff check src/mcp_pm
      - run: mypy src/mcp_pm
      - run: pytest --cov=src/mcp_pm
```

### Q: 如何贡献代码？

1. Fork 仓库
2. 创建 feature/fix 分支
3. 编写代码和测试
4. 运行 `ruff check`、`mypy`、`pytest`
5. 提交 PR，描述变更内容和测试方法
6. 等待 review

### Q: 本地 registry 如何搭建？

```bash
# 启动本地 registry (开发用)
docker run -d -p 8080:8080 mcp-registry:dev

# 配置指向本地
mcp-pm config set registry.url http://localhost:8080

# 测试连接
mcp-pm search test
```

### Q: 如何添加新的依赖？

```bash
# 安装运行时依赖
pip install <package>

# 安装开发依赖
pip install --dev <package>

# 更新 pyproject.toml
# 在 [project.dependencies] 或 [project.optional-dependencies.dev] 中添加
```

---

## 附录

### A. 常用命令速查

```bash
# 开发
pip install -e ".[dev]"    # 安装开发环境
ruff check src             # Lint 检查
ruff format src            # 格式化代码
mypy src                   # 类型检查
pytest                     # 运行测试
pytest --cov               # 带覆盖率的测试

# 构建与发布
python -m build            # 构建分发包
twine check dist/*         # 验证分发包
twine upload dist/*        # 发布到 PyPI

# 项目工具
mcp-pm --help              # 查看所有命令
mcp-pm doctor              # 诊断系统状态
mcp-pm config show         # 查看当前配置
```

### B. 推荐开发工具

| 工具 | 用途 | 安装方式 |
|------|------|---------|
| VS Code | 代码编辑器 | `code .` |
| Ruff | Linter & Formatter | `pip install ruff` |
| mypy | 类型检查 | `pip install mypy` |
| pytest | 测试框架 | `pip install pytest` |
| pytest-cov | 覆盖率 | `pip install pytest-cov` |
| bump-my-version | 版本管理 | `pip install bump-my-version` |
| pre-commit | Git hooks | `pip install pre-commit` |
| twine | PyPI 发布 | `pip install twine` |
| httpx | HTTP 调试 | `pip install httpx` (已包含) |
