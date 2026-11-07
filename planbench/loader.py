"""JSON loading and structural validation for plans and tool registries."""

from __future__ import annotations

import json


def _load_json(path: str, what: str) -> object:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except OSError as exc:
        raise SystemExit(f"error: cannot read {what}: {exc}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"error: invalid JSON in {what}: {exc}")


def load_tools(path: str) -> dict[str, dict]:
    """Load a tool registry: {"tools": [{"name", "cost", "failure_rate",
    "produces": [...]}...]}. Returns name -> spec."""
    data = _load_json(path, "tools file")
    if not isinstance(data, dict) or not isinstance(data.get("tools"), list):
        raise SystemExit("error: tools file must be an object with a 'tools' list")
    registry: dict[str, dict] = {}
    for spec in data["tools"]:
        if not isinstance(spec, dict) or not isinstance(spec.get("name"), str):
            raise SystemExit("error: every tool needs a string 'name'")
        name = spec["name"]
        if name in registry:
            raise SystemExit(f"error: duplicate tool name: {name}")
        cost = spec.get("cost", 0.0)
        failure_rate = spec.get("failure_rate", 0.0)
        produces = spec.get("produces", [])
        if not isinstance(cost, (int, float)) or cost < 0:
            raise SystemExit(f"error: tool {name}: cost must be a non-negative number")
        if not isinstance(failure_rate, (int, float)) or not 0 <= failure_rate <= 1:
            raise SystemExit(f"error: tool {name}: failure_rate must be in [0, 1]")
        if not isinstance(produces, list) or not all(isinstance(p, str) for p in produces):
            raise SystemExit(f"error: tool {name}: produces must be a list of strings")
        registry[name] = {"cost": float(cost), "failure_rate": float(failure_rate), "produces": produces}
    return registry


def load_plan(path: str) -> dict:
    """Load a plan: {"name", "steps": [{"id", "tool", "needs": [...],
    "duration", "max_retries"}...]}. Structural type checks only; semantic
    validation lives in validate.py."""
    data = _load_json(path, "plan file")
    if not isinstance(data, dict) or not isinstance(data.get("steps"), list):
        raise SystemExit("error: plan file must be an object with a 'steps' list")
    if not data["steps"]:
        raise SystemExit("error: plan has no steps")
    for step in data["steps"]:
        if not isinstance(step, dict):
            raise SystemExit("error: every step must be an object")
        if not isinstance(step.get("id"), str):
            raise SystemExit("error: every step needs a string 'id'")
        if not isinstance(step.get("tool"), str):
            raise SystemExit(f"error: step {step.get('id')}: needs a string 'tool'")
        duration = step.get("duration", 1.0)
        if not isinstance(duration, (int, float)) or duration <= 0:
            raise SystemExit(f"error: step {step['id']}: duration must be a positive number")
        retries = step.get("max_retries", 0)
        if not isinstance(retries, int) or retries < 0:
            raise SystemExit(f"error: step {step['id']}: max_retries must be a non-negative integer")
        needs = step.get("needs", [])
        if not isinstance(needs, list) or not all(isinstance(n, str) for n in needs):
            raise SystemExit(f"error: step {step['id']}: needs must be a list of step ids")
    return data
