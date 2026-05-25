"""更多内置 Skill - 数据库操作、API调用、图像处理等"""
from typing import List, Dict, Any, Optional
import json
import os
import base64
from pathlib import Path
from datetime import datetime

from thinkai.agent.tool import Tool
from thinkai.agent.function_calling import FunctionCallingAgent
from thinkai.core.client import ThinkAI


class BaseSkillMixin:
    """Skill mixin - 为独立 Skill 类提供通用能力"""

    def get_agent(self, ai_client: Optional[ThinkAI] = None) -> FunctionCallingAgent:
        return FunctionCallingAgent(
            name=f"{self.name}-agent",
            tools=self.get_tools(),
            ai_client=ai_client,
            system_prompt=self.description,
        )


class DatabaseSkill(BaseSkillMixin):
    """数据库操作 Skill - SQLite 查询"""

    name = "database"
    description = "Query and manage SQLite databases"

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path

    def get_tools(self) -> List[Tool]:
        import sqlite3

        def execute_sql(query: str, db_path: Optional[str] = None) -> str:
            """Execute a SQL query and return results.

            Args:
                query: SQL query to execute
                db_path: Database file path (optional, uses default if not provided)
            """
            try:
                path = db_path or self.db_path
                conn = sqlite3.connect(path)
                cursor = conn.cursor()
                cursor.execute(query)

                if query.strip().upper().startswith("SELECT"):
                    rows = cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description]
                    result = {"columns": columns, "rows": [list(row) for row in rows], "count": len(rows)}
                else:
                    conn.commit()
                    result = {"affected_rows": cursor.rowcount, "message": "Query executed successfully"}

                conn.close()
                return json.dumps(result, ensure_ascii=False)
            except Exception as e:
                return json.dumps({"error": str(e)})

        def create_table(table_name: str, columns: str, db_path: Optional[str] = None) -> str:
            """Create a table in the database.

            Args:
                table_name: Name of the table to create
                columns: Column definitions (e.g., 'id INTEGER PRIMARY KEY, name TEXT')
                db_path: Database file path (optional)
            """
            query = f"CREATE TABLE IF NOT EXISTS {table_name} ({columns})"
            return execute_sql(query, db_path)

        def describe_table(table_name: str, db_path: Optional[str] = None) -> str:
            """Get table schema information.

            Args:
                table_name: Name of the table
                db_path: Database file path (optional)
            """
            query = f"PRAGMA table_info({table_name})"
            return execute_sql(query, db_path)

        def list_tables(db_path: Optional[str] = None) -> str:
            """List all tables in the database.

            Args:
                db_path: Database file path (optional)
            """
            query = "SELECT name FROM sqlite_master WHERE type='table'"
            return execute_sql(query, db_path)

        return [
            Tool(name="execute_sql", description="Execute a SQL query", func=execute_sql),
            Tool(name="create_table", description="Create a table", func=create_table),
            Tool(name="describe_table", description="Get table schema", func=describe_table),
            Tool(name="list_tables", description="List all tables", func=list_tables),
        ]


