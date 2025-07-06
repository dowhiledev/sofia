"""Tests for the Nomos CLI."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from nomos.cli import _generate_project_files, app
from nomos.config import AgentConfig
from nomos.models.agent import Step as AgentStep


class TestCLI:
    """Test cases for CLI commands."""

    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()

    def test_version_callback(self):
        """Test version callback functionality."""
        result = self.runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        # Version should be printed

    def test_help_command(self):
        """Test help command."""
        result = self.runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Build Agents you can audit" in result.stdout

    def test_init_help(self):
        """Test init command help."""
        result = self.runner.invoke(app, ["init", "--help"])
        assert result.exit_code == 0
        assert "Initialize a new Nomos agent project" in result.stdout

    def test_run_help(self):
        """Test run command help."""
        result = self.runner.invoke(app, ["run", "--help"])
        assert result.exit_code == 0
        assert "Run the Nomos agent in development mode" in result.stdout

    def test_train_help(self):
        """Test train command help."""
        result = self.runner.invoke(app, ["train", "--help"])
        assert result.exit_code == 0
        assert "training mode" in result.stdout.lower()

    def test_serve_help(self):
        """Test serve command help."""
        result = self.runner.invoke(app, ["serve", "--help"])
        assert result.exit_code == 0
        assert "Serve the Nomos agent using FastAPI" in result.stdout

    def test_test_help(self):
        """Test test command help."""
        result = self.runner.invoke(app, ["test", "--help"])
        assert result.exit_code == 0
        assert "Run the Nomos testing framework" in result.stdout

    def test_schema_help(self):
        """Test schema command help."""
        result = self.runner.invoke(app, ["schema", "--help"])
        assert result.exit_code == 0
        assert "Generate JSON schema" in result.stdout


class TestInitCommand:
    """Test cases for the init command."""

    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()

    @patch("nomos.cli.Prompt.ask")
    @patch("nomos.cli.Confirm.ask")
    def test_init_basic_template(self, mock_confirm, mock_prompt):
        """Test init command with basic template."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir) / "test_agent"

            # Mock user inputs
            mock_prompt.side_effect = [
                str(project_dir),  # project directory
                "1",  # LLM choice (OpenAI)
                "basic",  # template choice
            ]
            mock_confirm.side_effect = [
                False,
                False,
            ]  # No to generate, no need to confirm

            result = self.runner.invoke(app, ["init"])

            # Should succeed
            assert result.exit_code == 0

            # Check that project files were created
            assert (project_dir / "config.agent.yaml").exists()
            assert (project_dir / "tools" / "__init__.py").exists()
            assert (project_dir / "tools" / "sample_tool.py").exists()
            assert (project_dir / "main.py").exists()
            assert (project_dir / "requirements.txt").exists()
            assert (project_dir / ".env").exists()
            assert (project_dir / "README.md").exists()

    def test_init_with_directory_flag(self):
        """Test init command with directory flag."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir) / "flagged_agent"

            with (
                patch("nomos.cli.Prompt.ask") as mock_prompt,
                patch("nomos.cli.Confirm.ask") as mock_confirm,
            ):
                mock_prompt.side_effect = [
                    "1",  # LLM choice
                    "basic",  # template choice
                ]
                mock_confirm.side_effect = [False, False]

                result = self.runner.invoke(app, ["init", "--directory", str(project_dir)])

                assert result.exit_code == 0
                assert (project_dir / "config.agent.yaml").exists()

    def test_init_with_template_flag(self):
        """Test init command with template flag."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir) / "template_agent"

            with patch("nomos.cli.Prompt.ask") as mock_prompt:
                mock_prompt.side_effect = [
                    str(project_dir),  # project directory
                    "1",  # LLM choice
                ]

                result = self.runner.invoke(app, ["init", "--template", "basic"])

                assert result.exit_code == 0
                assert (project_dir / "config.agent.yaml").exists()

    @patch("nomos.cli._handle_config_generation")
    @patch("nomos.cli.Prompt.ask")
    def test_init_with_generate_flag(self, mock_prompt, mock_generate):
        """Test init command with generate flag."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir) / "generated_agent"

            # Mock the generation response
            mock_config = Mock()
            mock_config.name = "test_agent"
            mock_config.persona = "A test agent"
            mock_config.to_agent_steps.return_value = [
                AgentStep(
                    step_id="start",
                    description="Start step",
                    available_tools=[],
                    routes=[],
                )
            ]
            mock_generate.return_value = mock_config

            mock_prompt.side_effect = [
                str(project_dir),  # project directory
                "1",  # LLM choice
                "1",  # LLM choice again (repeated in generate flow)
                "gpt-4o-mini",  # model choice
                "Create a test agent",  # usecase
                "tool1,tool2",  # tools
            ]

            result = self.runner.invoke(
                app,
                [
                    "init",
                    "--generate",
                    "--usecase",
                    "Create a test agent",
                    "--tools",
                    "tool1,tool2",
                ],
            )

            assert result.exit_code == 0
            assert (project_dir / "config.agent.yaml").exists()
            mock_generate.assert_called_once()

    def test_init_existing_directory_confirm_no(self):
        """Test init command with existing directory when user says no."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir) / "existing_agent"
            project_dir.mkdir()
            (project_dir / "existing_file.txt").write_text("test")

            with (
                patch("nomos.cli.Prompt.ask") as mock_prompt,
                patch("nomos.cli.Confirm.ask") as mock_confirm,
            ):
                mock_prompt.return_value = str(project_dir)
                mock_confirm.return_value = False  # User says no to continue

                result = self.runner.invoke(app, ["init"])

                assert result.exit_code == 1
                assert "cancelled" in result.stdout

    def test_init_invalid_template(self):
        """Test init command with invalid template."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir) / "invalid_agent"

            with patch("nomos.cli.Prompt.ask") as mock_prompt:
                mock_prompt.side_effect = [
                    str(project_dir),
                    "1",  # LLM choice
                ]

                result = self.runner.invoke(app, ["init", "--template", "invalid_template"])

                assert result.exit_code == 1
                assert "not found" in result.stdout


class TestRunCommand:
    """Test cases for the run command."""

    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()

    def test_run_missing_config(self):
        """Test run command with missing config file."""
        result = self.runner.invoke(app, ["run", "--config", "nonexistent_config.yaml"])

        assert result.exit_code == 1
        assert "Configuration file not found" in result.stdout

    def test_run_missing_tool_file(self):
        """Test run command with missing tool file."""
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as config_file:
            # Create a minimal config
            config_content = """
