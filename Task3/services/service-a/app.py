"""
Service A (Orders) - при вызове GET / вызывает Service B (расчёт) и возвращает объединённый ответ.
Трейсинг: OpenTelemetry, контекст передаётся в service-b через HTTP-заголовки.
"""
import os
import flask
import requests
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

# Распространение контекста трейса в HTTP-заголовках (service-a -> service-b)
set_global_textmap(TraceContextTextMapPropagator())

app = flask.Flask(__name__)

# OpenTelemetry: ресурс с именем сервиса
resource = Resource.create({"service.name": "service-a"})
provider = TracerProvider(resource=resource)

# Экспорт в Jaeger (OTLP gRPC). Endpoint задаётся через env OTEL_EXPORTER_OTLP_ENDPOINT
endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
if endpoint.startswith("http://"):
    endpoint = endpoint.replace("http://", "", 1)
if endpoint.startswith("https://"):
    endpoint = endpoint.replace("https://", "", 1)
# OTLP gRPC обычно без схемы в экспортере
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True)))
trace.set_tracer_provider(provider)

FlaskInstrumentor().instrument_app(app)
RequestsInstrumentor().instrument()

tracer = trace.get_tracer(__name__, "1.0.0")

SERVICE_B_URL = os.environ.get("SERVICE_B_URL", "http://service-b:8080")


@app.route("/", methods=["GET"])
def orders():
    """GET / — сервис заказов: вызывает сервис расчёта и возвращает объединённый ответ."""
    with tracer.start_as_current_span("orders.get"):
        try:
            resp = requests.get(f"{SERVICE_B_URL}/", timeout=5)
            resp.raise_for_status()
            calculation = resp.json()
        except Exception as e:
            return flask.jsonify({"service": "service-a", "error": str(e)}), 502
        return flask.jsonify({
            "service": "service-a",
            "message": "orders",
            "calculation": calculation,
        })


@app.route("/health", methods=["GET"])
def health():
    return flask.jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
