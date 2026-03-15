#!/bin/bash
# Manual deployment script for Cloud Run.
# Uses gcloud run deploy --source . to build from Dockerfile and deploy.
#
# Prerequisites: gcloud CLI, authenticated, Cloud Run API enabled.
# Optional env vars: GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_REGION, CLOUD_RUN_SERVICE

set -e

PROJECT_ID=${GOOGLE_CLOUD_PROJECT:-$(gcloud config get-value project)}
REGION=${GOOGLE_CLOUD_REGION:-us-central1}
SERVICE_NAME=${CLOUD_RUN_SERVICE:-playable-storybook}

echo "Deploying to Cloud Run: $SERVICE_NAME (project: $PROJECT_ID, region: $REGION)"
gcloud run deploy "$SERVICE_NAME" \
  --source . \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300
