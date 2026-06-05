# Notes — Chapter 23

## Cardinality is a tax

Each unique label combination is a new time-series. `path=/jobs/<id>`
explodes to one series per id — Prometheus will OOM. Use the route
template (`/jobs/{id}`) or sanitise.

## Sampling tail latency

p99 latency tells you the worst 1% — usually the only experience that
matters for retention. Aggregate over rolling 5-minute windows.

## Centralised logs

Ship JSON logs from stdout to your log aggregator with the cloud
provider's agent (CloudWatch, Stackdriver) or `fluentbit`. Do not
write log files inside the container.

## Tracing in 2 lines

```bash
pip install opentelemetry-instrumentation-fastapi opentelemetry-exporter-otlp
```
```python
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
FastAPIInstrumentor.instrument_app(app)
```

Then point `OTEL_EXPORTER_OTLP_ENDPOINT` at Honeycomb, Tempo,
Datadog, etc. Spans show up immediately.

## Alerting

Alert on **symptoms**, not causes:
- error rate > 1% for 5 min
- p99 latency > 1s for 5 min
- queue depth > N for 5 min

Avoid alerts on "CPU > 80%" — wakes you up for non-problems.
