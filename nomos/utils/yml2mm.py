#!/usr/bin/env python3
"""
Enhanced YAML to Mermaid Flowchart Converter.

This script converts config.agent.yaml files into well-organized Mermaid flowchart diagrams.
It analyzes the agent configuration and generates a visual representation with better
categorization, styling, and flow organization.

Usage:
    python yaml_to_mermaid.py [input_file] [--output output_file] [--summary] [--style]

Example:
    python yaml_to_mermaid.py config.agent.yaml --output flowchart.md --summary --style
"""

import argparse
import datetime
import json
import re
from typing import Any, Dict, List, Set

import yaml

from .logging import log_error, log_info


def sanitize_node_id(node_id: str) -> str:
    """Sanitize node ID for Mermaid diagram."""
    # Handle Mermaid reserved keywords
    # Use dictionary lookup for reserved keywords
    reserved_keywords = {
        "end": "end_step",
        "start": "start_step",
        "class": "class_step",
        "style": "style_step",
    }

    if node_id in reserved_keywords:
        return reserved_keywords[node_id]

    # Replace non-alphanumeric characters with underscores
    sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", node_id)

    # Ensure it starts with a letter or underscore
    if sanitized and sanitized[0].isdigit():
        sanitized = "step_" + sanitized

    return sanitized


def truncate_text(text: str, max_length: int = 35) -> str:
    """Truncate text to fit in diagram nodes."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def format_description(description: str) -> str:
    """Format description for display in nodes."""
    # Clean up the description
    description = re.sub(r"\s+", " ", description.strip())

    # Extract key concepts for better readability
    if "greet" in description.lower() and (
        "customer" in description.lower() or "hello" in description.lower()
    ):
        return "Greet Customer"
    elif "take" in description.lower() and "order" in description.lower():
        return "Take Coffee Order"
    elif "finalize" in description.lower() and "order" in description.lower():
        return "Finalize Order"
    elif "clear" in description.lower() and "cart" in description.lower():
        return "Clear Cart & End"
    elif "budget" in description.lower():
        return "Budget Planning"
    elif "expense" in description.lower() and "track" in description.lower():
        return "Track Expenses"
    elif "savings" in description.lower():
        return "Savings Goals"
    elif "financial health" in description.lower():
        return "Financial Health Check"
    elif (
        description.lower().strip().startswith("end ")
        or "end the conversation" in description.lower()
    ):
        return "End Session"

    # Fall back to first sentence
    sentences = description.split(".")
    if len(sentences) > 0:
        first_sentence = sentences[0].strip()
        return truncate_text(first_sentence, 35)

    return truncate_text(description, 35)


def get_node_class(step: Dict[str, Any]) -> str:
    """Determine the CSS class for a node based on its properties."""
    step_id = step.get("step_id", "")
    description = step.get("description", "").lower()
    tools = step.get("available_tools", [])

    if step_id == "end":
        return "endStyle"
    elif step_id == "greet" or "greet" in description:
        return "startStyle"
    elif "budget" in description or "calculate_budget" in tools:
        return "budgetStyle"
    elif "expense" in description or any("expense" in tool for tool in tools):
        return "expenseStyle"
    elif "savings" in description or "set_savings_goal" in tools:
        return "savingsStyle"
    elif "financial_health" in description or "get_financial_health" in tools:
        return "healthStyle"
    elif tools:
        return "toolStyle"
    else:
        return "processStyle"


def parse_yaml_config(file_path: str) -> Dict[str, Any]:
    """Parse the YAML configuration file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        log_error(f"Error: File '{file_path}' not found.")
        raise
    except yaml.YAMLError as e:
        log_error(f"Error parsing YAML: {e}")
        raise ValueError(f"Error parsing YAML: {e}")


