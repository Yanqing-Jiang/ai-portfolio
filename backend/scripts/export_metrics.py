"""
Script: export_metrics.py
Purpose: Export analytics metrics to JSON for monitoring/dashboards.
Usage: python backend/scripts/export_metrics.py [--output metrics.json] [--reset]
Why: Enables metrics collection for Grafana, CloudWatch, or other monitoring tools.
Part of Phase 6: Observability implementation.
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analytics.core.metrics import get_metrics_collector


def main():
    parser = argparse.ArgumentParser(
        description="Export analytics metrics to JSON"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("metrics.json"),
        help="Output path for metrics JSON file (default: metrics.json)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset metrics after export",
    )
    parser.add_argument(
        "--format",
        choices=["json", "prometheus", "cloudwatch"],
        default="json",
        help="Export format (default: json)",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output",
    )
    
    args = parser.parse_args()
    
    # Get metrics
    collector = get_metrics_collector()
    metrics = collector.get_all_metrics()
    
    if not metrics or (
        not metrics.get("flows") 
        and not metrics.get("lanes") 
        and not metrics.get("tools")
    ):
        print("No metrics collected yet", file=sys.stderr)
        sys.exit(0)
    
    # Format output
    if args.format == "json":
        output = json.dumps(
            metrics,
            indent=2 if args.pretty else None,
            default=str,
        )
    elif args.format == "prometheus":
        output = format_prometheus(metrics)
    elif args.format == "cloudwatch":
        output = json.dumps(
            format_cloudwatch(metrics),
            indent=2 if args.pretty else None,
        )
    else:
        raise ValueError(f"Unknown format: {args.format}")
    
    # Write output
    try:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Metrics exported to: {args.output}")
    except Exception as e:
        print(f"Error writing output: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Print summary
    flow_count = len(metrics.get("flows", {}))
    lane_count = len(metrics.get("lanes", {}))
    tool_count = len(metrics.get("tools", {}))
    
    print(f"\nMetrics Summary:")
    print(f"  Flows: {flow_count}")
    print(f"  Lanes: {lane_count}")
    print(f"  Tools: {tool_count}")
    
    # Reset if requested
    if args.reset:
        collector.reset()
        print("\nMetrics reset")


def format_prometheus(metrics: dict) -> str:
    """Format metrics in Prometheus text format."""
    lines = []
    
    # Flow metrics
    for flow_mode, flow_data in metrics.get("flows", {}).items():
        prefix = f'analytics_flow{{mode="{flow_mode}"}}'
        lines.append(f'# HELP analytics_flow_run_count Total flow runs')
        lines.append(f'# TYPE analytics_flow_run_count counter')
        lines.append(f'{prefix}_run_count {flow_data["run_count"]}')
        lines.append(f'{prefix}_success_count {flow_data["success_count"]}')
        lines.append(f'{prefix}_avg_latency_ms {flow_data["avg_latency_ms"]}')
        lines.append(f'{prefix}_p95_latency_ms {flow_data["p95_latency_ms"]}')
    
    # Lane metrics
    for lane_name, lane_data in metrics.get("lanes", {}).items():
        prefix = f'analytics_lane{{name="{lane_name}"}}'
        lines.append(f'# HELP analytics_lane_execution_count Total lane executions')
        lines.append(f'# TYPE analytics_lane_execution_count counter')
        lines.append(f'{prefix}_execution_count {lane_data["execution_count"]}')
        lines.append(f'{prefix}_success_count {lane_data["success_count"]}')
        lines.append(f'{prefix}_avg_latency_ms {lane_data["avg_latency_ms"]}')
    
    # Tool metrics
    for tool_name, tool_data in metrics.get("tools", {}).items():
        prefix = f'analytics_tool{{name="{tool_name}"}}'
        lines.append(f'# HELP analytics_tool_invocation_count Total tool invocations')
        lines.append(f'# TYPE analytics_tool_invocation_count counter')
        lines.append(f'{prefix}_invocation_count {tool_data["invocation_count"]}')
        lines.append(f'{prefix}_cache_hit_count {tool_data["cache_hit_count"]}')
    
    return "\n".join(lines)


def format_cloudwatch(metrics: dict) -> dict:
    """Format metrics for CloudWatch."""
    metric_data = []
    timestamp = datetime.utcnow().isoformat()
    
    # Flow metrics
    for flow_mode, flow_data in metrics.get("flows", {}).items():
        metric_data.extend([
            {
                "MetricName": "FlowRunCount",
                "Dimensions": [{"Name": "FlowMode", "Value": flow_mode}],
                "Value": flow_data["run_count"],
                "Unit": "Count",
                "Timestamp": timestamp,
            },
            {
                "MetricName": "FlowSuccessRate",
                "Dimensions": [{"Name": "FlowMode", "Value": flow_mode}],
                "Value": flow_data["success_rate"],
                "Unit": "Percent",
                "Timestamp": timestamp,
            },
            {
                "MetricName": "FlowLatency",
                "Dimensions": [{"Name": "FlowMode", "Value": flow_mode}],
                "Value": flow_data["avg_latency_ms"],
                "Unit": "Milliseconds",
                "Timestamp": timestamp,
            },
        ])
    
    return {"MetricData": metric_data, "Namespace": "Analytics"}


if __name__ == "__main__":
    main()