name: test_agent
persona: Test persona
steps:
  - step_id: start
    description: Start step
    available_tools: []
    routes: []
start_step_id: start
llm:
  provider: openai
  model: gpt-4o-mini
"""
            config_file.write(config_content.encode())
            config_file.flush()

            try:
                result = self.runner.invoke(
                    app,
                    [
                        "run",
                        "--config",
                        config_file.name,
                        "--tools",
                        "nonexistent_tool.py",
                    ],
                )

                assert result.exit_code == 1
                assert "Tool file not found" in result.stdout
            finally:
                os.unlink(config_file.name)

    @patch("nomos.cli._run")
    def test_run_success(self, mock_run):
        """Test successful run command."""
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as config_file:
            config_content = """
name: test_agent
persona: Test persona
steps:
  - step_id: start
    description: Start step
    available_tools: []
    routes: []
start_step_id: start
llm:
  provider: openai
  model: gpt-4o-mini
"""
            config_file.write(config_content.encode())
            config_file.flush()

            try:
                result = self.runner.invoke(app, ["run", "--config", config_file.name, "--verbose"])

                assert result.exit_code == 0
                mock_run.assert_called_once()
            finally:
                os.unlink(config_file.name)

    @patch("nomos.cli._run")
    def test_run_keyboard_interrupt(self, mock_run):
        """Test run command with keyboard interrupt."""
        mock_run.side_effect = KeyboardInterrupt()

        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as config_file:
            config_content = """
name: test_agent
persona: Test persona
steps:
  - step_id: start
    description: Start step
    available_tools: []
    routes: []
start_step_id: start
llm:
  provider: openai
  model: gpt-4o-mini
"""
            config_file.write(config_content.encode())
            config_file.flush()

            try:
                result = self.runner.invoke(app, ["run", "--config", config_file.name])

                assert result.exit_code == 0
                assert "stopped" in result.stdout
            finally:
                os.unlink(config_file.name)


class TestServeCommand:
    """Test cases for the serve command."""

    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()

    def test_serve_missing_config(self):
        """Test serve command with missing config file."""
        result = self.runner.invoke(app, ["serve", "--config", "nonexistent_config.yaml"])

        assert result.exit_code == 1
        assert "Configuration file not found" in result.stdout

    @patch("nomos.cli.run_server")
    def test_serve_success(self, mock_run_server):
        """Test successful serve command."""
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as config_file:
            config_content = """
name: test_agent
persona: Test persona
steps:
  - step_id: start
    description: Start step
    available_tools: []
    routes: []
start_step_id: start
llm:
  provider: openai
  model: gpt-4o-mini
server:
  port: 8000
  workers: 1
