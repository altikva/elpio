#!/usr/bin/env bash
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Install Knative Serving (+ Kourier) and KEDA into the current
#              kube-context, tuned for a fast scale-to-zero so the e2e test
#              completes quickly. Idempotent.
set -euo pipefail

KNATIVE_VERSION="${KNATIVE_VERSION:-v1.15.0}"
KEDA_VERSION="${KEDA_VERSION:-2.15.1}"
KN="https://github.com/knative/serving/releases/download/knative-${KNATIVE_VERSION}"
KOURIER="https://github.com/knative/net-kourier/releases/download/knative-${KNATIVE_VERSION}/kourier.yaml"

echo ">> Knative Serving CRDs + core (${KNATIVE_VERSION})"
kubectl apply -f "${KN}/serving-crds.yaml"
kubectl apply -f "${KN}/serving-core.yaml"

echo ">> Kourier networking layer"
kubectl apply -f "${KOURIER}"
kubectl patch configmap/config-network -n knative-serving --type merge \
  -p '{"data":{"ingress-class":"kourier.ingress.networking.knative.dev"}}'

echo ">> Tight autoscaler windows (fast scale-to-zero for tests)"
kubectl patch configmap/config-autoscaler -n knative-serving --type merge \
  -p '{"data":{"scale-to-zero-grace-period":"30s","stable-window":"30s","enable-scale-to-zero":"true"}}'

echo ">> Waiting for Knative to become Available"
kubectl wait --for=condition=Available deployment --all -n knative-serving --timeout=300s

echo ">> KEDA (${KEDA_VERSION}) for the keda engine"
if kubectl get crd scaledobjects.keda.sh >/dev/null 2>&1; then
  echo "   KEDA already present (e.g. installed via Helm); skipping to avoid apply conflicts"
else
  kubectl apply --server-side -f \
    "https://github.com/kedacore/keda/releases/download/v${KEDA_VERSION}/keda-${KEDA_VERSION}.yaml"
fi

echo ">> Done: Knative + KEDA installed"
