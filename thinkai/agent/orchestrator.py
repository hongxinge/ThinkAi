"""多 Agent 协作系统 - Agent 间通信和任务分配"""
from typing import Optional, List, Dict, Any, Callable, Union
from enum import Enum
import asyncio
import json
from datetime import datetime

from thinkai.agent.base import Agent
from thinkai.agent.function_calling import FunctionCallingAgent
from thinkai.core.client import ThinkAI
from thinkai.core.models import ChatMessage
from thinkai.agent.tool import Tool


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentRole(str, Enum):
    """Agent角色"""
    COORDINATOR = "coordinator"  # 协调者
    WORKER = "worker"            # 工作者
    REVIEWER = "reviewer"        # 审核者
    SPECIALIST = "specialist"    # 专家


class Task:
    """协作任务"""

    def __init__(
        self,
        task_id: str,
        description: str,
        assigned_to: str = "",
        status: TaskStatus = TaskStatus.PENDING,
        result: Optional[str] = None,
        error: Optional[str] = None,
        priority: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.task_id = task_id
        self.description = description
        self.assigned_to = assigned_to
        self.status = status
        self.result = result
        self.error = error
        self.priority = priority
        self.metadata = metadata or {}
        self.created_at = datetime.now()
        self.completed_at = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "description": self.description,
            "assigned_to": self.assigned_to,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "priority": self.priority,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class AgentNode:
    """Agent节点 - 封装一个Agent及其运行时信息"""

    def __init__(
        self,
        agent: Agent,
        role: AgentRole = AgentRole.WORKER,
        capabilities: Optional[List[str]] = None,
        description: str = "",
    ):
        self.agent = agent
        self.role = role
        self.capabilities = capabilities or []
        self.description = description
        self.task_count = 0
        self.success_count = 0
        self.is_available = True

    async def execute_task(self, task: Task) -> str:
        """执行任务"""
        self.task_count += 1
        self.is_available = False
        try:
            result = await self.agent.run(task.description)
            self.success_count += 1
            return result
        except Exception as e:
            return f"Error: {str(e)}"
        finally:
            self.is_available = True


class MultiAgentOrchestrator:
    """
    多 Agent 编排器 - 协调多个 Agent 协作

    工作模式:
    1. Sequential: 顺序执行, 一个 Agent 的输出作为下一个的输入
    2. Parallel: 并行执行, 多个 Agent 同时处理不同任务
    3. Hierarchical: 层级执行, 协调者分配任务给工作者

    使用示例:
        orchestrator = MultiAgentOrchestrator(ai_client=ai)

        orchestrator.add_agent(
            agent=search_agent,
            role=AgentRole.SPECIALIST,
            capabilities=["search", "research"],
        )

        orchestrator.add_agent(
            agent=writer_agent,
            role=AgentRole.WORKER,
            capabilities=["writing", "summarization"],
        )

        result = await orchestrator.run(
            task="搜索并总结AI的最新进展",
            mode="sequential",
        )
    """

    def __init__(
        self,
        ai_client: Optional[ThinkAI] = None,
        system_prompt: Optional[str] = None,
        max_parallel_tasks: int = 5,
    ):
        self.ai_client = ai_client
        self.agents: Dict[str, AgentNode] = {}
        self.task_queue: List[Task] = []
        self.task_results: Dict[str, str] = {}
        self.max_parallel_tasks = max_parallel_tasks
        self.system_prompt = system_prompt or "You are a coordinator that manages multiple agents to complete complex tasks."

        # 创建协调者 Agent
        self.coordinator: Optional[FunctionCallingAgent] = None

    def add_agent(
        self,
        agent: Agent,
        role: AgentRole = AgentRole.WORKER,
        capabilities: Optional[List[str]] = None,
        description: str = "",
        name: Optional[str] = None,
    ) -> str:
        """添加 Agent 到编排器"""
        agent_name = name or agent.name
        self.agents[agent_name] = AgentNode(
            agent=agent,
            role=role,
            capabilities=capabilities or [],
            description=description,
        )
        return agent_name

    def remove_agent(self, name: str) -> bool:
        """移除 Agent"""
        if name in self.agents:
            del self.agents[name]
            return True
        return False

    def get_available_agents(self, capability: Optional[str] = None) -> List[str]:
        """获取可用的 Agent"""
        available = []
        for name, node in self.agents.items():
            if node.is_available and node.role != AgentRole.COORDINATOR:
                if capability is None or capability in node.capabilities:
                    available.append(name)
        return available

    def _create_coordinator(self):
        """创建协调者 Agent"""
        if self.coordinator is None and self.ai_client:
            self.coordinator = FunctionCallingAgent(
                name="coordinator",
                ai_client=self.ai_client,
                system_prompt=self.system_prompt,
            )

    async def run_sequential(
        self,
        tasks: List[Union[str, Task]],
        agent_order: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """
        顺序执行模式

        Args:
            tasks: 任务列表
            agent_order: Agent 执行顺序

        Returns:
            任务结果字典
        """
        results = {}
        previous_result = ""

        for i, task in enumerate(tasks):
            if isinstance(task, str):
                task = Task(task_id=f"task_{i}", description=task)

            # 选择 Agent
            if agent_order and i < len(agent_order):
                agent_name = agent_order[i]
            else:
                available = self.get_available_agents()
                if not available:
                    results[task.task_id] = "No available agents"
                    continue
                agent_name = available[0]

            agent_node = self.agents.get(agent_name)
            if not agent_node:
                results[task.task_id] = f"Agent '{agent_name}' not found"
                continue

            # 如果任务依赖前一个结果,更新描述
            if previous_result and "{previous_result}" in task.description:
                task.description = task.description.replace("{previous_result}", previous_result)

            task.status = TaskStatus.RUNNING
            task.assigned_to = agent_name

            result = await agent_node.execute_task(task)
            task.result = result
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()

            results[task.task_id] = result
            previous_result = result

        return results

    async def run_parallel(
        self,
        tasks: List[Union[str, Task]],
    ) -> Dict[str, str]:
        """
        并行执行模式

        Args:
            tasks: 任务列表

        Returns:
            任务结果字典
        """
        results = {}

        # 创建异步任务
        async def execute_one(task: Task, agent_name: str) -> tuple:
            agent_node = self.agents.get(agent_name)
            if not agent_node:
                return task.task_id, f"Agent '{agent_name}' not found"

            task.status = TaskStatus.RUNNING
            task.assigned_to = agent_name

            result = await agent_node.execute_task(task)
            task.result = result
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()

            return task.task_id, result

        # 分配任务到可用 Agent
        coroutines = []
        available_agents = self.get_available_agents()
        if not available_agents:
            return {"error": "No available agents"}

        for i, task in enumerate(tasks):
            if isinstance(task, str):
                task = Task(task_id=f"task_{i}", description=task)

            agent_name = available_agents[i % len(available_agents)]
            coroutines.append(execute_one(task, agent_name))

        # 并行执行
        task_results = await asyncio.gather(*coroutines)
        for task_id, result in task_results:
            results[task_id] = result

        return results

    async def run_hierarchical(
        self,
        task: str,
        decompose_prompt: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        层级执行模式 - 协调者分解任务并分配

        Args:
            task: 总任务描述
            decompose_prompt: 任务分解的额外提示

        Returns:
            任务结果字典
        """
        self._create_coordinator()
        if not self.coordinator:
            return {"error": "Coordinator not available"}

        # 协调者分解任务
        available_agents_info = json.dumps([
            {"name": name, "capabilities": node.capabilities}
            for name, node in self.agents.items()
            if node.is_available
        ], ensure_ascii=False)

        decomposition_prompt = f"""
You are a task coordinator. Break down the following task into subtasks and assign them to appropriate agents.

Available agents:
{available_agents_info}

Main task: {task}

{decompose_prompt or ''}

Please respond with a JSON array of subtasks in this format:
[
    {{"agent": "agent_name", "task": "subtask description", "depends_on": null or previous_task_index}}
]

Only output valid JSON, no other text.
"""

        try:
            decomposition_response = await self.coordinator.run(decomposition_prompt)
            subtasks = json.loads(decomposition_response)
            if not isinstance(subtasks, list):
                subtasks = [{"agent": list(self.agents.keys())[0], "task": task}]
        except Exception:
            subtasks = [{"agent": list(self.agents.keys())[0], "task": task}]

        # 执行子任务
        results = {}
        task_results_cache = []

        for i, subtask in enumerate(subtasks):
            agent_name = subtask.get("agent", "")
            task_desc = subtask.get("task", "")

            # 替换依赖结果
            for cache in task_results_cache:
                task_desc = task_desc.replace(f"{{{cache['index']}}}", cache["result"])

            task_obj = Task(task_id=f"subtask_{i}", description=task_desc)
            task_obj.assigned_to = agent_name

            agent_node = self.agents.get(agent_name)
            if not agent_node:
                results[f"subtask_{i}"] = f"Agent '{agent_name}' not found"
                continue

            result = await agent_node.execute_task(task_obj)
            task_obj.result = result
            task_obj.status = TaskStatus.COMPLETED

            results[f"subtask_{i}"] = result
            task_results_cache.append({"index": i, "result": result})

        # 协调者汇总结果
        summary_prompt = f"""
Please summarize the results of all subtasks:

{json.dumps(results, ensure_ascii=False, indent=2)}

Provide a comprehensive final answer.
"""

        try:
            summary = await self.coordinator.run(summary_prompt)
            results["_summary"] = summary
        except Exception as e:
            results["_summary"] = f"Error generating summary: {str(e)}"

        return results

    async def run(
        self,
        task: Union[str, List[str]],
        mode: str = "hierarchical",
        agent_order: Optional[List[str]] = None,
        decompose_prompt: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        运行多 Agent 协作

        Args:
            task: 任务描述或任务列表
            mode: 执行模式 (sequential, parallel, hierarchical)
            agent_order: Agent 执行顺序 (仅 sequential 模式需要)
            decompose_prompt: 任务分解提示 (仅 hierarchical 模式需要)

        Returns:
            任务结果字典
        """
        if isinstance(task, str):
            task = [task]

        if mode == "sequential":
            tasks = [Task(task_id=f"task_{i}", description=t) for i, t in enumerate(task)]
            return await self.run_sequential(tasks, agent_order=agent_order)
        elif mode == "parallel":
            tasks = [Task(task_id=f"task_{i}", description=t) for i, t in enumerate(task)]
            return await self.run_parallel(tasks)
        elif mode == "hierarchical":
            return await self.run_hierarchical(task[0], decompose_prompt=decompose_prompt)
        else:
            raise ValueError(f"Unknown mode: {mode}. Use 'sequential', 'parallel', or 'hierarchical'")

    def get_status(self) -> Dict[str, Any]:
        """获取编排器状态"""
        return {
            "agents": {
                name: {
                    "role": node.role.value,
                    "capabilities": node.capabilities,
                    "available": node.is_available,
                    "task_count": node.task_count,
                    "success_count": node.success_count,
                }
                for name, node in self.agents.items()
            },
            "task_queue_size": len(self.task_queue),
            "completed_tasks": len(self.task_results),
        }
