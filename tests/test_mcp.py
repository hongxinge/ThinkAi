"""MCP支持测试"""
import pytest


class TestMCP:
    """MCP 模块测试"""

    def test_import(self):
        from thinkai.mcp import MCPAdapter, MCPServerClient, MCPTool, MCPRegistry
        assert MCPAdapter is not None
        assert MCPServerClient is not None
        assert MCPTool is not None
        assert MCPRegistry is not None

    def test_import_from_thinkai(self):
        from thinkai import MCPAdapter, MCPServerClient, MCPTool, MCPRegistry
        assert MCPAdapter is not None
        assert MCPServerClient is not None
        assert MCPTool is not None
        assert MCPRegistry is not None

    def test_mcp_tool_creation(self):
        from thinkai.mcp import MCPTool

        tool = MCPTool(
            name="read_file",
            description="Read a file",
            input_schema={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        )
        assert tool.name == "read_file"
        assert tool.description == "Read a file"

    def test_mcp_tool_to_openai(self):
        from thinkai.mcp import MCPTool

        tool = MCPTool(
            name="write_file",
            description="Write to a file",
            input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
        )
        spec = tool.to_openai_format()

        assert spec["type"] == "function"
        assert spec["function"]["name"] == "write_file"
        assert spec["function"]["description"] == "Write to a file"
        assert "parameters" in spec["function"]

    def test_mcp_server_client_creation(self):
        from thinkai.mcp import MCPServerClient

        client = MCPServerClient(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
        )
        assert client.command == "npx"
        assert "-y" in client.args

    def test_mcp_adapter_creation(self):
        from thinkai.mcp import MCPAdapter

        adapter = MCPAdapter()
        assert adapter is not None
        assert len(adapter._servers) == 0

    def test_mcp_adapter_add_server(self):
        from thinkai.mcp import MCPAdapter

        adapter = MCPAdapter()
        adapter.add_server(
            name="test-fs",
            command="echo",
            args=["test"],
        )
        assert "test-fs" in adapter._servers
        assert adapter._servers["test-fs"].command == "echo"

    def test_mcp_registry_filesystem(self):
        from thinkai.mcp import MCPRegistry

        config = MCPRegistry.filesystem(path="/workspace")
        assert config["name"] == "filesystem"
        assert "/workspace" in config["args"]

    def test_mcp_registry_sqlite(self):
        from thinkai.mcp import MCPRegistry

        config = MCPRegistry.sqlite(db_path="./test.db")
        assert config["name"] == "sqlite"
        assert "./test.db" in config["args"]

    def test_mcp_registry_github(self):
        from thinkai.mcp import MCPRegistry

        config = MCPRegistry.github(token="test-token")
        assert config["name"] == "github"
        assert config["env"]["GITHUB_PERSONAL_ACCESS_TOKEN"] == "test-token"

    def test_mcp_registry_puppeteer(self):
        from thinkai.mcp import MCPRegistry

        config = MCPRegistry.puppeteer()
        assert config["name"] == "puppeteer"
        assert "puppeteer" in " ".join(config["args"])
