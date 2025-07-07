"""Runtime helpers to execute YAML defined agent tests."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List, Optional


def _create_test_file(yaml_path: Path) -> Path:
    """Generate a pytest file that executes YAML defined tests."""
    agent_cfg = yaml_path.parent / "config.agent.yaml"
    test_file = yaml_path.parent / "test_generated.py"
    lines: List[str] = [
        "import pytest",
        "from pathlib import Path",
        "from nomos import *",
        "from nomos.llms import LLMConfig",
        "from nomos.testing.yaml_tests import load_yaml_tests",
        f"yaml_file = Path('{yaml_path.as_posix()}')",
        "suite = load_yaml_tests(yaml_file)",
        f"cfg = AgentConfig.from_yaml('{agent_cfg.as_posix()}')",
        "llm_cfg = suite.llm or cfg.llm",
        "if llm_cfg is None:",
        "    llm_cfg = LLMConfig(provider='openai', model='gpt-4o-mini')",
        "llm = llm_cfg.get_llm()",
        "agent = Agent.from_config(cfg, llm)",
        "",
        "# Unit tests",
        "for name, tc in suite.unit.items():",
        "    def _test(tc=tc):",
        "        ctx = tc.build_context()",
        "        res = agent.next(tc.input, session_data=ctx, verbose=tc.verbose)",
        "        if tc.invalid:",
        "            with pytest.raises(AssertionError):",
        "                smart_assert(res.decision, tc.expectation, agent.llm)",
        "        else:",
        "            smart_assert(res.decision, tc.expectation, agent.llm)",
        "    globals()[f'test_{name}'] = _test",
        "",
        "# E2E tests",
        "for name, tc in suite.e2e.items():",
        "    def _test(tc=tc):",
        "        scenario = Scenario(scenario=tc.scenario, expectation=tc.expectation)",
        "        ScenarioRunner.run(agent, scenario, tc.max_steps)",
        "    globals()[f'test_{name}'] = _test",
    ]
    with open(test_file, "w") as f:
        f.write("\n".join(lines))
    return test_file


def run_yaml_tests(
    yaml_path: Path, pytest_args: Optional[List[str]] = None, coverage: bool = True
) -> int:
    """Run YAML defined tests using pytest."""
    test_file = _create_test_file(yaml_path)
    cmd = ["python", "-m", "pytest", str(test_file)]
    if pytest_args:
        cmd.extend(pytest_args)
    if coverage:
        cmd.extend(["--cov=.", "--cov-report=term-missing"])
    result = subprocess.run(cmd)
    return result.returncode


__all__ = ["run_yaml_tests"]
