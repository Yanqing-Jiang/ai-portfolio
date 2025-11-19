# --- Analytics Function/Class Map ---
# Class: AgentRevisionLaneMissing
#   Role: Signals that an agentic revision run never produced a lane decision or ready card.
#   Called from: analytics.flows.single_agent_tools, analytics.flows.multi_agent
#   Collaborators: analytics.flows.workflow.analytics_memory_workflow, analytics.core.session_state.SessionStateSnapshot
#   Why: Lets revision controllers emit guardrails instead of replaying deterministic planners when agents do not produce revisions.
# --- End Analytics Function/Class Map ---

class AgentRevisionLaneMissing(RuntimeError):
    """Raised when an agentic revision completes without a lane decision or ready event."""

