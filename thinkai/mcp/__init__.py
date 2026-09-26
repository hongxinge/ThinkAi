"""MCP (Model Context Protocol) 支持 - 轻量级MCP Client集成"""
from typing import List, Dict, Any, Optional, AsyncIterator
import json
import asyncio
from pathlib import Path


class MCPTool:
    """MCP工具 - 封装MCP Server提供的工具"""

    def __init__(self, name: str, description: str, input_schema: Dict[str, Any]):
        self.name = name
        self.description = description
        self.input_schema = input_schema

    def to_openai_format(self) -> Dict[str, Any]:
        """转换为OpenAI兼容的工具格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }


class MCPServerClient:
    """
    MCP Server 客户端 - 通过stdio与MCP Server通信

    实现了标准MCP握手流程(initialize -> notifications/initialized),
    支持并发请求、响应按id匹配、请求超时与stderr日志排空。

    使用示例:
        client = MCPServerClient(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "/path/to/dir"],
        )
        await client.connect()
        tools = await client.list_tools()
        result = await client.call_tool("read_file", {"path": "file.txt"})
        await client.close()
    """

    def __init__(
        self,
        command: str,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: float = 30.0,
    ):
        self.command = command
        self.args = args or []
        self.env = env
        self.timeout = timeout
        self._process: Optional[asyncio.subprocess.Process] = None
        self._request_id = 0
        self._pending: Dict[int, asyncio.Future] = {}
        self._reader_task: Optional[asyncio.Task] = None
        self._stderr_task: Optional[asyncio.Task] = None
        self._stderr_tail: List[str] = []

    async def connect(self) -> None:
        """启动MCP Server进程并完成initialize握手"""
        self._stderr_tail.clear()
        self._process = await asyncio.create_subprocess_exec(
            self.command,
            *self.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self.env,
        )

        loop = asyncio.get_running_loop()
        self._reader_task = loop.create_task(self._read_loop())
        self._stderr_task = loop.create_task(self._drain_stderr())

        # MCP协议握手: initialize -> notifications/initialized
        # 未握手的Server会拒绝tools/list等后续请求
        from thinkai import __version__
        await self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "thinkai", "version": __version__},
        })
        await self._send_notification("notifications/initialized")

    async def _read_loop(self) -> None:
        """持续读取stdout,按id分发JSON-RPC响应,跳过通知与请求"""
        process = self._process
        if not process or not process.stdout:
            return
        try:
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(message, dict):
                    continue
                msg_id = message.get("id")
                if msg_id is None:
                    continue  # 服务端通知,当前客户端无需处理
                future = self._pending.pop(msg_id, None)
                if future is None or future.cancelled() or future.done():
                    continue
                if "error" in message:
                    err = message["error"]
                    future.set_exception(RuntimeError(
                        f"MCP error {err.get('code')}: {err.get('message')}"
                    ))
                else:
                    future.set_result(message.get("result", {}))
        except asyncio.CancelledError:
            raise
        finally:
            # 进程输出已关闭 - 让所有等待中的请求失败
            for future in self._pending.values():
                if not future.done():
                    future.set_exception(RuntimeError("MCP Server closed connection"))
            self._pending.clear()

    async def _drain_stderr(self) -> None:
        """持续读取stderr防止缓冲区撑满导致死锁,保留尾部日志用于诊断"""
        process = self._process
        if not process or not process.stderr:
            return
        try:
            while True:
                line = await process.stderr.readline()
                if not line:
                    break
                self._stderr_tail.append(line.decode("utf-8", errors="replace").rstrip())
                if len(self._stderr_tail) > 50:
                    self._stderr_tail.pop(0)
        except asyncio.CancelledError:
            raise

    def get_stderr_tail(self) -> List[str]:
        """获取stderr尾部日志(连接失败时用于诊断)"""
        return list(self._stderr_tail)

    async def _send_notification(self, method: str) -> None:
        """发送JSON-RPC通知(无需响应)"""
        if not self._process or not self._process.stdin:
            raise RuntimeError("MCP Server not connected")
        message = json.dumps({"jsonrpc": "2.0", "method": method}) + "\n"
        self._process.stdin.write(message.encode("utf-8"))
        await self._process.stdin.drain()

    async def _send_request(self, method: str, params: Optional[Dict] = None) -> Dict:
        """发送JSON-RPC请求并等待匹配id的响应"""
        if not self._process or not self._process.stdin:
            raise RuntimeError("MCP Server not connected")

        self._request_id += 1
        request_id = self._request_id
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params or {},
        }

        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        self._pending[request_id] = future

        try:
            request_json = json.dumps(request) + "\n"
            self._process.stdin.write(request_json.encode("utf-8"))
            await self._process.stdin.drain()
            return await asyncio.wait_for(future, timeout=self.timeout)
        except asyncio.TimeoutError:
            raise RuntimeError(
                f"MCP request '{method}' timed out after {self.timeout}s"
            ) from None
        finally:
            self._pending.pop(request_id, None)

    async def list_tools(self) -> List[MCPTool]:
        """列出MCP Server提供的所有工具"""
        result = await self._send_request("tools/list")
        tools = []
        for tool_data in result.get("tools", []):
            tools.append(MCPTool(
                name=tool_data["name"],
                description=tool_data.get("description", ""),
                input_schema=tool_data.get("inputSchema", {}),
            ))
        return tools

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """调用MCP Server的工具"""
        result = await self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments,
        })
        content = result.get("content", [])
        if not content:
            return json.dumps(result, ensure_ascii=False)
        text_parts = []
        for item in content:
            if item.get("type") == "text":
                text_parts.append(item["text"])
            else:
                text_parts.append(json.dumps(item, ensure_ascii=False))
        return "\n".join(text_parts) if text_parts else json.dumps(result, ensure_ascii=False)

    async def close(self) -> None:
        """关闭MCP Server进程(先停止读取任务,优雅退出,超时强杀)"""
        process, self._process = self._process, None

        # 先停止读取任务,避免与进程清理产生竞态
        for task in (self._reader_task, self._stderr_task):
            if task and not task.done():
                task.cancel()
        for task in (self._reader_task, self._stderr_task):
            if task:
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception:
                    pass
        self._reader_task = None
        self._stderr_task = None

        if process:
            try:
                if process.stdin:
                    process.stdin.close()
            except Exception:
                pass
            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except asyncio.TimeoutError:
                try:
                    process.kill()
                except Exception:
                    pass
                try:
                    await process.wait()
                except Exception:
                    pass


class MCPAdapter:
    """
    MCP适配器 - 将MCP Server工具集成到ThinkAi Agent

    使用示例:
        from thinkai.mcp import MCPAdapter
        from thinkai import ThinkAI

        ai = ThinkAI(provider="openai", api_key="your-key")

        adapter = MCPAdapter()
        adapter.add_server(
            name="filesystem",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "/workspace"],
        )

        agent = adapter.create_agent(ai_client=ai)
        result = await agent.run("读取/workspace/readme.md文件内容")
    """

    def __init__(self):
        self._servers: Dict[str, MCPServerClient] = {}
        self._mcp_tools: Dict[str, List[MCPTool]] = {}

    def add_server(self, name: str, command: str, args: Optional[List[str]] = None, env: Optional[Dict[str, str]] = None):
        """添加MCP Server"""
        self._servers[name] = MCPServerClient(command=command, args=args, env=env)

    async def connect_all(self):
        """连接所有MCP Server"""
        for name, client in self._servers.items():
            await client.connect()
            tools = await client.list_tools()
            self._mcp_tools[name] = tools

    async def close_all(self):
        """关闭所有MCP Server"""
        for client in self._servers.values():
            await client.close()

    def get_all_tools(self) -> List[MCPTool]:
        """获取所有MCP工具"""
        all_tools = []
        for tools in self._mcp_tools.values():
            all_tools.extend(tools)
        return all_tools

    def create_agent(self, ai_client, agent_class=None, **agent_kwargs):
        """创建集成了MCP工具的Agent"""
        from thinkai.agent.function_calling import FunctionCallingAgent

        all_tools = self.get_all_tools()
        if not all_tools:
            raise RuntimeError("No MCP tools available. Call connect_all() first.")

        return FunctionCallingAgent(
            name="mcp-agent",
            ai_client=ai_client,
            tools=[self._wrap_mcp_tool(t) for t in all_tools],
            **agent_kwargs,
        )

    def _wrap_mcp_tool(self, mcp_tool: MCPTool):
        """将MCPTool包装为ThinkAI Tool"""
        from thinkai.agent.tool import Tool

        server_name = None
        for name, tools in self._mcp_tools.items():
            if mcp_tool in tools:
                server_name = name
                break

        async def mcp_tool_wrapper(**kwargs) -> str:
            client = self._servers.get(server_name)
            if not client:
                return json.dumps({"error": f"MCP server '{server_name}' not found"})
            try:
                return await client.call_tool(mcp_tool.name, kwargs)
            except Exception as e:
                return json.dumps({"error": str(e)})

        return Tool(
            name=mcp_tool.name,
            description=mcp_tool.description,
            func=mcp_tool_wrapper,
        )


class MCPRegistry:
    """
    常用MCP Server注册表 - 预定义常用MCP Server配置
    """

    @staticmethod
    def filesystem(path: str = ".") -> Dict[str, Any]:
        """文件系统MCP Server"""
        return {
            "name": "filesystem",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", path],
        }

    @staticmethod
    def sqlite(db_path: str = "./data.db") -> Dict[str, Any]:
        """SQLite数据库MCP Server"""
        return {
            "name": "sqlite",
            "command": "uvx",
            "args": ["mcp-server-sqlite", "--db-path", db_path],
        }

    @staticmethod
    def github(token: str) -> Dict[str, Any]:
        """GitHub MCP Server"""
        import os
        env = os.environ.copy()
        env["GITHUB_PERSONAL_ACCESS_TOKEN"] = token
        return {
            "name": "github",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
            "env": env,
        }

    @staticmethod
    def puppeteer() -> Dict[str, Any]:
        """浏览器自动化MCP Server"""
        return {
            "name": "puppeteer",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-puppeteer"],
        }
