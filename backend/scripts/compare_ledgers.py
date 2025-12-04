"""
Script: compare_ledgers.py
Purpose: Compare two agent process ledgers and output differences.
Usage: python backend/scripts/compare_ledgers.py baseline.json compare.json [--detailed]
Why: Debugging tool for identifying behavioral changes in analytics flows.
Part of Phase 6: Observability implementation.
"""

import sys
import json
import argparse
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analytics.core.ledger_diff import compare_ledgers, summarize_differences


def main():
    parser = argparse.ArgumentParser(
        description="Compare two agent process ledgers"
    )
    parser.add_argument(
        "baseline",
        type=Path,
        help="Path to baseline ledger JSON file",
    )
    parser.add_argument(
        "compare",
        type=Path,
        help="Path to comparison ledger JSON file",
    )
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Include detailed field-by-field comparison",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Output path for JSON diff report",
    )
    parser.add_argument(
        "--no-normalize",
        action="store_true",
        help="Disable normalization (compare exact values including timestamps)",
    )
    
    args = parser.parse_args()
    
    # Validate inputs
    if not args.baseline.exists():
        print(f"Error: Baseline file not found: {args.baseline}", file=sys.stderr)
        sys.exit(1)
    
    if not args.compare.exists():
        print(f"Error: Compare file not found: {args.compare}", file=sys.stderr)
        sys.exit(1)
    
    # Perform comparison
    try:
        diff = compare_ledgers(
            args.baseline,
            args.compare,
            normalize=not args.no_normalize,
            detailed=args.detailed,
        )
    except Exception as e:
        print(f"Error comparing ledgers: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Print summary
    print(summarize_differences(diff))
    
    # Export JSON if requested
    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(diff.to_dict(), f, indent=2, default=str)
            print(f"\nDetailed diff exported to: {args.output}")
        except Exception as e:
            print(f"Warning: Failed to write output file: {e}", file=sys.stderr)
    
    # Exit with appropriate code
    sys.exit(0 if diff.identical else 1)


if __name__ == "__main__":
    main()

