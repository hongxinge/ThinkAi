"""MCP (Model Context Protocol) 支持 - 轻量级MCP Client集成"""
from typing import List, Dict, Any, Optional, AsyncIterator
import json
import asyncio
import subprocess
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
    MCP Server 客户端 - 通过stdio/stdin与MCP Server通信

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

    def __init__(self, command: str, args: Optional[List[str]] = None, env: Optional[Dict[str, str]] = None):
        self.command = command
        self.args = args or []
        self.env = env
        self._process: Optional[subprocess.Popen] = None
        self._request_id = 0

    async def connect(self) -> None:
        """启动MCP Server进程"""
        self._process = await asyncio.create_subprocess_exec(
            self.command,
            *self.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self.env,
        )

    async def close(self) -> None:
        """关闭MCP Server进程"""
        if self._process and self._process.stdin:
            try:
                self._process.stdin.close()
            except Exception:
                pass
        if self._process:
            try:
                self._process.kill()
            except Exception:
                pass

    async def _send_request(self, method: str, params: Optional[Dict] = None) -> Dict:
        """发送JSON-RPC请求"""
        self._request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params or {},
        }
        if not self._process or not self._process.stdin:
            raise RuntimeError("MCP Server not connected")

        request_json = json.dumps(request) + "\n"
        self._process.stdin.write(request_json.encode("utf-8"))
        await self._process.stdin.drain()

        if not self._process.stdout:
            raise RuntimeError("MCP Server stdout not available")

        line = await self._process.stdout.readline()
        if not line:
            raise RuntimeError("MCP Server closed connection")

        return json.loads(line.decode("utf-8"))

    async def list_tools(self) -> List[MCPTool]:
        """列出MCP Server提供的所有工具"""
        response = await self._send_request("tools/list")
        tools = []
        for tool_data in response.get("result", {}).get("tools", []):
            tools.append(MCPTool(
                name=tool_data["name"],
                description=tool_data.get("description", ""),
                input_schema=tool_data.get("inputSchema", {}),
            ))
        return tools

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """调用MCP Server的工具"""
        response = await self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments,
        })
        result = response.get("result", {})
        content = result.get("content", [])
        if not content:
            return json.dumps(result)
        text_parts = []
        for item in content:
            if item.get("type") == "text":
                text_parts.append(item["text"])
            else:
                text_parts.append(json.dumps(item))
        return "\n".join(text_parts) if text_parts else json.dumps(result)


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
