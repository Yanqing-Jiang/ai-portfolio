# --- Component Validator Function/Class Map ---
# Class: ComponentValidator
#   Role: Validate LLM-generated component selections against catalog and skill schema.
#   Called from: backend.generative_ui.runtime.A2UIRuntime.stream_dashboard
#   Invokes: FinancialCatalog.validate_component
#   Why: Ensures LLM selections are catalog-safe before rendering.
# --- End Component Validator Function/Class Map ---
"""
Validation layer for LLM-generated component selections.

This module validates that LLM widget selections conform to:
1. The component catalog (valid widget types and properties)
2. The skill's data schema (valid data paths)
3. Widget binding rules (correct path-to-property mappings)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Set, Tuple

from .component_selector import DashboardLayout, WidgetSelection
from .skills import A2UISkillMeta
from .a2ui.catalog import get_catalog

logger = logging.getLogger(__name__)


class ComponentValidator:
    """
    Validate LLM-generated component selections against catalog and skill schema.
    
    Class: ComponentValidator - enforces catalog safety for LLM selections.
    Called from: backend.generative_ui.runtime.A2UIRuntime
    Invokes: FinancialCatalog.validate_component, skill schema checks
    Why: Prevents invalid components from being rendered.
    """
    
    def __init__(self):
        """Initialize validator with catalog reference."""
        self.catalog = get_catalog()
    
    def validate_selection(
        self,
        selection: DashboardLayout,
        skill: A2UISkillMeta,
    ) -> Tuple[bool, List[str]]:
        """
        Validate widget selection against catalog and skill constraints.
        
        Method: validate_selection - full validation of LLM selection.
        Called from: backend.generative_ui.runtime.A2UIRuntime.stream_dashboard
        Invokes: _validate_widget_type, _validate_bindings
        Why: Ensures all widgets are valid before component tree generation.
        
        Args:
            selection: LLM-generated dashboard layout
            skill: The skill providing data schema constraints
            
        Returns:
            (is_valid, list_of_errors)
        """
        errors: List[str] = []
        seen_ids: Set[str] = set()
        valid_paths = self._get_valid_paths(skill)
        
        for widget in selection.widgets:
            # Check widget type is in skill's allowed widgets
            if widget.widget_type not in skill.widgets:
                errors.append(
                    f"Widget '{widget.widget_type}' not allowed for skill {skill.skill_id}. "
                    f"Allowed: {skill.widgets}"
                )
                continue
            
            # Check widget type exists in catalog
            if widget.widget_type not in self.catalog.component_names:
                errors.append(f"Unknown widget type: {widget.widget_type}")
                continue
            
            # Check for duplicate widget IDs
            if widget.widget_id in seen_ids:
                errors.append(f"Duplicate widget ID: {widget.widget_id}")
            seen_ids.add(widget.widget_id)
            
            # Validate widget ID format
            if not self._is_valid_widget_id(widget.widget_id):
                errors.append(
                    f"Invalid widget ID '{widget.widget_id}'. "
                    "Must be lowercase with underscores only."
                )
            
            # Validate data bindings
            binding_errors = self._validate_bindings(
                widget,
                skill,
                valid_paths,
            )
            errors.extend(binding_errors)
        
        # Check minimum widget count
        if len(selection.widgets) < 2:
            errors.append("Dashboard must have at least 2 widgets")
        
        # Validate emphasis
        valid_emphasis = {"focus_chart", "focus_table", "focus_news", "balanced", None}
        if selection.emphasis and selection.emphasis not in valid_emphasis:
            errors.append(f"Invalid emphasis: {selection.emphasis}")
        
        is_valid = len(errors) == 0
        
        if not is_valid:
            logger.warning(
                "[VALIDATOR] Selection rejected with %d errors: %s",
                len(errors),
                errors[:3]  # Log first 3 errors
            )
        
        return (is_valid, errors)
    
    def _get_valid_paths(self, skill: A2UISkillMeta) -> Set[str]:
        """
        Extract all valid data paths from skill schema.
        
        Method: _get_valid_paths - flattens skill schema to path set.
        Called from: validate_selection
        Why: Builds lookup set for binding validation.
        """
        paths = set()
        
        # Add top-level paths from data_paths
        for path in skill.data_paths.values():
            paths.add(path)
        
        # Add nested paths from data_schema
        for base_path, schema in skill.data_schema.items():
            paths.add(base_path)
            if isinstance(schema, dict) and "properties" in schema:
                for prop in schema["properties"]:
                    paths.add(f"{base_path}/{prop}")
        
        # Add paths from widget_bindings
        for widget_rules in skill.widget_bindings.values():
            if isinstance(widget_rules, dict):
                for key, value in widget_rules.items():
                    if isinstance(value, list):
                        paths.update(value)
                    elif isinstance(value, str) and value.startswith("/"):
                        paths.add(value)
        
        return paths
    
    def _validate_bindings(
        self,
        widget: WidgetSelection,
        skill: A2UISkillMeta,
        valid_paths: Set[str],
    ) -> List[str]:
        """
        Validate data bindings against skill schema.
        
        Method: _validate_bindings - checks each binding property.
        Called from: validate_selection
        Why: Ensures LLM doesn't bind to non-existent data paths.
        """
        errors: List[str] = []
        widget_rules = skill.widget_bindings.get(widget.widget_type, {})
        
        for prop_name, binding in widget.data_bindings.items():
            if not isinstance(binding, dict):
                continue
            
            # Check if it's a path binding
            if "path" in binding:
                path_value = binding["path"]
                
                # Validate path exists in skill schema
                if path_value not in valid_paths:
                    # Also check if it's a nested path we might have missed
                    path_valid = False
                    for valid in valid_paths:
                        if path_value.startswith(valid + "/") or path_value == valid:
                            path_valid = True
                            break
                    
                    if not path_valid:
                        errors.append(
                            f"{widget.widget_type}.{prop_name}: "
                            f"Invalid path '{path_value}'"
                        )
                
                # Check if path is valid for this specific property
                prop_key = f"valid_{prop_name}_paths"
                if prop_key in widget_rules:
                    allowed_paths = widget_rules[prop_key]
                    if isinstance(allowed_paths, list) and path_value not in allowed_paths:
                        # Log warning but don't fail - schema might be incomplete
                        logger.debug(
                            "Path %s not in recommended paths for %s.%s",
                            path_value, widget.widget_type, prop_name
                        )
            
            elif "literalString" in binding:
                # Literal strings are always valid
                pass
            
            elif "literalNumber" in binding:
                # Literal numbers are always valid
                pass
        
        return errors
    
    def _is_valid_widget_id(self, widget_id: str) -> bool:
        """
        Check if widget ID follows naming conventions.
        
        Method: _is_valid_widget_id - validates ID format.
        Called from: validate_selection
        Why: Ensures consistent widget IDs for DOM references.
        """
        if not widget_id:
            return False
        
        # Must be lowercase with underscores and numbers
        import re
        return bool(re.match(r'^[a-z][a-z0-9_]*$', widget_id))
    
    def sanitize_selection(
        self,
        selection: DashboardLayout,
        skill: A2UISkillMeta,
    ) -> DashboardLayout:
        """
        Sanitize and fix common issues in LLM selection.
        
        Method: sanitize_selection - auto-fixes minor issues.
        Called from: runtime before rendering
        Why: Improves success rate by fixing trivial errors.
        """
        sanitized_widgets = []
        valid_paths = self._get_valid_paths(skill)
        
        for widget in selection.widgets:
            # Skip invalid widget types
            if widget.widget_type not in skill.widgets:
                continue
            
            # Fix widget ID if needed
            widget_id = widget.widget_id
            if not self._is_valid_widget_id(widget_id):
                widget_id = f"{widget.widget_type.lower()}_{len(sanitized_widgets)}"
            
            # Sanitize bindings
            sanitized_bindings = {}
            for prop, binding in widget.data_bindings.items():
                if isinstance(binding, dict):
                    if "path" in binding:
                        path = binding["path"]
                        # Keep path if it looks valid (starts with /data)
                        if path.startswith("/data"):
                            sanitized_bindings[prop] = binding
                    elif "literalString" in binding or "literalNumber" in binding:
                        sanitized_bindings[prop] = binding
            
            sanitized_widgets.append(WidgetSelection(
                widget_type=widget.widget_type,
                widget_id=widget_id,
                data_bindings=sanitized_bindings,
                priority=widget.priority,
            ))
        
        return DashboardLayout(
            widgets=sanitized_widgets,
            emphasis=selection.emphasis if selection.emphasis in 
                {"focus_chart", "focus_table", "focus_news", "balanced"} else "balanced",
            rationale=selection.rationale,
        )


# Singleton instance
_validator: ComponentValidator = None


def get_component_validator() -> ComponentValidator:
    """Get the component validator singleton."""
    global _validator
    if _validator is None:
        _validator = ComponentValidator()
    return _validator


__all__ = [
    "ComponentValidator",
    "get_component_validator",
]
