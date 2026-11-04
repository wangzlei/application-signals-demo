#!/bin/bash
# set -x
#
# Installs the amazon-cloudwatch-observability stack from the helm chart source.
# Used for testing unreleased add-on versions before they are published to the EKS marketplace.
#
# Required environment variables:
#   HELM_CHART_REF  - git ref (branch, tag, or commit SHA) of aws-observability/helm-charts
#   REGION          - AWS region
#   CLUSTER_NAME    - EKS cluster name
#
# Optional environment variables:
#   OPERATOR_IMAGE  - full operator image URI to override
#                     e.g. "123456789.dkr.ecr.us-east-1.amazonaws.com/staging-operator:integration"
#   HELM_CHART_REPO - git URL of the helm-charts repository to install from
#                     (default: https://github.com/aws-observability/helm-charts.git), e.g. a fork
#   INSTRUMENTATION_INJECTION_MODE - value for manager.instrumentationInjectionMode
#                     (old | injector | comma-separated languages); only set when given, and only
#                     supported by charts that have this value

if [ -z "${HELM_CHART_REF}" ]; then
    echo "ERROR: HELM_CHART_REF is required"
    exit 1
fi

if [ -z "${REGION}" ] || [ -z "${CLUSTER_NAME}" ]; then
    echo "ERROR: REGION and CLUSTER_NAME must be set"
    exit 1
fi

HELM_CHART_REPO="${HELM_CHART_REPO:-https://github.com/aws-observability/helm-charts.git}"

echo "Installing from helm chart at ref: ${HELM_CHART_REF} (${HELM_CHART_REPO})"

# Install helm if not available
if ! command -v helm &> /dev/null; then
    echo "helm not found, installing..."
    if ! curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash; then
        echo "Failed to install helm"
        exit 1
    fi
fi

# Clone the helm-charts repo at the specified ref
HELM_CHARTS_DIR=$(mktemp -d)
echo "Cloning ${HELM_CHART_REPO} at ref ${HELM_CHART_REF}"
if ! git clone --depth 1 --branch "${HELM_CHART_REF}" "${HELM_CHART_REPO}" "${HELM_CHARTS_DIR}" 2>/dev/null; then
    # --branch may fail for a commit SHA; fall back to full clone + checkout
    rm -rf "${HELM_CHARTS_DIR}"
    HELM_CHARTS_DIR=$(mktemp -d)
    if ! git clone "${HELM_CHART_REPO}" "${HELM_CHARTS_DIR}"; then
        echo "Failed to clone helm-charts repo"
        rm -rf "${HELM_CHARTS_DIR}"
        exit 1
    fi
    if ! git -C "${HELM_CHARTS_DIR}" checkout "${HELM_CHART_REF}"; then
        echo "Failed to checkout helm-charts at ref ${HELM_CHART_REF}"
        rm -rf "${HELM_CHARTS_DIR}"
        exit 1
    fi
fi

CHART_PATH="${HELM_CHARTS_DIR}/charts/amazon-cloudwatch-observability"
if [ ! -d "${CHART_PATH}" ]; then
    echo "ERROR: Chart not found at ${CHART_PATH}"
    rm -rf "${HELM_CHARTS_DIR}"
    exit 1
fi

HELM_SET_ARGS=(
    --set "region=${REGION}"
    --set "clusterName=${CLUSTER_NAME}"
)

if [ -n "${OPERATOR_IMAGE}" ]; then
    IMAGE_TAG="${OPERATOR_IMAGE##*:}"
    IMAGE_REPO_FULL="${OPERATOR_IMAGE%:*}"
    IMAGE_DOMAIN="${IMAGE_REPO_FULL%%/*}"
    IMAGE_REPO="${IMAGE_REPO_FULL#*/}"
    HELM_SET_ARGS+=(
        --set "manager.image.repositoryDomainMap.public=${IMAGE_DOMAIN}"
        --set "manager.image.repository=${IMAGE_REPO}"
        --set "manager.image.tag=${IMAGE_TAG}"
    )
    echo "Overriding operator image: ${OPERATOR_IMAGE}"
fi

if [ -n "${INSTRUMENTATION_INJECTION_MODE}" ]; then
    HELM_SET_ARGS+=(--set "manager.instrumentationInjectionMode=${INSTRUMENTATION_INJECTION_MODE}")
    echo "Setting instrumentation injection mode: ${INSTRUMENTATION_INJECTION_MODE}"
fi

# enable-app-signals.sh creates the cloudwatch-agent ServiceAccount (with its IRSA role) via eksctl
# before this script runs; the chart also renders it, so let Helm adopt the existing object.
if kubectl get serviceaccount cloudwatch-agent -n amazon-cloudwatch >/dev/null 2>&1; then
    echo "Adopting existing ServiceAccount amazon-cloudwatch/cloudwatch-agent into the Helm release"
    kubectl label serviceaccount cloudwatch-agent -n amazon-cloudwatch app.kubernetes.io/managed-by=Helm --overwrite
    kubectl annotate serviceaccount cloudwatch-agent -n amazon-cloudwatch \
        meta.helm.sh/release-name=amazon-cloudwatch-observability \
        meta.helm.sh/release-namespace=amazon-cloudwatch --overwrite
fi

echo "Running helm install..."
if ! helm install amazon-cloudwatch-observability "${CHART_PATH}" \
    --namespace amazon-cloudwatch --create-namespace \
    --wait --timeout 5m \
    "${HELM_SET_ARGS[@]}"; then
    echo "Helm install failed!"
    rm -rf "${HELM_CHARTS_DIR}"
    exit 1
fi

echo "Helm chart installed successfully"
rm -rf "${HELM_CHARTS_DIR}"