def generate_mermaid_flowchart(config: Dict[str, Any], include_styling: bool = True) -> str:
    """Generate enhanced Mermaid flowchart from config."""
    steps = config.get("steps", [])
    flows = config.get("flows", [])
    start_step = config.get("start_step_id", "start")
    agent_name = config.get("name", "Agent")

    mermaid_lines = [
        "flowchart TD",
        f"    %% {agent_name.title().replace('_', ' ')} Agent Flow",
        "",
    ]

    # Add start node
    start_node = sanitize_node_id(start_step)
    mermaid_lines.append(f'    START(["🚀 Start"]) --> {start_node}')
    mermaid_lines.append("")

    # Build flow mappings for step categorization
    flow_step_mapping: Dict[str, List[str]] = {}
    flow_info = {}

    for flow in flows:
        flow_id = flow["flow_id"]
        flow_info[flow_id] = {
            "description": flow.get("description", flow_id),
            "enters": flow.get("enters", []),
            "exits": flow.get("exits", []),
        }

        # Map all steps that belong to this flow
        enter_steps = flow.get("enters", [])
        exit_steps = flow.get("exits", [])

        for step_id in enter_steps + exit_steps:
            if step_id not in flow_step_mapping:
                flow_step_mapping[step_id] = []
            flow_step_mapping[step_id].append(flow_id)

    # If we have flows, organize by subgraphs
    if flows:
        # Track which steps have been added to avoid duplicates
        added_steps = set()

        # Create subgraphs for each flow
        for flow_id, flow_data in flow_info.items():
            flow_description = flow_data["description"]
            mermaid_lines.append(f'    subgraph {flow_id}_flow ["{flow_description}"]')

            # Find all steps that belong to this flow
            flow_steps = []

            # Add enter steps (these are unique to each flow)
            for step in steps:
                step_id = step["step_id"]
                if step_id in flow_data["enters"] and step_id not in added_steps:
                    flow_steps.append(step)
                    added_steps.add(step_id)

            # Add exit steps only if they haven't been added to another flow yet
            for step in steps:
                step_id = step["step_id"]
                if step_id in flow_data["exits"] and step_id not in added_steps:
                    flow_steps.append(step)
                    added_steps.add(step_id)

            # Add steps to subgraph
            for step in flow_steps:
                step_id = step["step_id"]
                sanitized_id = sanitize_node_id(step_id)
                description = format_description(step.get("description", ""))
                tools = step.get("available_tools", [])
                node_class = get_node_class(step)

                # Create node definition with icons
                if node_class == "endStyle":
                    mermaid_lines.append(f'        {sanitized_id}(["🏁 {description}"])')
                elif node_class == "startStyle":
                    mermaid_lines.append(f'        {sanitized_id}["👋 {description}"]')
                elif tools:
                    tool_icons = "🛠️" if tools else ""
                    mermaid_lines.append(f'        {sanitized_id}["{tool_icons} {description}"]')
                else:
                    mermaid_lines.append(f'        {sanitized_id}["{description}"]')

            mermaid_lines.append("    end")
            mermaid_lines.append("")

        # Add any steps not in flows
        orphan_steps = []
        for step in steps:
            step_id = step["step_id"]
            if step_id not in flow_step_mapping and step_id not in added_steps:
                orphan_steps.append(step)

        if orphan_steps:
            mermaid_lines.append("    %% Independent Steps")
            for step in orphan_steps:
                step_id = step["step_id"]
                sanitized_id = sanitize_node_id(step_id)
                description = format_description(step.get("description", ""))
                tools = step.get("available_tools", [])
                node_class = get_node_class(step)

                # Create node definition with icons
                if node_class == "endStyle":
                    mermaid_lines.append(f'    {sanitized_id}(["🏁 {description}"])')
                elif node_class == "startStyle":
                    mermaid_lines.append(f'    {sanitized_id}["👋 {description}"]')
                elif tools:
                    tool_icons = "🛠️" if tools else ""
                    mermaid_lines.append(f'    {sanitized_id}["{tool_icons} {description}"]')
                else:
                    mermaid_lines.append(f'    {sanitized_id}["{description}"]')
            mermaid_lines.append("")

    else:
        # Fallback to original categorization when no flows are defined
        # Organize steps by category
        categorized_steps: dict = {"start": [], "core": [], "end": []}

        for step in steps:
            node_class = get_node_class(step)
            if node_class in ["start"]:
                categorized_steps["start"].append(step)
            elif node_class in ["end"]:
                categorized_steps["end"].append(step)
            else:
                categorized_steps["core"].append(step)

        # Process steps by category
        for category, category_steps in categorized_steps.items():
            if not category_steps:
                continue

            if category == "start":
                mermaid_lines.append("    %% Entry Point")
            elif category == "core":
                mermaid_lines.append("    %% Core Functions")
            elif category == "end":
                mermaid_lines.append("    %% Session End")

            for step in category_steps:
                step_id = step["step_id"]
                sanitized_id = sanitize_node_id(step_id)
                description = format_description(step.get("description", ""))
                tools = step.get("available_tools", [])
                node_class = get_node_class(step)

                # Create node definition with icons
                if node_class == "end":
                    mermaid_lines.append(f'    {sanitized_id}(["🏁 {description}"])')
                elif node_class == "start":
                    mermaid_lines.append(f'    {sanitized_id}["👋 {description}"]')
                elif tools:
                    tool_text = " ".join([f"🛠️ {tool}" for tool in tools])
                    mermaid_lines.append(f'    {sanitized_id}["{tool_text} {description}"]')
                else:
                    mermaid_lines.append(f'    {sanitized_id}["{description}"]')

            mermaid_lines.append("")

    # Add routing connections
    mermaid_lines.append("    %% Flow Connections")
    for step in steps:
        step_id = step["step_id"]
        sanitized_id = sanitize_node_id(step_id)
        routes = step.get("routes", [])

        for route in routes:
            target = route["target"]
            condition = route.get("condition", "")
            sanitized_target = sanitize_node_id(target)

            # Simplify condition text
            if condition:
                # Extract key words from condition
                condition = condition.replace("User wants ", "")
                condition = condition.replace("User ", "")
                condition = condition.replace(" or ", "/")
                condition_text = truncate_text(condition, 25)
                mermaid_lines.append(f"    {sanitized_id} -->|{condition_text}| {sanitized_target}")
            else:
                mermaid_lines.append(f"    {sanitized_id} --> {sanitized_target}")

    # Add styling if requested
    if include_styling:
        mermaid_lines.extend(
            [
                "",
                "    %% Styling",
                "    classDef startStyle fill:#e3f2fd,stroke:#1976d2,stroke-width:3px,color:#000,font-weight:bold",
                "    classDef budgetStyle fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px,color:#000",
                "    classDef expenseStyle fill:#e8f5e8,stroke:#388e3c,stroke-width:2px,color:#000",
                "    classDef savingsStyle fill:#fff3e0,stroke:#f57c00,stroke-width:2px,color:#000",
                "    classDef healthStyle fill:#fce4ec,stroke:#c2185b,stroke-width:2px,color:#000",
                "    classDef endStyle fill:#ffebee,stroke:#d32f2f,stroke-width:3px,color:#000,font-weight:bold",
                "    classDef toolStyle fill:#f0f4c3,stroke:#827717,stroke-width:2px,color:#000",
                "    classDef processStyle fill:#f5f5f5,stroke:#616161,stroke-width:2px,color:#000",
                "",
                "    class START startStyle",
            ]
        )

        # Apply classes to nodes
        for step in steps:
            step_id = sanitize_node_id(step["step_id"])
            node_class = get_node_class(step)
            mermaid_lines.append(f"    class {step_id} {node_class}")

    return "\n".join(mermaid_lines)


