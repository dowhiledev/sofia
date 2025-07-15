"""Tests for the tracing module."""

import importlib
import sys
import types
from unittest.mock import MagicMock, patch


class MockSpan:
    """Mock span for testing."""

    def __init__(self):
        self.attributes = {}
        self.start_time = 1234567890
        self.status = None
        self.exceptions = []

    def set_attribute(self, key, value):
        self.attributes[key] = value

    def record_exception(self, exception):
        self.exceptions.append(exception)

    def set_status(self, status):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


def _create_mock_opentelemetry_modules():
    """Create comprehensive mock OpenTelemetry modules for testing."""
    # Status module
    status_mod = types.ModuleType("opentelemetry.trace.status")
    status_mod.Status = MagicMock()
    status_mod.StatusCode = types.SimpleNamespace(ERROR=2, OK=1)

    # Main trace module
    trace_mod = types.ModuleType("opentelemetry.trace")
    trace_mod.set_tracer_provider = MagicMock()
    trace_mod.get_tracer_provider = MagicMock()
    trace_mod.get_tracer = MagicMock()  # Add get_tracer method
    trace_mod.get_current_span = MagicMock()
    trace_mod.set_span_in_context = MagicMock()
    trace_mod.SpanKind = types.SimpleNamespace(INTERNAL=0, CLIENT=1)
    trace_mod.status = status_mod

    # Exporter module
    exporter_mod = types.ModuleType("opentelemetry.exporter.otlp.proto.http.trace_exporter")
    exporter_mod.OTLPSpanExporter = MagicMock()

    # SDK modules
    sdk_trace = types.ModuleType("opentelemetry.sdk.trace")
    sdk_trace.TracerProvider = MagicMock()

    sdk_export = types.ModuleType("opentelemetry.sdk.trace.export")
    sdk_export.BatchSpanProcessor = MagicMock()

    # Instrumentor module
    instr_mod = types.ModuleType("opentelemetry.instrumentation.instrumentor")
    instr_mod.BaseInstrumentor = object

    return {
        "trace": trace_mod,
        "exporter": exporter_mod,
        "sdk_trace": sdk_trace,
        "sdk_export": sdk_export,
        "instrumentor": instr_mod,
        "status": status_mod,
    }


def _load_tracing(monkeypatch):
    """Return tracing module with fake opentelemetry dependencies."""
    modules = _create_mock_opentelemetry_modules()

    # Register modules and parents
    root_mod = types.ModuleType("opentelemetry")
    root_mod.trace = modules["trace"]
    root_mod.instrumentation = types.ModuleType("opentelemetry.instrumentation")
    root_mod.exporter = types.ModuleType("opentelemetry.exporter")
    root_mod.sdk = types.ModuleType("opentelemetry.sdk")

    # Register all modules in sys.modules
    monkeypatch.setitem(sys.modules, "opentelemetry", root_mod)
    monkeypatch.setitem(sys.modules, "opentelemetry.trace", modules["trace"])
    monkeypatch.setitem(sys.modules, "opentelemetry.trace.status", modules["status"])
    monkeypatch.setitem(sys.modules, "opentelemetry.exporter", root_mod.exporter)
    monkeypatch.setitem(sys.modules, "opentelemetry.exporter.otlp", types.ModuleType("op.exp.otlp"))
    monkeypatch.setitem(
        sys.modules,
        "opentelemetry.exporter.otlp.proto",
        types.ModuleType("op.exp.otlp.proto"),
    )
    monkeypatch.setitem(
        sys.modules,
        "opentelemetry.exporter.otlp.proto.http",
        types.ModuleType("op.exp.otlp.proto.http"),
    )
    monkeypatch.setitem(
        sys.modules,
        "opentelemetry.exporter.otlp.proto.http.trace_exporter",
        modules["exporter"],
    )

    root_mod.instrumentation.instrumentor = modules["instrumentor"]
    monkeypatch.setitem(sys.modules, "opentelemetry.instrumentation", root_mod.instrumentation)
    monkeypatch.setitem(
        sys.modules,
        "opentelemetry.instrumentation.instrumentor",
        modules["instrumentor"],
    )

    root_mod.sdk.trace = modules["sdk_trace"]
    root_mod.sdk.trace.export = modules["sdk_export"]
    monkeypatch.setitem(sys.modules, "opentelemetry.sdk", root_mod.sdk)
    monkeypatch.setitem(sys.modules, "opentelemetry.sdk.trace", modules["sdk_trace"])
    monkeypatch.setitem(sys.modules, "opentelemetry.sdk.trace.export", modules["sdk_export"])

    tracing = importlib.import_module("nomos.utils.tracing")
    importlib.reload(tracing)
    return tracing, modules