class APISkill(BaseSkillMixin):
    """API 调用 Skill - HTTP 请求"""

    name = "api"
    description = "Make HTTP API requests"

    def get_tools(self) -> List[Tool]:
        import httpx

        async def http_request(
            method: str = "GET",
            url: str = "",
            headers: Optional[str] = None,
            body: Optional[str] = None,
            query_params: Optional[str] = None,
        ) -> str:
            """Make an HTTP request.

            Args:
                method: HTTP method (GET, POST, PUT, DELETE, etc.)
                url: Request URL
                headers: JSON string of headers
                body: Request body (for POST/PUT)
                query_params: JSON string of query parameters
            """
            try:
                headers_dict = json.loads(headers) if headers else {}
                params_dict = json.loads(query_params) if query_params else {}
                body_dict = json.loads(body) if body else None

                async with httpx.AsyncClient(timeout=30) as client:
                    response = await client.request(
                        method=method.upper(),
                        url=url,
                        headers=headers_dict,
                        json=body_dict if body_dict else None,
                        params=params_dict,
                    )

                    try:
                        result = response.json()
                    except:
                        result = response.text

                    return json.dumps({
                        "status_code": response.status_code,
                        "headers": dict(response.headers),
                        "body": result,
                    }, ensure_ascii=False, default=str)
            except Exception as e:
                return json.dumps({"error": str(e)})

        async def http_get(url: str, headers: Optional[str] = None) -> str:
            """Make a GET request.

            Args:
                url: Request URL
                headers: JSON string of headers
            """
            return await http_request("GET", url, headers=headers)

        async def http_post(url: str, body: str, headers: Optional[str] = None) -> str:
            """Make a POST request.

            Args:
                url: Request URL
                body: JSON request body
                headers: JSON string of headers
            """
            return await http_request("POST", url, headers=headers, body=body)

        return [
            Tool(name="http_request", description="Make any HTTP request", func=http_request),
            Tool(name="http_get", description="Make a GET request", func=http_get),
            Tool(name="http_post", description="Make a POST request", func=http_post),
        ]


class ImageSkill(BaseSkillMixin):
    """图像处理 Skill - 基础操作"""

    name = "image"
    description = "Process and analyze images"

    def get_tools(self) -> List[Tool]:
        def image_info(file_path: str) -> str:
            """Get image file information.

            Args:
                file_path: Path to the image file
            """
            try:
                path = Path(file_path)
                if not path.exists():
                    return json.dumps({"error": f"File not found: {file_path}"})

                size = path.stat().st_size
                suffix = path.suffix.lower()

                # Try to get image dimensions if PIL is available
                try:
                    from PIL import Image
                    img = Image.open(path)
                    return json.dumps({
                        "file": str(path),
                        "format": suffix,
                        "size_bytes": size,
                        "width": img.width,
                        "height": img.height,
                        "mode": img.mode,
                    })
                except ImportError:
                    return json.dumps({
                        "file": str(path),
                        "format": suffix,
                        "size_bytes": size,
                        "note": "Install Pillow for detailed image info",
                    })
            except Exception as e:
                return json.dumps({"error": str(e)})

        def image_to_base64(file_path: str) -> str:
            """Convert image file to base64 string.

            Args:
                file_path: Path to the image file
            """
            try:
                with open(file_path, "rb") as f:
                    data = base64.b64encode(f.read()).decode("utf-8")
                return json.dumps({"base64": data[:200] + "..." if len(data) > 200 else data, "length": len(data)})
            except Exception as e:
                return json.dumps({"error": str(e)})

        def list_images(directory: str) -> str:
            """List image files in a directory.

            Args:
                directory: Directory to search
            """
            try:
                path = Path(directory)
                image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"}
                images = [f.name for f in path.iterdir() if f.suffix.lower() in image_extensions]
                return json.dumps({"directory": str(path), "images": images, "count": len(images)})
            except Exception as e:
                return json.dumps({"error": str(e)})

        return [
            Tool(name="image_info", description="Get image file information", func=image_info),
            Tool(name="image_to_base64", description="Convert image to base64", func=image_to_base64),
            Tool(name="list_images", description="List image files", func=list_images),
        ]


