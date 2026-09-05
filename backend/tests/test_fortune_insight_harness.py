"""Chart parity, evidence integrity, timing, and unchanged presentation contracts."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from iztro_py import astro

from fortune.agents import FortuneRunContext, _build_narrative_prompt, run_foundation
from fortune.classics import retrieve_classical_references
from fortune.insight_harness import ReadingBrief, validate_brief, prepare_reading_brief, available_evidence_paths
from fortune.ziwei_engine import compute_ziwei_chart


FIXTURES = json.loads((Path(__file__).parent / "golden/ziwei_iztro_2_6_0.json").read_text())["cases"]


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda f: f["date"])
def test_chart_matches_upstream_major_stars_and_decades(fixture):
    index = fixture["time_index"]
    hour = 0 if index == 0 else index * 2 - 1
    date = "-".join(f"{int(v):02d}" for v in fixture["date"].split("-"))
    gender = "male" if fixture["gender"] == "男" else "female"
    chart = compute_ziwei_chart(f"{date}T{hour:02d}:00:00", "Asia/Shanghai", gender)
    # Translate only labels for comparison; fixtures come from independent JS.
    native = astro.by_solar(date, index, fixture["gender"], language="zh-CN")
    names = {s.name: s.translate_name("zh-CN") for p in native.palaces for s in p.major_stars}
    actual = [
        {"index": p["index"], "body": p["is_body_palace"],
         "decadal_ages": p["decadal_nominal_ages"],
         "stars": [[names[s["name"]], s["brightness"], s["mutagen"]] for s in p["major_stars"]]}
        for p in chart["palaces"]
    ]
    assert actual == fixture["palaces"]


@pytest.mark.parametrize(("hour", "index"), [(0, 0), (1, 1), (2, 1), (21, 11), (22, 11), (23, 12)])
def test_birth_hour_boundaries(hour, index):
    assert compute_ziwei_chart(f"1990-05-15T{hour:02d}:00:00", "UTC", "female")["time_index"] == index


def test_timezone_and_missing_inputs():
    local = compute_ziwei_chart("1990-05-16T00:00:00", "Asia/Shanghai", "female")
    # China observed daylight saving time (+09:00) on this historical date.
    utc = compute_ziwei_chart("1990-05-15T15:00:00Z", "Asia/Shanghai", "female")
    assert local == utc
    assert compute_ziwei_chart("not used", "UTC", "female", True)["reason"] == "birth_time_unknown"
    assert compute_ziwei_chart("not used", "UTC", "unknown")["palaces"] == []


def _payload():
    return {
        "current_year": 2026, "timing_horizon_end": 2036, "birth_year": 1990,
        "notable_annual_pillars": [{"year": 2027, "branch": "卯"}],
        "ten_gods": [{"english": "Direct Officer"}],
        "ziwei": {"status": "computed", "palaces": [{"name": "career"}]},
    }


def _brief():
    return ReadingBrief.model_validate({
        "findings": [{
            "topic": f"Theme {n}", "opportunity": "A larger role", "risk": "Overcommitting",
            "action": "Test scope first", "alternative": "Stay if support is missing",
            "technical_basis": "Annual pressure plus career-palace support",
            "evidence_paths": ["/notable_annual_pillars/0", "/ziwei/palaces/0"],
            "agreement": "convergent", "start_year": 2027, "end_year": 2027,
        } for n in range(3)], "limitations": ["Symbolic interpretation"],
    })


def test_ages_derived_from_calendar_year_not_nominal_ages():
    result = validate_brief(_brief(), _payload())
    assert result["findings"][0]["age_at_birthday"] == [37, 37]
    assert "before birthday" in result["findings"][0]["age_label"]


@pytest.mark.parametrize("mutation", ["invented_path", "unavailable_ziwei"])
def test_rejects_unsupported_claim_evidence(mutation):
    brief, payload = _brief(), _payload()
    finding = brief.findings[0]
    if mutation == "invented_path":
        finding.evidence_paths[0] = "/ten_gods/99"
    elif mutation == "unavailable_ziwei":
        finding.evidence_paths[1] = "/ziwei/status"
    with pytest.raises(ValueError):
        validate_brief(brief, payload)


@pytest.mark.parametrize("mutation", ["uncovered_year", "past_year", "missing_end"])
def test_withholds_entire_unsupported_timed_finding_but_keeps_supported_siblings(mutation):
    brief = _brief()
    if mutation == "uncovered_year": brief.findings[0].end_year = 2028
    elif mutation == "past_year": brief.findings[0].start_year = 2025
    else: brief.findings[0].end_year = None
    result = validate_brief(brief, _payload())
    assert len(result["findings"]) == 2
    assert result["withheld_findings"][0]["topic"] == "Theme 0"
    assert all(f["topic"] != "Theme 0" for f in result["findings"])


def test_source_labels_cannot_claim_unsupported_agreement():
    brief = _brief()
    brief.findings[0].evidence_paths = ["/notable_annual_pillars/0"]
    brief.findings[1].agreement = "bazi_only"
    result = validate_brief(brief, _payload())
    assert result["findings"][0]["agreement"] == "bazi_only"
    assert result["findings"][1]["agreement"] == "mixed"


def test_no_unsupported_findings_can_escape_as_a_successful_reading():
    brief = _brief()
    for finding in brief.findings: finding.end_year = 2028
    with pytest.raises(ValueError, match="No findings"):
        validate_brief(brief, _payload())


def test_retrieval_does_not_invent_similarity_and_matches_stems():
    assert retrieve_classical_references("zzzznonmatching") == []
    assert retrieve_classical_references("geng", limit=1)[0]["id"] == "di_tian_sui_geng"
    assert retrieve_classical_references("庚金", limit=1)[0]["id"] == "di_tian_sui_geng"
    refs = retrieve_classical_references("Will I find a new role this year geng metal seasonal roots")
    assert not any(r["id"] in {"yuan_hai_children", "di_tian_sui_jia", "di_tian_sui_xin"} for r in refs)


def test_enum_addresses_empty_palace_as_a_record_and_preserves_partner_paths():
    payload = _payload()
    payload["ziwei"]["palaces"][0]["major_stars"] = []
    payload["person_b"] = {"enhanced_element_counts": {"wood": 2.0}}
    paths = available_evidence_paths(payload)
    assert "/ziwei/palaces/0" in paths
    assert "/ziwei/palaces/0/major_stars" not in paths
    assert "/person_b/enhanced_element_counts/wood" in paths
    assert validate_brief(_brief(), payload)["findings"]


@pytest.mark.asyncio
async def test_technical_stage_repairs_evidence_once_without_session(monkeypatch):
    import fortune.agents as agents
    import fortune.insight_harness as harness
    bad, good = _brief(), _brief()
    bad.findings[0].evidence_paths[0] = "/ten_gods/99"
    runner = AsyncMock(side_effect=[
        SimpleNamespace(final_output=bad, raw_responses=[]),
        SimpleNamespace(final_output=good, raw_responses=[]),
    ])
    monkeypatch.setattr(harness.Runner, "run", runner)
    monkeypatch.setattr(agents, "_build_narrative_prompt", lambda *_: json.dumps(_payload()))
    foundation = {}
    await prepare_reading_brief(FortuneRunContext(fortune_id="test", surface_id="test"), foundation)
    assert runner.await_count == 2
    assert all("session" not in call.kwargs for call in runner.call_args_list)
    assert foundation["reading_brief"]["findings"][0]["age_at_birthday"] == [37, 37]


@pytest.mark.asyncio
async def test_real_foundation_prompt_keeps_birth_data_before_intent(monkeypatch):
    ctx = FortuneRunContext(fortune_id="test", surface_id="test", birth_iso="1990-05-15T12:00:00",
                           timezone="Asia/Shanghai", gender="female", question="Career?",
                           metadata={"current_year": 2026})
    foundation = await run_foundation(ctx)
    first = _build_narrative_prompt(ctx, foundation)
    ctx.question = "Relationship?"
    second = _build_narrative_prompt(ctx, foundation)
    assert first.split('"question":')[0] == second.split('"question":')[0]
    assert json.loads(first)["ziwei"]["status"] == "computed"


@pytest.mark.asyncio
async def test_stream_snapshot_restores_both_charts_and_brief_after_restart(monkeypatch):
    from fortune.pipeline import _snapshot_pillars, _snapshot_mechanics, _snapshot_references
    from fortune.routes import _hydrate_foundation_from_snapshot
    ctx = FortuneRunContext(fortune_id="test", surface_id="test", birth_iso="1990-05-15T12:00:00",
                           timezone="Asia/Shanghai", gender="female", metadata={"current_year": 2026})
    foundation = await run_foundation(ctx)
    foundation["reading_brief"] = validate_brief(_brief(), _payload())
    foundation["person_b"] = {key: value for key, value in foundation.items() if key != "trace"}
    stored = _snapshot_pillars(None, foundation)
    repo = SimpleNamespace(get_snapshot=AsyncMock(return_value={
        "latest_pillars": stored, "latest_mechanics": _snapshot_mechanics(None, foundation["analysis"]),
        "latest_references": _snapshot_references(foundation),
    }))
    restored = await _hydrate_foundation_from_snapshot(repo, "11111111-1111-1111-1111-111111111111")
    assert restored["ziwei"] == foundation["ziwei"]
    assert restored["person_b"]["ziwei"] == foundation["person_b"]["ziwei"]
    assert restored["reading_brief"] == foundation["reading_brief"]
    assert restored["birth_year"] == 1990
    # Real post-restart JSON shapes must work for a timing Ask, not just a
    # mocked prompt builder fed live Pydantic objects.
    import fortune.agents as agents
    from fortune.triage import run_triage
    assert isinstance(restored["elements"], dict)
    assert all(isinstance(ref, dict) for ref in restored["references"])
    prompt = json.loads(_build_narrative_prompt(ctx, restored))
    supported = prompt["notable_annual_pillars"][0]["year"]
    narrative = agents.EnrichedNarrativeOutput(tldr="Prepare carefully.", insights=[
        agents.InsightSection(id=str(i), icon="•", heading="Prepare", tagline="Stay flexible.",
                             bullets=[agents.InsightBullet(icon="•", text="Define scope."),
                                      agents.InsightBullet(icon="•", text="Measure results.")])
        for i in range(2)
    ], year_predictions=[
        agents.YearPrediction(year=year, prediction="Take a measured step.", confidence=0.9)
        for year in [supported, 2099]
    ])
    monkeypatch.setattr(agents.Runner, "run", AsyncMock(return_value=SimpleNamespace(final_output=narrative, raw_responses=[])))
    answer = await run_triage(ctx, foundation=restored, ask_mode=True)
    assert [p.year for p in answer.year_predictions] == [supported]



def test_ziwei_library_failure_keeps_bazi_reading_available(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("library edge")
    monkeypatch.setattr(astro, "by_solar", fail)
    chart = compute_ziwei_chart("1990-05-15T12:00:00", "UTC", "female")
    assert chart["status"] == "unavailable"
    assert chart["reason"] == "engine_error"
    assert chart["palaces"] == []


def test_final_writer_years_are_bounded_by_computed_records_and_retained_findings(monkeypatch):
    import fortune.agents as agents
    from fortune.insight_harness import validate_narrative_years
    from unittest.mock import MagicMock
    payload = {**_payload(), "luck_pillars": [{"start_year": 2030, "end_year": 2040}]}
    monkeypatch.setattr(agents, "_build_narrative_prompt", lambda *_: json.dumps(payload))
    narrative = agents.EnrichedNarrativeOutput(tldr="Prepare carefully.", insights=[
        agents.InsightSection(id=str(i), icon="•", heading="Prepare", tagline="Stay flexible.",
                             bullets=[agents.InsightBullet(icon="•", text="Define scope."),
                                      agents.InsightBullet(icon="•", text="Measure results.")])
        for i in range(2)
    ], year_predictions=[
        agents.YearPrediction(year=year, prediction="Take a measured step.", confidence=0.9)
        for year in [2025, 2027, 2028, 2029, 2030, 2036, 2037]
    ])
    trace = MagicMock()
    foundation = {"trace": trace, "reading_brief": {"findings": [
        {"start_year": 2029, "end_year": 2029}, {"start_year": None, "end_year": None},
    ]}}
    result = validate_narrative_years(None, foundation, narrative)
    assert [p.year for p in result.year_predictions] == [2027, 2029, 2030, 2036]
    assert len(narrative.year_predictions) == 7  # do not mutate the SDK guardrail input
    trace.add_instant.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["ask", "narrative"])
async def test_final_year_validation_is_applied_to_ask_and_nonstream_writer(monkeypatch, path):
    import fortune.agents as agents
    import fortune.triage as triage
    import fortune.insight_harness as harness
    monkeypatch.setattr(agents, "_build_narrative_prompt", lambda *_: json.dumps(_payload()))
    monkeypatch.setattr(triage, "_build_triage_prompt", lambda *args, **kwargs: "test")
    monkeypatch.setattr(harness, "prepare_reading_brief", AsyncMock())
    narrative = agents.EnrichedNarrativeOutput(tldr="Prepare carefully.", insights=[
        agents.InsightSection(id=str(i), icon="•", heading="Prepare", tagline="Stay flexible.",
                             bullets=[agents.InsightBullet(icon="•", text="Define scope."),
                                      agents.InsightBullet(icon="•", text="Measure results.")])
        for i in range(2)
    ], year_predictions=[
        agents.YearPrediction(year=year, prediction="Take a measured step.", confidence=0.9)
        for year in [2027, 2099]
    ])
    monkeypatch.setattr(agents.Runner, "run", AsyncMock(return_value=SimpleNamespace(final_output=narrative, raw_responses=[])))
    ctx = FortuneRunContext(fortune_id="test", surface_id="test", question="Career?")
    result = await (triage.run_triage(ctx, foundation={}, ask_mode=True) if path == "ask"
                    else agents.run_narrative(ctx, foundation={}))
    assert [p.year for p in result.year_predictions] == [2027]