def generate_summary(config: Dict[str, Any]) -> str:
    """Generate a text summary of the agent configuration."""
    name = config.get("name", "Unknown Agent")
    persona = config.get("persona", "No persona defined")
    steps = config.get("steps", [])
    flows = config.get("flows", [])

    # Count tools and routes
    all_tools = set()
    total_routes = 0
    for step in steps:
        tools = step.get("available_tools", [])
        all_tools.update(tools)
        total_routes += len(step.get("routes", []))

    summary_lines = [
        f"# 🤖 Agent Summary: {name.title().replace('_', ' ')}",
        "",
        "## 📋 Overview",
        f"- **Agent Name**: {name}",
        f"- **Total Steps**: {len(steps)}",
        f"- **Total Flows**: {len(flows)}",
        f"- **Start Step**: {config.get('start_step_id', 'Not specified')}",
        f"- **Total Routes**: {total_routes}",
        f"- **Available Tools**: {len(all_tools)}",
        "",
        "## 👤 Persona",
        persona.strip(),
        "",
    ]

    # Add flows section if flows exist
    if flows:
        summary_lines.extend(["## 🔄 Flows"])
        for flow in flows:
            flow_id = flow["flow_id"]
            description = flow.get("description", "No description")
            enters = ", ".join(flow.get("enters", []))
            exits = ", ".join(flow.get("exits", []))

            summary_lines.extend(
                [
                    f"### {flow_id}",
                    f"**Description**: {description}",
                    f"**Enter Steps**: {enters or 'None'}",
                    f"**Exit Steps**: {exits or 'None'}",
                    "",
                ]
            )

    summary_lines.extend(["## 🛠️ Tools"])

    if all_tools:
        for tool in sorted(all_tools):
            summary_lines.append(f"- `{tool}`")
    else:
        summary_lines.append("- No tools defined")

    summary_lines.extend(["", "## 📊 Flow Steps"])

    for step in steps:
        step_id = step["step_id"]
        description = step.get("description", "No description")
        tools = step.get("available_tools", [])
        routes = step.get("routes", [])

        # Get first line of description
        first_line = description.split(".")[0].strip()

        summary_lines.extend(
            [
                f"### {step_id}",
                f"**Purpose**: {first_line}",
                f"**Tools**: {', '.join(tools) if tools else 'None'}",
                f"**Routes**: {len(routes)} paths",
                "",
            ]
        )

    return "\n".join(summary_lines)


