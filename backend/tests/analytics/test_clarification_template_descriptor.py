from analytics.core.intent_impl.models import FollowUpModel, SlotStatusModel
from analytics.flows.planner.intent_templates import build_template_descriptor


def test_build_template_descriptor_filters_placeholder_slots() -> None:
    followups = [
        FollowUpModel(slot="__any__", prompt="Ignore this", suggestions=["foo"], allow_custom=True),
        FollowUpModel(
            slot="timeframe",
            prompt="Choose timeframe",
            suggestions=["last 5 years", "last 8 quarters"],
            allow_custom=False,
            reason="Needed for trend window",
        ),
    ]
    slot_statuses = {
        "timeframe": SlotStatusModel(status="defaulted", value="last 5 years"),
    }
    descriptor = build_template_descriptor(
        intent_key="margin_growth_vs_peers",
        template={"id": "margin_growth_vs_peers", "name": "Margin Growth vs Peers"},
        followups=followups,
        slot_statuses=slot_statuses,
    )
    assert descriptor is not None
    assert descriptor["intentKey"] == "margin_growth_vs_peers"
    steps = descriptor["steps"]
    assert len(steps) == 1
    step = steps[0]
    assert step["slot"] == "timeframe"
    assert step["control"] == "select"
    option_labels = [option["label"] for option in step["options"]]
    assert option_labels == ["last 5 years", "last 8 quarters"]
    assert step["allowCustom"] is False
    assert step["prefillValue"] == "last 5 years"
