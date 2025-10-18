#!/usr/bin/env python3
"""Report basic slot catalog usage statistics."""
from __future__ import annotations

from collections import Counter

from analytics.core.config import get_configs
from analytics.core.slot_catalog import get_slot_catalog


def main() -> None:
    configs = get_configs()
    catalog = get_slot_catalog(refresh=True)

    intents = catalog.list_intents()
    required_cfg = configs.query_requirements.get('required_slots', {})
    if not isinstance(required_cfg, dict):
        required_cfg = {}

    unused_requirements = sorted(set(required_cfg.keys()) - set(intents))
    missing_requirements = sorted(set(intents) - set(required_cfg.keys()))

    slot_counter: Counter[str] = Counter()
    intents_with_requirements = 0

    print('Slot Catalog Summary')
    print('---------------------')
    print(f"Total intents: {len(intents)}")

    for intent_key in intents:
        definition = catalog.get_intent_definition(intent_key)
        required = definition.required_slots if definition else []
        optional = definition.optional_slots if definition else []
        if required:
            intents_with_requirements += 1
        for slot in required:
            slot_counter[slot] += 1
        print(f"- {intent_key}: required={required or '[]'} optional={optional or '[]'}")

    print()
    print(f"Intents with required slots: {intents_with_requirements}")
    print('Most common required slots:')
    for slot, count in slot_counter.most_common():
        print(f"  - {slot}: {count}")

    if unused_requirements:
        print()
        print('Unmatched entries in query_requirements.yaml:')
        for intent_key in unused_requirements:
            print(f"  - {intent_key}")

    if missing_requirements:
        print()
        print('Intents missing query_requirements entry:')
        for intent_key in missing_requirements:
            print(f"  - {intent_key}")


if __name__ == '__main__':
    main()
