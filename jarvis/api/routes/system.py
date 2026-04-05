"""System routes - system info, tasks, and the original Jarvis plugins via API."""

from fastapi import APIRouter, Request
from pydantic import BaseModel

from jarvis.plugins.system_monitor import SystemMonitorPlugin
from jarvis.plugins.task_manager import TaskManagerPlugin

router = APIRouter()
sys_monitor = SystemMonitorPlugin()
task_mgr = TaskManagerPlugin()


@router.get("/status")
async def system_status():
    """Get full system status."""
    return {"report": sys_monitor.handle("system status")}


@router.get("/cpu")
async def cpu_info():
    """Get CPU information."""
    return {"report": sys_monitor.handle("cpu")}


@router.get("/memory")
async def memory_info():
    """Get memory information."""
    return {"report": sys_monitor.handle("memory")}


@router.get("/disk")
async def disk_info():
    """Get disk information."""
    return {"report": sys_monitor.handle("disk")}


@router.get("/uptime")
async def uptime():
    """Get system uptime."""
    return {"report": sys_monitor.handle("uptime")}


# === TASK MANAGEMENT VIA API ===

class TaskCreate(BaseModel):
    content: str


class TaskAction(BaseModel):
    task_id: int


@router.get("/tasks")
async def list_tasks():
    """List all tasks."""
    return {"report": task_mgr.handle("list all tasks")}


@router.post("/tasks")
async def create_task(task: TaskCreate):
    """Create a new task."""
    return {"report": task_mgr.handle(f"add task {task.content}")}


@router.post("/tasks/complete")
async def complete_task(action: TaskAction):
    """Complete a task by ID."""
    return {"report": task_mgr.handle(f"complete task #{action.task_id}")}


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: int):
    """Delete a task by ID."""
    return {"report": task_mgr.handle(f"delete task #{task_id}")}
