# Prompt Version Registry Inline Plan

## Plan
1. **Confirm current usage**: Inspect `backend\analytics\flows\multi_agent.py:1175` and `backend\analytics\flows\planner_executor.py:4515` where `self._prompt_versions = get_prompt_versions()` seeds telemetry so the exact embedding points are clear. Double-check `_annotate()` hooks at `backend\analytics\flows\multi_agent.py:1992` and `backend\analytics\flows\planner_executor.py:4594`, plus metadata emitted in `_bootstrap_shared_context()` to ensure every consumer stays wired into the new source.
2. **Design inline registries**: Introduce a class-level constant `_PROMPT_VERSIONS = {"schema_clarifier": "2025-10-16", "multi_agent.supervisor": "2025-10-16"}` (or a shared mixin) directly inside each flow, then copy it in `__init__` via `self._prompt_versions = dict(self._PROMPT_VERSIONS)` so downstream annotations keep a defensive snapshot while allowing future extensions by subclassing.
3. **Update dependents**: Replace `from analytics.prompt_versions import get_prompt_versions` imports in `backend\analytics\flows\multi_agent.py`, `backend\analytics\flows\planner_executor.py`, `backend\scripts\seed_agentic_staging.py`, and `backend\tests\analytics\test_prompt_contracts.py` with references to the inlined registry (for example, exposing a `@classmethod def get_prompt_versions(cls)` or reexporting a module-level helper). Ensure test fixtures read from the same source to avoid hard-coded drift and adjust seeding scripts to call the new accessor.
4. **Cleanup removal**: Delete `backend\analytics\prompt_versions.py`, strip any `__all__` references, and run the analytics contract tests (`pytest backend/tests/analytics/test_prompt_contracts.py`) to confirm no lingering import errors or mismatched telemetry payloads.

## Legacy Code Inventory
- `backend\analytics\prompt_versions.py` (module becomes redundant once flows inline the registry).
- Import references expecting `get_prompt_versions()` in:
  - `backend\analytics\flows\multi_agent.py:22`
  - `backend\analytics\flows\planner_executor.py:53`
  - `backend\scripts\seed_agentic_staging.py:24`
  - `backend\tests\analytics\test_prompt_contracts.py:10`
- Any external helper or script relying on `analytics.prompt_versions.get_prompt_versions()` would also be legacy; evaluate consumer code and either migrate to the new class accessor or add a temporary shim if deprecation is needed.
