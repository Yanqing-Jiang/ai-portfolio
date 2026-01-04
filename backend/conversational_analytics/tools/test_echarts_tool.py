"""Tests for ECharts tool generation."""
import pytest
from conversational_analytics.tools.echarts_tool import (
    generate_echarts_spec,
    execute_echarts_tool,
    ECHARTS_TOOL_DEFINITION,
)


class TestEchartsToolDefinition:
    """Tests for the ECharts tool definition schema."""

    def test_tool_definition_has_required_fields(self):
        """Verify tool definition has name, description, and input_schema."""
        assert ECHARTS_TOOL_DEFINITION["name"] == "generate_echarts"
        assert "description" in ECHARTS_TOOL_DEFINITION
        assert "input_schema" in ECHARTS_TOOL_DEFINITION

    def test_required_properties(self):
        """Verify required properties in schema."""
        required = ECHARTS_TOOL_DEFINITION["input_schema"]["required"]
        assert "chart_type" in required
        assert "data" in required
        assert "x_field" in required
        assert "y_field" in required


class TestGenerateEchartsSpec:
    """Tests for generate_echarts_spec function."""

    def test_bar_chart_single_series(self):
        """Test simple bar chart generation."""
        data = [
            {"ticker": "NVDA", "revenue": 26_974_000_000},
            {"ticker": "AMD", "revenue": 22_680_000_000},
            {"ticker": "INTC", "revenue": 54_228_000_000},
        ]
        
        result = generate_echarts_spec(
            chart_type="bar",
            data=data,
            x_field="ticker",
            y_field="revenue",
            title="Revenue Comparison",
        )
        
        assert result["title"]["text"] == "Revenue Comparison"
        assert "xAxis" in result
        assert result["xAxis"]["data"] == ["NVDA", "AMD", "INTC"]  # Preserves input order
        assert "yAxis" in result
        assert len(result["series"]) == 1
        assert result["series"][0]["type"] == "bar"

    def test_line_chart_with_series_field(self):
        """Test line chart with multiple series (grouped by ticker)."""
        data = [
            {"year": "2021", "ticker": "NVDA", "margin": 0.25},
            {"year": "2022", "ticker": "NVDA", "margin": 0.30},
            {"year": "2021", "ticker": "AMD", "margin": 0.20},
            {"year": "2022", "ticker": "AMD", "margin": 0.22},
        ]
        
        result = generate_echarts_spec(
            chart_type="line",
            data=data,
            x_field="year",
            y_field="margin",
            series_field="ticker",
            title="Margin Trend",
            value_unit="percentage",
        )
        
        assert result["title"]["text"] == "Margin Trend"
        assert len(result["series"]) == 2  # NVDA and AMD
        assert result["xAxis"]["data"] == ["2021", "2022"]
        # Check that value_meta was set for percentage
        assert result["value_meta"]["unit"] == "percentage"
        assert result["value_meta"]["suffix"] == "%"

    def test_pie_chart(self):
        """Test pie chart aggregation."""
        data = [
            {"company": "NVDA", "share": 40},
            {"company": "AMD", "share": 25},
            {"company": "INTC", "share": 35},
        ]
        
        result = generate_echarts_spec(
            chart_type="pie",
            data=data,
            x_field="company",
            y_field="share",
            title="Market Share",
        )
        
        assert result["series"][0]["type"] == "pie"
        assert len(result["series"][0]["data"]) == 3

    def test_area_chart(self):
        """Test area chart has areaStyle."""
        data = [
            {"quarter": "Q1", "value": 100},
            {"quarter": "Q2", "value": 120},
        ]
        
        result = generate_echarts_spec(
            chart_type="area",
            data=data,
            x_field="quarter",
            y_field="value",
        )
        
        assert result["series"][0]["type"] == "line"
        assert "areaStyle" in result["series"][0]

    def test_empty_data_returns_empty_series(self):
        """Test that empty data returns a valid but empty chart."""
        result = generate_echarts_spec(
            chart_type="bar",
            data=[],
            x_field="x",
            y_field="y",
        )
        
        assert result["series"] == []

    def test_value_unit_millions_usd(self):
        """Test value_unit formatting for millions USD."""
        data = [{"q": "Q1", "revenue": 10_000_000_000}]  # 10 billion
        
        result = generate_echarts_spec(
            chart_type="bar",
            data=data,
            x_field="q",
            y_field="revenue",
            value_unit="millions_usd",
        )
        
        # Should auto-upgrade to billions when values are >= 10B
        assert result["value_meta"]["unit"] == "billions_usd"
        assert result["value_meta"]["suffix"] == "B"

    def test_value_unit_auto_infer_from_field_name(self):
        """Test value_unit is inferred from field name containing 'margin'."""
        data = [{"q": "Q1", "net_margin": 0.25}]
        
        result = generate_echarts_spec(
            chart_type="bar",
            data=data,
            x_field="q",
            y_field="net_margin",
        )
        
        assert result["value_meta"]["unit"] == "percentage"


class TestExecuteEchartsTool:
    """Tests for the async execute_echarts_tool function."""

    @pytest.mark.asyncio
    async def test_execute_success(self):
        """Test successful chart execution."""
        data = [
            {"year": "2023", "value": 100},
            {"year": "2024", "value": 150},
        ]
        
        result = await execute_echarts_tool(
            chart_type="bar",
            data=data,
            x_field="year",
            y_field="value",
            title="Test Chart",
        )
        
        assert result["success"] is True
        assert "config" in result
        assert result["chart_type"] == "bar"

    @pytest.mark.asyncio
    async def test_execute_with_empty_data(self):
        """Test chart generation with empty data still succeeds."""
        result = await execute_echarts_tool(
            chart_type="line",
            data=[],
            x_field="x",
            y_field="y",
        )
        
        # Empty data should still succeed (returns empty chart spec)
        assert result["success"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