def generate_config_json(config: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a JSON representation of the agent configuration with enhanced metadata."""
    steps = config.get("steps", [])
    flows = config.get("flows", [])
    start_step = config.get("start_step_id", "start")
    name = config.get("name", "Unknown Agent")
    persona = config.get("persona", "No persona defined")

    # Count tools and routes
    all_tools: Set[str] = set()
    total_routes = 0
    step_categories = {}

    for step in steps:
        tools = step.get("available_tools", [])
        all_tools.update(tools)
        total_routes += len(step.get("routes", []))
        step_categories[step["step_id"]] = get_node_class(step)

    # Process flows information
    flows_info = []
    for flow in flows:
        flow_info = {
            "flow_id": flow["flow_id"],
            "description": flow.get("description", ""),
            "enters": flow.get("enters", []),
            "exits": flow.get("exits", []),
            "components": flow.get("components", {}),
            "metadata": flow.get("metadata", {}),
        }
        flows_info.append(flow_info)

    # Process steps with enhanced metadata
    enhanced_steps = []
    for step in steps:
        step_id = step["step_id"]
        description = step.get("description", "")
        tools = step.get("available_tools", [])
        routes = step.get("routes", [])

        enhanced_step = {
            "step_id": step_id,
            "description": description,
            "formatted_description": format_description(description),
            "category": get_node_class(step),
            "tools": tools,
            "routes": routes,
            "route_count": len(routes),
            "is_start": step_id == start_step,
            "is_end": step_id == "end" or "end" in description.lower(),
            "sanitized_id": sanitize_node_id(step_id),
        }
        enhanced_steps.append(enhanced_step)

    # Generate flow statistics
    flow_stats = {
        "total_steps": len(steps),
        "total_routes": total_routes,
        "total_tools": len(all_tools),
        "total_flows": len(flows),
        "categories": {},
    }

    # Count steps by category
    for category in step_categories.values():
        flow_stats["categories"][category] = flow_stats["categories"].get(category, 0) + 1  # type: ignore

    # Build the complete configuration JSON
    config_json = {
        "metadata": {
            "name": name,
            "formatted_name": name.title().replace("_", " "),
            "persona": persona,
            "start_step_id": start_step,
            "generated_at": None,  # Will be set when endpoint is called
            "version": "1.0",
        },
        "flow": {"steps": enhanced_steps, "statistics": flow_stats},
        "flows": flows_info,
        "tools": {"available_tools": sorted(list(all_tools)), "tool_usage": {}},  # noqa
        "visualization": {
            "mermaid_flowchart": generate_mermaid_flowchart(config, include_styling=True),
            "summary_markdown": generate_summary(config),
        },
    }

    # Add tool usage statistics
    for tool in all_tools:
        tool_steps = [s["step_id"] for s in steps if tool in s.get("available_tools", [])]
        config_json["tools"]["tool_usage"][tool] = {  # type: ignore
            "used_in_steps": tool_steps,
            "usage_count": len(tool_steps),
        }

    return config_json


def main() -> None:
    """Main function to handle command line arguments and execute conversion."""
    parser = argparse.ArgumentParser(
        description="Convert config.agent.yaml to enhanced Mermaid flowchart",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python yaml_to_mermaid.py config.agent.yaml
  python yaml_to_mermaid.py config.agent.yaml --output flowchart.md
  python yaml_to_mermaid.py config.agent.yaml --summary --style
        """,
    )

    parser.add_argument(
        "input_file",
        nargs="?",
        default="config.agent.yaml",
        help="Input YAML file (default: config.agent.yaml)",
    )
    parser.add_argument("--output", "-o", type=str, help="Output file path (default: stdout)")
    parser.add_argument(
        "--summary", "-s", action="store_true", help="Include configuration summary"
    )
    parser.add_argument(
        "--style",
        action="store_true",
        default=True,
        help="Include Mermaid styling (default: True)",
    )
    parser.add_argument("--no-style", action="store_true", help="Disable Mermaid styling")
    parser.add_argument(
        "--json", "-j", action="store_true", help="Output as JSON instead of markdown"
    )

    args = parser.parse_args()

    # Parse include_styling flag
    include_styling = args.style and not args.no_style

    # Parse the YAML configuration
    config = parse_yaml_config(args.input_file)

    # Generate output
    output_content = []

    if args.json:
        # Generate JSON output
        config_json = generate_config_json(config)
        config_json["metadata"]["generated_at"] = datetime.datetime.now().isoformat()
        final_output = json.dumps(config_json, indent=2, ensure_ascii=False)
    else:
        # Generate markdown output
        if args.summary:
            output_content.append(generate_summary(config))
            output_content.append("")

        # Add mermaid code block wrapper for markdown output
        mermaid_content = generate_mermaid_flowchart(config, include_styling)
        output_content.append("```mermaid")
        output_content.append(mermaid_content)
        output_content.append("```")
        final_output = "\n".join(output_content)

    # Output to file or stdout
    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(final_output)
            log_info(f"✅ Enhanced flowchart generated successfully: {args.output}")
        except IOError as e:
            log_error(f"❌ Error writing to file: {e}")
            raise
    else:
        log_info(final_output)


if __name__ == "__main__":
    main()