class TextSkill(BaseSkillMixin):
    """文本处理 Skill"""

    name = "text"
    description = "Advanced text processing utilities"

    def get_tools(self) -> List[Tool]:
        def count_words(text: str) -> str:
            """Count words, characters, and lines in text.

            Args:
                text: The text to analyze
            """
            words = len(text.split())
            chars = len(text)
            lines = text.count("\n") + 1
            return json.dumps({
                "words": words,
                "characters": chars,
                "lines": lines,
                "non_empty_lines": len([l for l in text.split("\n") if l.strip()]),
            })

        def extract_keywords(text: str, top_n: int = 10) -> str:
            """Extract keywords from text using frequency analysis.

            Args:
                text: The text to analyze
                top_n: Number of top keywords to return
            """
            import re
            from collections import Counter

            stop_words = {"the", "a", "an", "is", "are", "was", "were", "in", "on", "at", "to", "for", "with", "by", "of", "and", "or", "not", "it", "this", "that", "these", "those"}
            words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
            words = [w for w in words if w not in stop_words]
            counter = Counter(words)
            keywords = [{"word": w, "count": c} for w, c in counter.most_common(top_n)]
            return json.dumps({"keywords": keywords, "total_words": len(words)})

        def summarize_structure(text: str) -> str:
            """Analyze text structure (paragraphs, headings, etc.).

            Args:
                text: The text to analyze
            """
            paragraphs = text.split("\n\n")
            headings = [line for line in text.split("\n") if line.startswith("#") or line.isupper()]
            return json.dumps({
                "paragraphs": len(paragraphs),
                "headings": headings[:10],
                "avg_paragraph_length": sum(len(p) for p in paragraphs) / max(len(paragraphs), 1),
            })

        return [
            Tool(name="count_words", description="Count text statistics", func=count_words),
            Tool(name="extract_keywords", description="Extract keywords from text", func=extract_keywords),
            Tool(name="summarize_structure", description="Analyze text structure", func=summarize_structure),
        ]


class SystemSkill(BaseSkillMixin):
    """系统操作 Skill"""

    name = "system"
    description = "System and file operations"

    def __init__(self, allowed_env_prefixes: Optional[List[str]] = None, allowed_dirs: Optional[List[str]] = None):
        self.allowed_env_prefixes = allowed_env_prefixes or ["THINKAI_", "APP_", "PATH"]
        self.allowed_dirs = [os.path.abspath(d) for d in (allowed_dirs or ["."])]

    def get_tools(self) -> List[Tool]:
        allowed_env_prefixes = self.allowed_env_prefixes
        allowed_dirs = self.allowed_dirs

        def list_directory(path: str = ".") -> str:
            """List contents of a directory.

            Args:
                path: Directory path to list (must be within allowed directories)
            """
            try:
                abs_path = os.path.abspath(path)
                if not any(abs_path.startswith(d) for d in allowed_dirs):
                    return json.dumps({"error": f"Access denied. Path '{path}' is outside allowed directories."})
                p = Path(abs_path)
                items = []
                for item in p.iterdir():
                    item_type = "dir" if item.is_dir() else "file"
                    items.append({"name": item.name, "type": item_type, "size": item.stat().st_size if item.is_file() else None})
                return json.dumps({"path": str(p), "items": items, "count": len(items)})
            except Exception as e:
                return json.dumps({"error": str(e)})

        def get_system_info() -> str:
            """Get system information.

            Returns:
                JSON string with system info
            """
            import platform
            import os

            info = {
                "platform": platform.system(),
                "release": platform.release(),
                "machine": platform.machine(),
                "processor": platform.processor(),
                "python_version": platform.python_version(),
                "cwd": os.getcwd(),
                "current_time": datetime.now().isoformat(),
            }
            return json.dumps(info)

        def get_env_variable(name: str) -> str:
            """Get an environment variable.

            Args:
                name: Variable name (must start with an allowed prefix)
            """
            if not any(name.startswith(prefix) for prefix in allowed_env_prefixes):
                return json.dumps({"error": f"Access denied. Variable '{name}' does not match any allowed prefix."})
            value = os.environ.get(name)
            if value is None:
                return json.dumps({"error": f"Variable '{name}' not found"})
            return json.dumps({"name": name, "value": value})

        return [
            Tool(name="list_directory", description="List directory contents", func=list_directory),
            Tool(name="get_system_info", description="Get system information", func=get_system_info),
            Tool(name="get_env_variable", description="Get environment variable", func=get_env_variable),
        ]