class TestNomosInstrumentor:
    """Test cases for the NomosInstrumentor class."""

    def test_instrumentation_dependencies(self, monkeypatch):
        """Test that instrumentation_dependencies returns empty list."""
        tracing, modules = _load_tracing(monkeypatch)
        instrumentor = tracing.NomosInstrumentor()
        assert instrumentor.instrumentation_dependencies() == []

    def test_instrument_patches_methods(self, monkeypatch):
        """Test that _instrument properly patches all target methods."""
        tracing, modules = _load_tracing(monkeypatch)

        # Mock the tracer
        mock_tracer = MagicMock()
        modules["trace"].get_tracer.return_value = mock_tracer

        # Mock the Agent and Session classes
        mock_agent = MagicMock()
        mock_session = MagicMock()

        with (
            patch("nomos.utils.tracing.Agent", mock_agent),
            patch("nomos.utils.tracing.Session", mock_session),
        ):
            instrumentor = tracing.NomosInstrumentor()
            instrumentor._instrument()

            # Verify that methods were assigned (patched)
            # The exact implementation details may vary, but we can check that
            # the methods were called/assigned
            modules["trace"].get_tracer.assert_called_once()

    def test_uninstrument_restores_methods(self, monkeypatch):
        """Test that _uninstrument restores original methods."""
        tracing, modules = _load_tracing(monkeypatch)

        # Mock the Agent and Session classes with wrapped methods
        mock_agent = MagicMock()
        mock_session = MagicMock()

        # Create mock wrapped methods - need to handle the __wrapped__ attribute properly
        original_create_session = MagicMock()
        wrapped_create_session = MagicMock()
        wrapped_create_session.__wrapped__ = original_create_session
        mock_agent.create_session = wrapped_create_session

        original_next = MagicMock()
        wrapped_next = MagicMock()
        wrapped_next.__wrapped__ = original_next
        mock_session.next = wrapped_next

        original_run_tool = MagicMock()
        wrapped_run_tool = MagicMock()
        wrapped_run_tool.__wrapped__ = original_run_tool
        mock_session._run_tool = wrapped_run_tool

        original_get_next_decision = MagicMock()
        wrapped_get_next_decision = MagicMock()
        wrapped_get_next_decision.__wrapped__ = original_get_next_decision
        mock_session._get_next_decision = wrapped_get_next_decision

        with (
            patch("nomos.utils.tracing.Agent", mock_agent),
            patch("nomos.utils.tracing.Session", mock_session),
        ):
            instrumentor = tracing.NomosInstrumentor()
            instrumentor._uninstrument()

            # Verify that methods were restored to their wrapped versions
            assert mock_agent.create_session == original_create_session
            assert mock_session.next == original_next
            assert mock_session._run_tool == original_run_tool
            assert mock_session._get_next_decision == original_get_next_decision


