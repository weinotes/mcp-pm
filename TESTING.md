# MCP-PM 测试策略文档

> **项目**: mcp-pm (Model Context Protocol Package Manager)
> **技术栈**: Python 3.11+ · Click · FastAPI · httpx · Pydantic · pytest · pytest-asyncio
> **作者**: Davey Wong \<wgwcko@gmail.com\>
> **测试框架**: pytest 8.x + pytest-asyncio + httpx.MockTransport
> **覆盖率目标**: ≥ 85%

---

## 目录

1. [测试金字塔](#1-测试金字塔)
2. [单元测试策略](#2-单元测试策略)
3. [集成测试](#3-集成测试)
4. [E2E 测试](#4-e2e-测试)
5. [CI 配置说明](#5-ci-配置说明)
6. [性能基准测试](#6-性能基准测试)
7. [覆盖率目标与度量](#7-覆盖率目标与度量)

---

## 1. 测试金字塔

项目采用经典测试金字塔策略，从底层到顶层逐层覆盖：

```
          ╱╲
         ╱  ╲            E2E 测试 (5%)
        ╱    ╲           ──────────────
       ╱      ╲          install → list → serve → call
      ╱────────╲         完整工作流验证
     ╱          ╲
    ╱  集成测试   ╲       Integration (15%)
   ╱     (15%)    ╲      ──────────────────
  ╱────────────────╲     Mock MCP 服务器启动
 ╱                  ╲    HTTP 代理端到端响应
╱────────────────────╲   CLI → Core 模块交互
╱                    ╲
╱   单元测试 (80%)    ╲   Unit (80%)
╱──────────────────────╲ ──────────────────
╱                        ╲ 每个函数/方法的独立测试
╱                          ╲ Mock 所有外部依赖 (HTTP, 子进程, 文件系统)
```

### 各层级比例

| 层级 | 占比 | 运行频率 | 执行时间目标 |
|------|------|---------|------------|
| 单元测试 | ~80% | 每次提交 | < 30 秒 |
| 集成测试 | ~15% | 每次 PR | < 2 分钟 |
| E2E 测试 | ~5% | 每次发布 / 每日 | < 10 分钟 |

### 测试目录结构

```
tests/
├── conftest.py                   # 共享 fixtures 和全局 mock
├── fixtures/                     # 测试数据
│   ├── __init__.py
│   ├── mock_registry.py          # Mock 注册中心响应
│   ├── mock_mcp_server.py        # Mock MCP 服务器进程
│   ├── sample_config.yaml        # 样例配置文件
│   └── sample_manifests/         # 样例 server manifest
├── unit/                         # 单元测试
│   ├── test_cli.py               # CLI 命令解析和参数验证
│   ├── test_config.py            # 配置读写、验证、迁移
│   ├── test_registry.py          # 注册中心客户端
│   ├── test_installer.py         # 安装/卸载逻辑
│   ├── test_client.py            # MCP 客户端运行时
│   ├── test_server.py            # HTTP 代理路由
│   ├── test_sandbox.py           # 沙箱隔离策略
│   ├── test_webui.py             # Web UI 路由和渲染
│   └── test_models.py            # Pydantic 数据模型
├── integration/                  # 集成测试
│   ├── test_install_flow.py      # 安装→配置→列表流程
│   ├── test_proxy_to_mcp.py      # HTTP 代理→MCP 服务器
│   ├── test_registry_integration.py  # 注册中心 API 实际调用
│   └── test_sandbox_docker.py    # Docker 沙箱集成
├── e2e/                          # 端到端测试
│   ├── test_workflow.py          # 完整 install→list→serve→call 流程
│   └── test_cli_e2e.py           # CLI 二进制端到端
├── benchmarks/                   # 性能基准测试
│   ├── test_install_speed.py     # 安装速度基准
│   ├── test_proxy_latency.py     # 代理延迟基准
│   └── test_concurrent_calls.py  # 并发调用基准
└── perf/                         # 性能回归测试
    └── test_compare_baseline.py
```

---

## 2. 单元测试策略

### 2.1 框架与工具

| 工具 | 用途 |
|------|------|
| `pytest` 8.x | 测试框架 |
| `pytest-asyncio` | 异步测试支持 |
| `pytest-cov` | 覆盖率统计 |
| `pytest-xdist` | 并行测试执行 |
| `pytest-timeout` | 测试超时控制 |
| `httpx.MockTransport` | HTTP 客户端 Mock |
| `unittest.mock` / `pytest-mock` | 通用 Mock |
| `freezegun` | 时间冻结 |
| `tmp_path` fixture | 临时文件系统 |

### 2.2 核心 Mock 策略

#### 2.2.1 HTTP 请求 Mock (httpx.MockTransport)

所有外部 HTTP 请求通过 `httpx.MockTransport` 进行 mock，无需真实网络：

```python
# tests/fixtures/mock_registry.py
from httpx import MockTransport, Request, Response
from pytest import fixture

@fixture
def mock_registry_transport():
    """Mock 注册中心 HTTP 响应。"""

    def handler(request: Request) -> Response:
        if "/search" in request.url.path and "calculator" in request.url.query.decode():
            return Response(
                200,
                json={
                    "results": [
                        {
                            "name": "@anthropic/calculator",
                            "version": "1.2.3",
                            "description": "A calculator MCP server",
                            "author": "Anthropic",
                        }
                    ]
                },
            )
        if request.url.path.startswith("/packages/"):
            return Response(
                200,
                json={
                    "name": "@anthropic/calculator",
                    "version": "1.2.3",
                    "download_url": "https://registry.example.com/packages/calc.tar.gz",
                    "checksum": "sha256:abc123...",
                    "dependencies": [],
                },
            )
        return Response(404, json={"error": "not_found"})

    return MockTransport(handler)


@fixture
async def registry_client(mock_registry_transport):
    """返回注册中心客户端实例（无真实网络 I/O）。"""
    from mcp_pm.registry import RegistryClient

    client = RegistryClient(
        base_url="https://registry.mcp-pm.dev",
        http_client_kwargs={"transport": mock_registry_transport},
    )
    return client
```

#### 2.2.2 子进程 Mock

MCP 服务器子进程通过 `unittest.mock.patch` 进行 mock：

```python
# tests/unit/test_client.py
from unittest.mock import AsyncMock, patch, MagicMock

async def test_call_tool_success():
    """测试工具调用成功路径。"""
    mock_process = AsyncMock()
    mock_process.communicate.return_value = (
        b'{"jsonrpc":"2.0","id":1,"result":{"content":[{"type":"text","text":"42"}]}}\n',
        b"",
    )
    mock_process.returncode = 0
    mock_create = AsyncMock(return_value=(mock_process, None))

    with patch("asyncio.create_subprocess_exec", return_value=mock_create):
        from mcp_pm.client import MCPClient
        client = MCPClient()
        result = await client.call_tool("calculate", {"expression": "6*7"})
        assert result.content[0].text == "42"
```

#### 2.2.3 文件系统 Mock

配置读写测试使用 `tmp_path` fixture 隔离文件系统：

```python
# tests/unit/test_config.py

async def test_config_load_and_save(tmp_path):
    """测试配置加载和保存的完整性。"""
    from mcp_pm.config import ConfigManager

    config_dir = tmp_path / ".config" / "mcp-pm"
    config_dir.mkdir(parents=True)

    config = ConfigManager(str(config_dir))
    assert config.load() is not None

    config.data.proxy.port = 9090
    config.save()

    config2 = ConfigManager(str(config_dir))
    config2.load()
    assert config2.data.proxy.port == 9090
```

### 2.3 测试用例模板

#### CLI 命令测试

```python
# tests/unit/test_cli.py
from click.testing import CliRunner
from pytest import fixture, mark

@fixture
def runner():
    return CliRunner()

@mark.asyncio
async def test_install_command(runner, mock_registry_client, tmp_path):
    """验证 `mcp-pm install` 命令的正确执行。"""
    from mcp_pm.cli import cli

    # 使用隔离的配置目录
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(
            cli,
            ["install", "@anthropic/calculator", "--version", "1.2.3"],
        )
        assert result.exit_code == 0
        assert "Installed" in result.output
        assert "@anthropic/calculator" in result.output
```

#### Pydantic 模型验证

```python
# tests/unit/test_models.py
from pydantic import ValidationError
from pytest import raises

def test_server_entry_validation():
    """验证 ServerEntry 数据模型的字段约束。"""
    from mcp_pm.models import ServerEntry

    # 有效数据
    entry = ServerEntry(
        name="test-server",
        version="1.0.0",
        transport="stdio",
    )
    assert entry.name == "test-server"
    assert entry.enabled is True  # 默认值

    # 无效传输协议
    with raises(ValidationError):
        ServerEntry(
            name="test-server",
            version="1.0.0",
            transport="grpc",  # 非法值
        )
```

### 2.4 测试标记分类

```python
# pyproject.toml 配置
# [tool.pytest.ini_options]
# markers = [
#     "slow: 执行较慢的测试",
#     "network: 需要网络连接的测试",
#     "docker: 需要 Docker 的测试",
#     "e2e: 端到端测试",
#     "benchmark: 性能基准测试",
# ]
```

**运行特定标记的测试**:

```bash
# 运行所有测试（跳过慢速和网络测试）
pytest -m "not slow and not network"

# 只运行单元测试
pytest tests/unit/

# 运行所有测试含慢速测试
pytest --run-slow

# 并行运行单元测试
pytest tests/unit/ -n auto
```

---

## 3. 集成测试

集成测试验证多个模块之间的协作，使用 Mock MCP 服务器而非真实的外部服务。

### 3.1 Mock MCP 服务器

使用一个最小化的 MCP 服务器实现作为测试夹具：

```python
# tests/fixtures/mock_mcp_server.py
import asyncio
import json
import sys
from asyncio.subprocess import PIPE

MOCK_SERVER_SCRIPT = """
import json, sys

def send(msg):
    sys.stdout.write(json.dumps(msg) + '\\n')
    sys.stdout.flush()

def recv():
    return json.loads(sys.stdin.readline())

# MCP Initialize handshake
init = recv()
assert init['method'] == 'initialize'
send({'jsonrpc': '2.0', 'id': init['id'], 'result': {
    'protocolVersion': '0.1.0',
    'capabilities': {'tools': {}},
    'serverInfo': {'name': 'mock-server', 'version': '1.0.0'}
}})

# Main loop
while True:
    msg = recv()
    method = msg.get('method')
    if method == 'tools/list':
        send({'jsonrpc': '2.0', 'id': msg['id'], 'result': {
            'tools': [{
                'name': 'echo',
                'description': 'Echo input back',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'message': {'type': 'string'}
                    },
                    'required': ['message']
                }
            }]
        }})
    elif method == 'tools/call':
        args = msg['params']['arguments']
        send({'jsonrpc': '2.0', 'id': msg['id'], 'result': {
            'content': [{'type': 'text', 'text': args.get('message', '')}]
        }})
    elif method == 'shutdown':
        send({'jsonrpc': '2.0', 'id': msg['id'], 'result': None})
        break
"""

@fixture
async def mock_mcp_server():
    """启动一个 Mock MCP 服务器子进程供集成测试使用。"""
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c", MOCK_SERVER_SCRIPT,
        stdin=PIPE,
        stdout=PIPE,
        stderr=PIPE,
    )
    # 等待初始化完成
    await asyncio.sleep(0.1)
    yield proc
    proc.terminate()
    await proc.wait()
```

### 3.2 代理服务器集成测试

```python
# tests/integration/test_proxy_to_mcp.py
from httpx import AsyncClient, ASGITransport
from pytest import mark

@mark.asyncio
async def test_proxy_forwards_tool_call(mock_mcp_server, app_config):
    """验证 HTTP 代理正确转发工具调用到 MCP 服务器。"""
    from mcp_pm.server import create_app

    app = create_app(app_config)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 列出工具
        resp = await client.post("/v1/tools/list")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["tools"]) > 0

        # 调用工具
        resp = await client.post("/v1/tools/call", json={
            "name": "mock-server__echo",
            "arguments": {"message": "hello"},
        })
        assert resp.status_code == 200
        assert resp.json()["content"][0]["text"] == "hello"
```

### 3.3 安装流程集成测试

```python
# tests/integration/test_install_flow.py
@mark.asyncio
async def test_install_updates_config(tmp_path, mock_registry_transport):
    """验证安装后配置文件正确更新。"""
    from mcp_pm.installer import Installer
    from mcp_pm.config import ConfigManager

    config_dir = tmp_path / ".config" / "mcp-pm"
    config = ConfigManager(str(config_dir))
    config.load()

    installer = Installer(
        config=config,
        registry_transport=mock_registry_transport,
    )
    result = await installer.install("@anthropic/calculator")

    assert result.success is True
    assert result.name == "@anthropic/calculator"

    # 验证配置已更新
    config.load()
    names = [s.name for s in config.data.profiles["default"].servers]
    assert "@anthropic/calculator" in names
```

---

## 4. E2E 测试

端到端测试覆盖完整的用户工作流，从 CLICK 调用到 HTTP 代理响应。

### 4.1 完整工作流测试

```python
# tests/e2e/test_workflow.py
import subprocess
import time
import httpx
from pytest import mark, fixture

@mark.e2e
@mark.slow
def test_install_list_serve_call_workflow(tmp_path, mcp_pm_binary):
    """
    E2E 测试：完整的 install → list → serve → call 流程。

    测试步骤：
    1. 使用 mock 注册中心安装一个 MCP 服务器
    2. 使用 list 命令验证安装成功
    3. 启动 HTTP 代理服务器
    4. 通过 HTTP 代理调用工具
    5. 验证响应正确
    6. 卸载服务器
    """
    # Step 1: Install
    install_result = subprocess.run(
        [mcp_pm_binary, "install", "@anthropic/calculator", "--yes"],
        capture_output=True,
        text=True,
        env={"MCP_PM_CONFIG_DIR": str(tmp_path / ".config")},
    )
    assert install_result.returncode == 0
    assert "Installed" in install_result.stdout

    # Step 2: List
    list_result = subprocess.run(
        [mcp_pm_binary, "list", "--json"],
        capture_output=True,
        text=True,
        env={"MCP_PM_CONFIG_DIR": str(tmp_path / ".config")},
    )
    assert list_result.returncode == 0
    assert "@anthropic/calculator" in list_result.stdout

    # Step 3: Serve (start proxy in background)
    proxy_proc = subprocess.Popen(
        [mcp_pm_binary, "serve", "127.0.0.1:9876"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={"MCP_PM_CONFIG_DIR": str(tmp_path / ".config")},
    )
    time.sleep(1)  # 等待服务器启动

    try:
        # Step 4: Call tool via HTTP
        async with httpx.AsyncClient(base_url="http://127.0.0.1:9876") as client:
            resp = await client.post("/v1/tools/list")
            assert resp.status_code == 200
            tools = resp.json()["tools"]
            assert len(tools) > 0

            # Step 5: Execute tool
            tool_name = tools[0]["name"]
            call_resp = await client.post("/v1/tools/call", json={
                "name": tool_name,
                "arguments": {},
            })
            assert call_resp.status_code == 200
    finally:
        # Cleanup
        proxy_proc.terminate()
        proxy_proc.wait()

    # Step 6: Uninstall
    uninstall_result = subprocess.run(
        [mcp_pm_binary, "uninstall", "@anthropic/calculator", "--yes"],
        capture_output=True,
        text=True,
        env={"MCP_PM_CONFIG_DIR": str(tmp_path / ".config")},
    )
    assert uninstall_result.returncode == 0
```

### 4.2 CLI 端到端测试

```python
# tests/e2e/test_cli_e2e.py
@mark.e2e
def test_cli_subcommand_help():
    """验证所有子命令的帮助信息正常输出。"""
    from click.testing import CliRunner
    from mcp_pm.cli import cli

    runner = CliRunner()

    commands = [
        ["install", "--help"],
        ["uninstall", "--help"],
        ["list", "--help"],
        ["search", "--help"],
        ["info", "--help"],
        ["explore", "--help"],
        ["serve", "--help"],
        ["config", "--help"],
        ["sandbox", "--help"],
        ["doctor", "--help"],
        ["run", "--help"],
        ["update", "--help"],
    ]

    for cmd in commands:
        result = runner.invoke(cli, cmd)
        assert result.exit_code == 0, f"Command 'mcp-pm {' '.join(cmd)}' failed"
        assert "Usage:" in result.output or "Show this message" in result.output
```

---

## 5. CI 配置说明

### 5.1 GitHub Actions 工作流

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

env:
  PYTHON_VERSION: "3.11"
  UV_VERSION: "0.4"

jobs:
  lint:
    name: Lint & Type Check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with:
          version: ${{ env.UV_VERSION }}
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      - name: Install dependencies
        run: uv pip install --system -e ".[dev]"
      - name: Run ruff
        run: ruff check src/mcp_pm tests
      - name: Run mypy
        run: mypy src/mcp_pm

  unit:
    name: Unit Tests (Python ${{ matrix.python-version }})
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with:
          version: ${{ env.UV_VERSION }}
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - name: Install dependencies
        run: uv pip install --system -e ".[dev]"
      - name: Run unit tests with coverage
        run: |
          pytest tests/unit/ \
            --cov=src/mcp_pm \
            --cov-report=xml \
            --cov-report=term-missing \
            --cov-fail-under=85 \
            -n auto \
            -m "not slow and not network and not docker and not e2e and not benchmark"
      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: ./coverage.xml
          flags: unit

  integration:
    name: Integration Tests
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with:
          version: ${{ env.UV_VERSION }}
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      - name: Install dependencies
        run: uv pip install --system -e ".[dev]"
      - name: Run integration tests
        run: |
          pytest tests/integration/ \
            --cov=src/mcp_pm \
            --cov-report=xml \
            --cov-report=term-missing \
            --cov-append \
            -m "not docker"
      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: ./coverage.xml
          flags: integration

  e2e:
    name: E2E Tests
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with:
          version: ${{ env.UV_VERSION }}
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      - name: Install dependencies
        run: uv pip install --system -e ".[dev]"
      - name: Build package
        run: pip install -e .
      - name: Run E2E tests
        run: pytest tests/e2e/ -v -m e2e --timeout=300

  benchmark:
    name: Performance Benchmarks
    runs-on: ubuntu-latest
    timeout-minutes: 15
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with:
          version: ${{ env.UV_VERSION }}
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      - name: Install dependencies
        run: uv pip install --system -e ".[dev]"
      - name: Run benchmarks
        run: pytest tests/benchmarks/ -v -m benchmark --benchmark-json=benchmark_results.json
      - name: Store benchmark results
        uses: actions/cache@v4
        with:
          path: benchmark_results.json
          key: benchmark-${{ github.sha }}

  coverage:
    name: Coverage Report
    runs-on: ubuntu-latest
    needs: [unit, integration]
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with:
          version: ${{ env.UV_VERSION }}
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      - name: Install dependencies
        run: uv pip install --system -e ".[dev]"
      - name: Run all tests with coverage aggregation
        run: |
          pytest tests/ \
            --cov=src/mcp_pm \
            --cov-report=xml \
            --cov-report=html \
            --cov-report=term \
            -m "not e2e and not docker and not benchmark"
      - name: Upload combined coverage
        uses: codecov/codecov-action@v4
        with:
          file: ./coverage.xml
      - name: Upload HTML report
        uses: actions/upload-artifact@v4
        with:
          name: coverage-report
          path: htmlcov/
```

### 5.2 预提交 Hook 配置

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.4.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.9.0
    hooks:
      - id: mypy
        additional_dependencies: [pydantic, httpx, types-click]
  - repo: local
    hooks:
      - id: pytest-unit
        name: pytest (unit)
        entry: pytest tests/unit/ -n auto
        language: system
        types: [python]
        pass_filenames: false
```

---

## 6. 性能基准测试

使用 `pytest-benchmark` 插件进行持续性能测量。

### 6.1 安装速度基准

```python
# tests/benchmarks/test_install_speed.py
from pytest import mark, fixture

@mark.benchmark
@mark.asyncio
async def test_install_speed(benchmark, mock_registry_client, tmp_path):
    """测量单次安装操作的耗时。"""
    from mcp_pm.installer import Installer
    from mcp_pm.config import ConfigManager

    config = ConfigManager(str(tmp_path / ".config"))

    installer = Installer(config=config)
    installer._registry = mock_registry_client

    def _install():
        import asyncio
        return asyncio.run(installer.install("@anthropic/calculator"))

    result = benchmark(_install)
    assert result.success is True
```

### 6.2 代理延迟基准

```python
# tests/benchmarks/test_proxy_latency.py
@mark.benchmark
@mark.asyncio
async def test_proxy_tool_call_latency(benchmark, app_with_mock_server):
    """测量通过 HTTP 代理调用工具的 P50/P95/P99 延迟。"""
    from httpx import AsyncClient, ASGITransport

    transport = ASGITransport(app=app_with_mock_server)
    async with AsyncClient(transport=transport, base_url="http://test") as client:

        async def _call_tool():
            resp = await client.post("/v1/tools/call", json={
                "name": "mock-server__echo",
                "arguments": {"message": "benchmark"},
            })
            return resp.status_code

        result = benchmark(_call_tool)
        assert result == 200
```

### 6.3 并发调用基准

```python
# tests/benchmarks/test_concurrent_calls.py
@mark.benchmark
@mark.asyncio
async def test_concurrent_tool_calls(benchmark, app_with_mock_server):
    """测量并发工具调用的吞吐量（10 并发）。"""
    import asyncio
    from httpx import AsyncClient, ASGITransport

    transport = ASGITransport(app=app_with_mock_server)

    async def _concurrent_calls():
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            tasks = [
                client.post("/v1/tools/call", json={
                    "name": "mock-server__echo",
                    "arguments": {"message": f"msg-{i}"},
                })
                for i in range(10)
            ]
            responses = await asyncio.gather(*tasks)
            return all(r.status_code == 200 for r in responses)

    result = benchmark(_concurrent_calls)
    assert result is True
```

### 6.4 基准阈值

```yaml
# .bencheth/benchmarks.yml
benchmarks:
  install_speed:
    max_duration_ms: 5000          # 安装操作 ≤ 5 秒
    max_variance_pct: 20           # 方差 ≤ 20%

  proxy_latency:
    p50_ms: 10                     # 中位数延迟 ≤ 10ms
    p95_ms: 50                     # P95 延迟 ≤ 50ms
    p99_ms: 100                    # P99 延迟 ≤ 100ms

  concurrent_calls:
    min_throughput: 500            # 每秒 ≥ 500 次调用
    max_p95_ms: 100                # 并发下 P95 ≤ 100ms

  server_startup:
    max_duration_ms: 3000          # MCP 服务器启动 ≤ 3 秒
```

---

## 7. 覆盖率目标与度量

### 7.1 覆盖率目标

| 模块 | 行覆盖率目标 | 分支覆盖率目标 |
|------|------------|--------------|
| `cli.py` | ≥ 80% | ≥ 70% |
| `config.py` | ≥ 90% | ≥ 85% |
| `registry.py` | ≥ 90% | ≥ 85% |
| `installer.py` | ≥ 85% | ≥ 80% |
| `client.py` | ≥ 85% | ≥ 80% |
| `server.py` | ≥ 85% | ≥ 80% |
| `sandbox.py` | ≥ 80% | ≥ 75% |
| `webui/` | ≥ 75% | ≥ 65% |
| **整体** | **≥ 85%** | **≥ 80%** |

### 7.2 覆盖率配置

```ini
# pyproject.toml
[tool.coverage.run]
source = ["src/mcp_pm"]
omit = [
    "src/mcp_pm/__main__.py",
    "src/mcp_pm/_version.py",
]

[tool.coverage.report]
# 覆盖率阈值
fail_under = 85
# 排除分支覆盖的代码
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "if __name__ == .__main__.:",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
]
```

### 7.3 覆盖率不可接受模式

以下模式不被视为有效覆盖，CI 将拒绝：

| 模式 | 原因 |
|------|------|
| 仅测 happy path，无错误路径 | 覆盖率虚高 |
| Mock 返回值与真实返回值不一致 | 测试无效 |
| 跳过异步代码的异常处理分支 | 关键路径未覆盖 |
| 使用 `# pragma: no cover` 覆盖大量代码 | 应编写测试而非跳过 |
| 集成测试 mock 了所有依赖（实为单元测试） | 需区分层级 |

### 7.4 覆盖率报告生成

```bash
# 本地生成覆盖率报告
pytest --cov=src/mcp_pm --cov-report=html tests/
open htmlcov/index.html

# 仅显示未覆盖的行
pytest --cov=src/mcp_pm --cov-report=term-missing tests/

# 增量覆盖率检查（与 baseline 对比）
pytest --cov=src/mcp_pm --cov-report=diff tests/
```

---

## 附录：测试命令速查

```bash
# 运行全部测试
pytest

# 仅单元测试
pytest tests/unit/

# 仅集成测试
pytest tests/integration/

# 仅 E2E 测试
pytest tests/e2e/ -m e2e

# 仅性能基准
pytest tests/benchmarks/ -m benchmark --benchmark-only

# 带覆盖率
pytest --cov=src/mcp_pm --cov-report=term-missing

# 特定测试文件
pytest tests/unit/test_config.py

# 特定测试函数
pytest tests/unit/test_config.py::test_config_load_and_save -v

# 按关键字过滤
pytest -k "install and not slow"

# 并行运行
pytest -n auto

# 失败时进入 PDB
pytest --pdb -x

# 最后一次失败重跑
pytest --lf

# 输出详细信息
pytest -v --tb=long
```
