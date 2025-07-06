"""OpenTelemetry tracing for the Nomos library."""

import functools
import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import SpanKind
from pydantic import BaseModel

from ..core import Agent, Session


class NomosInstrumentor(BaseInstrumentor):
    """Instrumentor for the Nomos library to add OpenTelemetry tracing."""

    def instrumentation_dependencies(self) -> list:
        """Return a list of dependencies required for instrumentation."""
        # No external dependencies
        return []

    def _instrument(self, **kwargs) -> None:
        """
        Instrument the Nomos library to add OpenTelemetry tracing.

        This method patches the create_session, next, _run_tool, and _get_next_decision
        methods to add tracing spans.
        """
        tracer = trace.get_tracer(__name__)

        # Patch Agent.create_session
        _original_create_session = Agent.create_session  # type: ignore

        @functools.wraps(Agent.create_session)
        def traced_create_session(self_, *args, **kwargs) -> Session:
            with tracer.start_as_current_span(
                "Agent.create_session",
                kind=SpanKind.INTERNAL,
                attributes={
                    "agent.name": self_.name,
                    "agent.class": self_.__class__.__name__,
                    "agent.module": self_.__class__.__module__,
                },
            ) as span:
                session = _original_create_session(self_, *args, **kwargs)
                span.set_attribute("session.id", session.session_id)
                span.set_attribute("session.start_time", span.start_time)
                session._otel_root_span_ctx = trace.set_span_in_context(span)
                return session

        Agent.create_session = traced_create_session  # type: ignore

        # Patch Session.next
        _original_next = Session.next  # type: ignore

        @functools.wraps(Session.next)
        def traced_next(self_, *args, **kwargs) -> BaseModel:
            """Get the next decision and tool result."""
            ctx = getattr(self_, "_otel_root_span_ctx", None)
            span_ctx = ctx if ctx is not None else trace.get_current_span()
            with tracer.start_as_current_span(
                "Session.next",
                context=span_ctx,
                kind=SpanKind.INTERNAL,
                attributes={
                    "session.id": self_.session_id,
                    "current_step": getattr(self_.current_step, "step_id", None),
                    "step.description": getattr(self_.current_step, "description", None),
                    "step.available_routes": str(getattr(self_.current_step, "routes", [])),
                    "history.length": len(getattr(self_, "history", [])),
                },
            ) as span:
                try:
                    res = _original_next(self_, *args, **kwargs)
                    span.set_attribute(
                        "decision.action",
                        getattr(getattr(res.decision, "action", None), "value", None),
                    )
                    span.set_attribute("decision.input", getattr(res.decision, "input", None))
                    if getattr(res.decision, "tool_name", None):
                        span.set_attribute("tool.name", res.decision.tool_name)
                        span.set_attribute(
                            "tool.kwargs", str(getattr(res.decision, "tool_kwargs", {}))
                        )
                    if res.tool_output is not None:
                        span.set_attribute("tool.result", str(res.tool_output))
                    span.set_attribute("session.history_length", len(self_.history))
                    return res
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(trace.status.Status(trace.status.StatusCode.ERROR, str(e)))
                    raise

        Session.next = traced_next  # type: ignore

        # Patch Session._run_tool
        _original_run_tool = Session._run_tool  # type: ignore

        @functools.wraps(Session._run_tool)
        def traced_run_tool(self_, tool_name, kwargs) -> str:
            """Run a tool with the given name and arguments."""
            ctx = getattr(self_, "_otel_root_span_ctx", None)
            span_ctx = ctx if ctx is not None else trace.get_current_span()
            with tracer.start_as_current_span(
                "Session._run_tool",
                context=span_ctx,
                kind=SpanKind.INTERNAL,
                attributes={
                    "session.id": self_.session_id,
                    "tool.name": tool_name,
                    "tool.kwargs": str(kwargs),
                    "step.id": getattr(self_, "current_step", None) and self_.current_step.step_id,
                },
            ) as span:
                try:
                    result = _original_run_tool(self_, tool_name, kwargs)
                    span.set_attribute("tool.result", str(result))
                    span.set_attribute("tool.success", True)
                    return result
                except Exception as e:
                    span.record_exception(e)
                    span.set_attribute("tool.success", False)
                    span.set_status(trace.status.Status(trace.status.StatusCode.ERROR, str(e)))
                    raise

        Session._run_tool = traced_run_tool  # type: ignore

        # Patch Session._get_next_decision
        _original_get_next_decision = Session._get_next_decision  # type: ignore

        @functools.wraps(Session._get_next_decision)
        def traced_get_next_decision(self_, *args, **kwargs) -> BaseModel:
            """Get the next decision from the LLM."""
            ctx = getattr(self_, "_otel_root_span_ctx", None)
            span_ctx = ctx if ctx is not None else trace.get_current_span()
            with tracer.start_as_current_span(
                "llm._get_output",
                context=span_ctx,
                kind=SpanKind.CLIENT,
                attributes={
                    "agent.name": getattr(self_, "name", None),
                    "session.id": getattr(self_, "session_id", None),
                    "step.id": getattr(self_.current_step, "step_id", None),
                    "llm.class": self_.llm.__class__.__name__,
                    "llm.provider": getattr(self_.llm, "__provider__", None),
                    "llm.model": getattr(self_.llm, "model", None),
                    "history.length": len(getattr(self_, "history", [])),
                    "system_message": getattr(self_, "system_message", None),
                    "persona": getattr(self_, "persona", None),
                },
            ) as span:
                try:
                    result = _original_get_next_decision(self_, *args, **kwargs)
                    span.set_attribute("llm.success", True)
                    if hasattr(result, "response"):
                        span.set_attribute("llm.output", str(result.input)[:200])
                    return result
                except Exception as e:
                    span.record_exception(e)
                    span.set_attribute("llm.success", False)
                    raise

        Session._get_next_decision = traced_get_next_decision  # type: ignore

    def _uninstrument(self, **kwargs) -> None:
        """Uninstrument the Nomos library and restore original methods."""
        # Restore original methods
        Agent.create_session = Agent.create_session.__wrapped__  # type: ignore
        Session.next = Session.next.__wrapped__  # type: ignore
        Session._run_tool = Session._run_tool.__wrapped__  # type: ignore
        Session._get_next_decision = Session._get_next_decision.__wrapped__  # type: ignore