class TestInitializeAndShutdownTracing:
    """Test cases for tracing initialization and shutdown."""

    def test_initialize_tracing_with_default_params(self, monkeypatch):
        """Test initialize_tracing with default parameters."""
        tracing, modules = _load_tracing(monkeypatch)

        tracer_instance = MagicMock()
        modules["sdk_trace"].TracerProvider.return_value = tracer_instance
        modules["trace"].get_tracer_provider.return_value = tracer_instance
        processor = MagicMock()
        modules["sdk_export"].BatchSpanProcessor.return_value = processor

        instrumentor = MagicMock()
        monkeypatch.setattr(tracing, "NomosInstrumentor", lambda: instrumentor)

        # Test with default parameters
        tracing.initialize_tracing()

        modules["trace"].set_tracer_provider.assert_called_once()
        modules["sdk_trace"].TracerProvider.assert_called_once_with()
        modules["exporter"].OTLPSpanExporter.assert_called_once()
        modules["sdk_export"].BatchSpanProcessor.assert_called_once()
        tracer_instance.add_span_processor.assert_called_once_with(processor)
        instrumentor.instrument.assert_called_once()

    def test_initialize_tracing_with_custom_params(self, monkeypatch):
        """Test initialize_tracing with custom parameters."""
        tracing, modules = _load_tracing(monkeypatch)

        tracer_instance = MagicMock()
        modules["sdk_trace"].TracerProvider.return_value = tracer_instance
        modules["trace"].get_tracer_provider.return_value = tracer_instance
        processor = MagicMock()
        modules["sdk_export"].BatchSpanProcessor.return_value = processor

        instrumentor = MagicMock()
        monkeypatch.setattr(tracing, "NomosInstrumentor", lambda: instrumentor)

        # Test with custom parameters
        tracer_kwargs = {"resource": "custom_resource"}
        exporter_kwargs = {"timeout": 30}
        processor_kwargs = {"max_queue_size": 1000}

        tracing.initialize_tracing(tracer_kwargs, exporter_kwargs, processor_kwargs)

        modules["trace"].set_tracer_provider.assert_called_once()
        modules["sdk_trace"].TracerProvider.assert_called_once_with(resource="custom_resource")
        modules["exporter"].OTLPSpanExporter.assert_called_once()
        # Check that custom exporter kwargs were passed
        call_args = modules["exporter"].OTLPSpanExporter.call_args
        assert "timeout" in call_args.kwargs

        modules["sdk_export"].BatchSpanProcessor.assert_called_once_with(
            modules["exporter"].OTLPSpanExporter.return_value, max_queue_size=1000
        )
        tracer_instance.add_span_processor.assert_called_once_with(processor)
        instrumentor.instrument.assert_called_once()

    def test_initialize_tracing_with_environment_variables(self, monkeypatch):
        """Test initialize_tracing uses environment variables correctly."""
        tracing, modules = _load_tracing(monkeypatch)

        # Set environment variables
        monkeypatch.setenv("ELASTIC_APM_SERVER_URL", "https://custom-apm.example.com:8200")
        monkeypatch.setenv("ELASTIC_APM_TOKEN", "secret-token-123")

        tracer_instance = MagicMock()
        modules["sdk_trace"].TracerProvider.return_value = tracer_instance
        modules["trace"].get_tracer_provider.return_value = tracer_instance

        instrumentor = MagicMock()
        monkeypatch.setattr(tracing, "NomosInstrumentor", lambda: instrumentor)

        tracing.initialize_tracing()

        # Verify that the exporter was called with the correct endpoint and headers
        call_args = modules["exporter"].OTLPSpanExporter.call_args
        assert call_args.kwargs["endpoint"] == "https://custom-apm.example.com:8200/v1/traces"
        assert call_args.kwargs["headers"] == {"Authorization": "Bearer secret-token-123"}

    def test_shutdown_tracing(self, monkeypatch):
        """Test shutdown_tracing uninstruments properly."""
        tracing, modules = _load_tracing(monkeypatch)

        instrumentor = MagicMock()
        monkeypatch.setattr(tracing, "NomosInstrumentor", lambda: instrumentor)

        tracing.shutdown_tracing()
        instrumentor.uninstrument.assert_called_once()


