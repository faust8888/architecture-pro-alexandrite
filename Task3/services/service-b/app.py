"""
Service B (Calculation) - GET / возвращает ответ сервиса расчёта.
Инструментирован OpenTelemetry; при вызове из service-a принимает контекст трейса из заголовков.
"""
import os
import flask
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

set_global_textmap(TraceContextTextMapPropagator())

app = flask.Flask(__name__)

# OpenTelemetry
resource = Resource.create({"service.name": "service-b"})
provider = TracerProvider(resource=resource)

endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
if endpoint.startswith("http://"):
    endpoint = endpoint.replace("http://", "", 1)
if endpoint.startswith("https://"):
    endpoint = endpoint.replace("https://", "", 1)
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True)))
trace.set_tracer_provider(provider)

FlaskInstrumentor().instrument_app(app)

tracer = trace.get_tracer(__name__, "1.0.0")


@app.route("/", methods=["GET"])
def calculate():
    """GET / — сервис расчёта (имитация расчёта стоимости)."""
    with tracer.start_as_current_span("calculate.get"):
        return flask.jsonify({
            "service": "service-b",
            "message": "calculation",
            "status": "ok",
        })


@app.route("/health", methods=["GET"])
def health():
    return flask.jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