"""
            config_file.write(config_content.encode())
            config_file.flush()

            try:
                result = self.runner.invoke(
                    app,
                    [
                        "serve",
                        "--config",
                        config_file.name,
                        "--port",
                        "9000",
                        "--workers",
                        "2",
                    ],
                )

                assert result.exit_code == 0
                mock_run_server.assert_called_once()
            finally:
                os.unlink(config_file.name)


class TestTestCommand:
    """Test cases for the test command."""

    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()

    @patch("nomos.cli._run_tests")
    def test_test_no_yaml_config(self, mock_run_tests):
        """Test test command without YAML config."""
        result = self.runner.invoke(app, ["test", "--no-coverage"])

        assert result.exit_code == 0
        mock_run_tests.assert_called_once()

    @patch("nomos.testing.yaml_runner.run_yaml_tests")
    def test_test_with_yaml_config(self, mock_run_yaml_tests):
        """Test test command with YAML config."""
        mock_run_yaml_tests.return_value = 0

        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as yaml_file:
            yaml_file.write(b"test: config")
            yaml_file.flush()

            try:
                result = self.runner.invoke(app, ["test", "--config", yaml_file.name])

                assert result.exit_code == 0
                mock_run_yaml_tests.assert_called_once()
            finally:
                os.unlink(yaml_file.name)

    @patch("nomos.testing.yaml_runner.run_yaml_tests")
    def test_test_yaml_config_failure(self, mock_run_yaml_tests):
        """Test test command with YAML config that fails."""
        mock_run_yaml_tests.return_value = 1

        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as yaml_file:
            yaml_file.write(b"test: config")
            yaml_file.flush()

            try:
                result = self.runner.invoke(app, ["test", "--config", yaml_file.name])

                assert result.exit_code == 1
                assert "failed" in result.stdout
            finally:
                os.unlink(yaml_file.name)


class TestSchemaCommand:
    """Test cases for the schema command."""

    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()

    def test_schema_stdout(self):
        """Test schema command output to stdout."""
        result = self.runner.invoke(app, ["schema"])

        assert result.exit_code == 0
        # Should output valid JSON
        output = result.stdout.strip()
        assert output.startswith("{")
        # Should be valid JSON
        json.loads(output)

    def test_schema_to_file(self):
        """Test schema command output to file."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as output_file:
            try:
                result = self.runner.invoke(app, ["schema", "--output", output_file.name])

                assert result.exit_code == 0
                assert "Schema written" in result.stdout

                # Check file was created and contains valid JSON
                assert Path(output_file.name).exists()
                content = Path(output_file.name).read_text()
                json.loads(content)  # Should not raise
            finally:
                os.unlink(output_file.name)


class TestGenerateProjectFiles:
    """Test cases for the _generate_project_files function."""

    def test_generate_project_files(self):
        """Test project file generation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            target_dir = Path(temp_dir)
            name = "test_agent"
            persona = "A test agent persona"
            llm_choice = "OpenAI"
            steps = [
                AgentStep(
                    step_id="start",
                    description="Start step",
                    available_tools=[],
                    routes=[],
                )
            ]

            _generate_project_files(target_dir, name, persona, llm_choice, steps)

            # Check all files were created
            assert (target_dir / "config.agent.yaml").exists()
            assert (target_dir / "tools" / "__init__.py").exists()
            assert (target_dir / "tools" / "sample_tool.py").exists()
            assert (target_dir / "main.py").exists()
            assert (target_dir / "requirements.txt").exists()
            assert (target_dir / ".env").exists()
            assert (target_dir / "README.md").exists()

            # Check config file content
            config = AgentConfig.from_yaml(str(target_dir / "config.agent.yaml"))
            assert config.name == name
            assert config.persona == persona
            assert len(config.steps) == 1
            assert config.steps[0].step_id == "start"

    def test_generate_project_files_no_steps_error(self):
        """Test project file generation with no steps raises error."""
        with tempfile.TemporaryDirectory() as temp_dir:
            target_dir = Path(temp_dir)

            with pytest.raises(AssertionError, match="At least one step must be defined"):
                _generate_project_files(target_dir, "test_agent", "persona", "OpenAI", [])


class TestConfigGeneration:
    """Test cases for config generation."""

    @pytest.mark.skip(reason="Complex integration test - requires real LLM mocking")
    def test_handle_config_generation(self):
        """Test config generation handling."""
        # This test requires complex mocking of the LLM interaction flow
        # TODO: Improve test by properly mocking the complete AgentGenerator flow
        pass


class TestUtilityFunctions:
    """Test cases for utility functions."""

    @patch("subprocess.run")
    def test_run_tests_success(self, mock_subprocess):
        """Test _run_tests function with success."""
        from nomos.cli import _run_tests

        mock_subprocess.return_value.returncode = 0

        _run_tests(["test_file.py"], coverage=True)

        mock_subprocess.assert_called_once()
        called_args = mock_subprocess.call_args[0][0]
        assert "pytest" in called_args
        assert "test_file.py" in called_args
        assert "--cov=." in called_args

    @patch("subprocess.run")
    def test_run_tests_failure(self, mock_subprocess):
        """Test _run_tests function with failure."""
        import typer

        from nomos.cli import _run_tests

        mock_subprocess.return_value.returncode = 1

        with pytest.raises(typer.Exit) as exc_info:
            _run_tests()

        # typer.Exit should contain the exit code
        assert exc_info.value.exit_code == 1

    @patch("subprocess.run")
    @patch("tempfile.NamedTemporaryFile")
    def test_run_function(self, mock_tempfile, mock_subprocess):
        """Test _run function."""
        from nomos.cli import _run

        # Mock temporary file
        mock_temp = Mock()
        mock_temp.name = "/tmp/test_script.py"
        mock_tempfile.return_value.__enter__.return_value = mock_temp

        mock_subprocess.return_value.returncode = 0

        config_path = Path("config.yaml")
        tool_files = []

        with patch("os.unlink"), patch("nomos.cli.Path.cwd") as mock_cwd:
            mock_cwd.return_value = Path("/test")
            _run(config_path, tool_files, verbose=True)

            mock_subprocess.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__])