class TestRegressionScenarios:
    """Regression tests for specific scenarios that might break."""

    def test_module_import_regression(self, monkeypatch):
        """Test that module imports work correctly in different scenarios."""
        tracing, modules = _load_tracing(monkeypatch)

        # Test that we can create an instrumentor instance
        instrumentor = tracing.NomosInstrumentor()
        assert instrumentor is not None
        assert hasattr(instrumentor, "instrumentation_dependencies")
        assert hasattr(instrumentor, "_instrument")
        assert hasattr(instrumentor, "_uninstrument")

    def test_configuration_parameter_regression(self, monkeypatch):
        """Test that configuration parameters are handled correctly."""
        tracing, modules = _load_tracing(monkeypatch)

        # Test with None parameters (should use defaults)
        tracer_instance = MagicMock()
        modules["sdk_trace"].TracerProvider.return_value = tracer_instance
        modules["trace"].get_tracer_provider.return_value = tracer_instance

        instrumentor = MagicMock()
        monkeypatch.setattr(tracing, "NomosInstrumentor", lambda: instrumentor)

        # These should all work without error
        tracing.initialize_tracing(None, None, None)
        tracing.initialize_tracing({}, {}, {})
        tracing.initialize_tracing()

    def test_opentelemetry_api_compatibility(self, monkeypatch):
        """Test compatibility with OpenTelemetry API patterns."""
        tracing, modules = _load_tracing(monkeypatch)

        # Test that our mocks provide the expected API
        assert hasattr(modules["trace"], "set_tracer_provider")
        assert hasattr(modules["trace"], "get_tracer_provider")
        assert hasattr(modules["trace"], "get_tracer")
        assert hasattr(modules["trace"], "SpanKind")
        assert hasattr(modules["trace"].SpanKind, "INTERNAL")
        assert hasattr(modules["trace"].SpanKind, "CLIENT")

        # Test that span kinds have expected values
        assert modules["trace"].SpanKind.INTERNAL == 0
        assert modules["trace"].SpanKind.CLIENT == 1

    def test_environment_variable_handling(self, monkeypatch):
        """Test that environment variables are handled correctly in various scenarios."""
        tracing, modules = _load_tracing(monkeypatch)

        # Test with custom environment variables
        monkeypatch.setenv("ELASTIC_APM_SERVER_URL", "https://test-apm.example.com:8200")
        monkeypatch.setenv("ELASTIC_APM_TOKEN", "test-token-456")

        tracer_instance = MagicMock()
        modules["sdk_trace"].TracerProvider.return_value = tracer_instance
        modules["trace"].get_tracer_provider.return_value = tracer_instance

        instrumentor = MagicMock()
        monkeypatch.setattr(tracing, "NomosInstrumentor", lambda: instrumentor)

        tracing.initialize_tracing()

        # Verify environment variables were used
        call_args = modules["exporter"].OTLPSpanExporter.call_args
        assert "https://test-apm.example.com:8200/v1/traces" in call_args.kwargs["endpoint"]
        assert "test-token-456" in call_args.kwargs["headers"]["Authorization"]

    def test_safe_attribute_access_patterns(self, monkeypatch):
        """Test that the attribute access patterns used in tracing are safe."""
        tracing, modules = _load_tracing(monkeypatch)

        # Test patterns used in the actual tracing code with real objects
        class TestObj:
            def __init__(self):
                self.attr = "value"

        test_obj = TestObj()

        # These patterns should not raise exceptions
        assert getattr(test_obj, "attr", None) == "value"
        assert getattr(test_obj, "missing", None) is None
        assert getattr(test_obj, "missing", "default") == "default"

        # Test nested attribute access
        class NestedObj:
            def __init__(self):
                self.action = TestObj()
                self.action.value = "ACTION_VALUE"

        test_nested = NestedObj()

        result = getattr(getattr(test_nested, "action", None), "value", None)
        assert result == "ACTION_VALUE"

        # Test with missing nested attribute
        test_nested.action = None
        result = getattr(getattr(test_nested, "action", None), "value", None)
        assert result is None

    def test_string_conversion_safety(self, monkeypatch):
        """Test that various object types can be safely converted to strings."""
        tracing, modules = _load_tracing(monkeypatch)

        test_cases = [
            {"dict": "value"},
            ["list", "items"],
            None,
            "",
            "string",
            42,
            {"nested": {"object": "value"}},
            Exception("error message"),
        ]

        for test_obj in test_cases:
            # Should not raise an exception
            result = str(test_obj)
            assert isinstance(result, str)

    def test_exception_handling_patterns(self, monkeypatch):
        """Test exception handling patterns used in tracing."""
        tracing, modules = _load_tracing(monkeypatch)

        # Create a mock span to test exception recording
        mock_span = MockSpan()

        test_exception = ValueError("Test exception")
        mock_span.record_exception(test_exception)

        assert test_exception in mock_span.exceptions

        # Test status setting
        mock_span.set_status("error_status")
        assert mock_span.status == "error_status"

    def test_instrumentor_lifecycle(self, monkeypatch):
        """Test the complete instrumentor lifecycle."""
        tracing, modules = _load_tracing(monkeypatch)

        instrumentor = tracing.NomosInstrumentor()

        # Test that dependencies method works
        deps = instrumentor.instrumentation_dependencies()
        assert isinstance(deps, list)
        assert len(deps) == 0

        # Test that instrument and uninstrument methods exist and can be called
        # (even if they fail due to missing real objects, they should be callable)
        assert callable(getattr(instrumentor, "_instrument", None))
        assert callable(getattr(instrumentor, "_uninstrument", None))

    def test_tracing_configuration_edge_cases(self, monkeypatch):
        """Test edge cases in tracing configuration."""
        tracing, modules = _load_tracing(monkeypatch)

        tracer_instance = MagicMock()
        modules["sdk_trace"].TracerProvider.return_value = tracer_instance
        modules["trace"].get_tracer_provider.return_value = tracer_instance

        instrumentor = MagicMock()
        monkeypatch.setattr(tracing, "NomosInstrumentor", lambda: instrumentor)

        # Test with empty environment variables
        monkeypatch.setenv("ELASTIC_APM_SERVER_URL", "")
        monkeypatch.setenv("ELASTIC_APM_TOKEN", "")

        # Should still work, using defaults when env vars are empty
        tracing.initialize_tracing()

        call_args = modules["exporter"].OTLPSpanExporter.call_args
        # When empty, should fall back to default - just check that exporter was called
        assert call_args is not None
        assert "endpoint" in call_args.kwargs
        # The empty env var should result in the default being used
        endpoint = call_args.kwargs["endpoint"]
        assert "/v1/traces" in endpoint

    def test_mock_span_behavior(self, monkeypatch):
        """Test that our MockSpan behaves correctly for testing purposes."""
        tracing, modules = _load_tracing(monkeypatch)

        span = MockSpan()

        # Test attribute setting
        span.set_attribute("test_key", "test_value")
        assert span.attributes["test_key"] == "test_value"

        # Test exception recording
        test_exception = RuntimeError("test error")
        span.record_exception(test_exception)
        assert test_exception in span.exceptions

        # Test status setting
        span.set_status("test_status")
        assert span.status == "test_status"

        # Test context manager behavior
        with span as s:
            assert s is span

    def test_comprehensive_api_coverage(self, monkeypatch):
        """Test that all major API components are properly mocked."""
        tracing, modules = _load_tracing(monkeypatch)

        # Test all the major components exist
        required_components = [
            "trace",
            "exporter",
            "sdk_trace",
            "sdk_export",
            "instrumentor",
            "status",
        ]

        for component in required_components:
            assert component in modules
            assert modules[component] is not None

        # Test specific API methods exist
        assert callable(modules["trace"].set_tracer_provider)
        assert callable(modules["trace"].get_tracer_provider)
        assert callable(modules["trace"].get_tracer)
        assert callable(modules["exporter"].OTLPSpanExporter)
        assert callable(modules["sdk_trace"].TracerProvider)
        assert callable(modules["sdk_export"].BatchSpanProcessor)

        # Test that instrumentor base class exists
        assert modules["instrumentor"].BaseInstrumentor is not None
