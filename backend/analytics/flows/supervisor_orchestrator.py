from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from agents import Agent
from agents.tool import Tool


@dataclass(frozen=True)
class SupervisorSpecialistConfig:
    """Configuration for a specialist that will be exposed as a supervisor tool."""

    lane: str
    name: str
    instructions: str
    description: Optional[str] = None
    model: Optional[str] = None
    reasoning_effort: Optional[str] = None
    max_turns: Optional[int] = None


@dataclass
class SupervisorToolBinding:
    lane: str
    tool_name: str
    tool: Tool
    agent: Agent


@dataclass
class SupervisorBundle:
    supervisor: Agent
    tools: Dict[str, Tool]
    bindings: List[SupervisorToolBinding]


def build_supervisor_bundle(
    *,
    supervisor_name: str,
    supervisor_instructions: str,
    model: str,
    reasoning_effort: Optional[str],
    max_turns: Optional[int],
    specialist_configs: Sequence[SupervisorSpecialistConfig],
) -> SupervisorBundle:
    """Build the supervisor Agent and expose specialists as callable tools."""

    tool_bindings: List[SupervisorToolBinding] = []
    tool_map: Dict[str, Tool] = {}

    for specialist in specialist_configs:
        specialist_agent = Agent(
            name=f"{supervisor_name}_{specialist.lane}",
            instructions=specialist.instructions,
            model=specialist.model or model,
        )
        tool_name = f"{specialist.lane}_specialist"
        description = specialist.description or f"{specialist.lane} specialist tool"
        max_turns_override = specialist.max_turns if specialist.max_turns is not None else max_turns
        tool = specialist_agent.as_tool(
            tool_name=tool_name,
            tool_description=description,
            max_turns=max_turns_override,
        )
        tool_map[specialist.lane] = tool
        tool_bindings.append(
            SupervisorToolBinding(
                lane=specialist.lane,
                tool_name=tool_name,
                tool=tool,
                agent=specialist_agent,
            )
        )

    supervisor_agent = Agent(
        name=supervisor_name,
        instructions=supervisor_instructions,
        model=model,
        tools=list(tool_map.values()),
    )

    return SupervisorBundle(supervisor=supervisor_agent, tools=tool_map, bindings=tool_bindings)
