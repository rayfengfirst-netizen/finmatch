"""
注册脚本 ID 与可导入模块路径。新增财务脚本时在此登记。
模块需实现: def run(payload: dict) -> dict
"""

from typing import Callable

# script_id -> "package.module:function_name" 或仅模块（默认函数名 run）
SCRIPT_REGISTRY: dict[str, str] = {
    "demo_echo": "demo_echo:run",
    "monthly_statement": "monthly_statement:run",
}


def resolve_runner(script_id: str) -> Callable[..., dict]:
    from importlib import import_module

    if script_id not in SCRIPT_REGISTRY:
        raise KeyError(f"未知任务类型: {script_id}")

    target = SCRIPT_REGISTRY[script_id]
    if ":" in target:
        mod_path, fn_name = target.split(":", 1)
    else:
        mod_path, fn_name = target, "run"

    mod = import_module(mod_path)
    fn = getattr(mod, fn_name)
    if not callable(fn):
        raise TypeError(f"{target} 不是可调用对象")
    return fn