def initialize_tracing(
    tracer_provider_kwargs=None,
    exporter_kwargs=None,
    span_processor_kwargs=None,
) -> None:
    """
    Initialize OpenTelemetry tracing with the specified configuration.

    param tracer_provider_kwargs: Dictionary of arguments for the TracerProvider.
    param exporter_kwargs: Dictionary of arguments for the OTLPSpanExporter.
    param span_processor_kwargs: Dictionary of arguments for the BatchSpanProcessor.
    """
    if tracer_provider_kwargs is None:
        tracer_provider_kwargs = {}
    if exporter_kwargs is None:
        exporter_kwargs = {}
    if span_processor_kwargs is None:
        span_processor_kwargs = {}

    # Set up OpenTelemetry tracing
    trace.set_tracer_provider(TracerProvider(**tracer_provider_kwargs))
    tracer_provider = trace.get_tracer_provider()

    # Set up the OTLP exporter
    otlp_exporter = OTLPSpanExporter(
        endpoint=f"{os.getenv('ELASTIC_APM_SERVER_URL', 'http://localhost:8200')}/v1/traces",
        headers={"Authorization": f"Bearer {os.getenv('ELASTIC_APM_TOKEN', '')}"},
        **exporter_kwargs,
    )

    # Set up the span processor
    span_processor = BatchSpanProcessor(otlp_exporter, **span_processor_kwargs)
    tracer_provider.add_span_processor(span_processor)

    # Initialize OpenTelemetry tracing
    NomosInstrumentor().instrument()


def shutdown_tracing() -> None:
    """Shutdown OpenTelemetry tracing and clean up resources."""
    # Uninstrument OpenTelemetry tracing
    NomosInstrumentor().uninstrument()
