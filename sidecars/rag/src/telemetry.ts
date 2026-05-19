/* eslint-disable no-console */
import { NodeSDK } from '@opentelemetry/sdk-node';
import { getNodeAutoInstrumentations } from '@opentelemetry/auto-instrumentations-node';
import { ConsoleSpanExporter } from '@opentelemetry/sdk-trace-node';
import { PrometheusExporter } from '@opentelemetry/exporter-prometheus';

const exporter = new PrometheusExporter({
  port: 9465,
});

const sdk = new NodeSDK({
  traceExporter: new ConsoleSpanExporter(),
  metricReader: exporter,
  instrumentations: [getNodeAutoInstrumentations()],
});

export function initTelemetry() {
  sdk.start();
  console.log('OpenTelemetry initialized with Prometheus metrics on port 9465');
}

process.on('SIGTERM', () => {
  sdk
    .shutdown()
    .then(() => {
      console.log('Tracing terminated');
    })
    .catch((error: unknown) => {
      console.log('Error terminating tracing', error);
    })
    .finally(() => process.exit(0));
});
