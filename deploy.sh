#!/bin/bash
# deploy.sh
# Deployment script for EntropyShield across GCP Cloud Run

set -e

# Default variables
REGION=${REGION:-"asia-south1"}
BACKEND_SERVICE="entropy-backend"
FRONTEND_SERVICE="entropy-frontend"

echo "======================================================"
echo " Starting Deployment of EntropyShield / Veridoc "
echo " Region: $REGION"
echo "======================================================"

echo "[1/4] Ensuring GCP Authentication and Project config..."
PROJECT_ID=$(gcloud config get-value project)
if [ -z "$PROJECT_ID" ]; then
    echo "ERROR: No GCP project configured. Run 'gcloud config set project <PROJECT_ID>'"
    exit 1
fi
echo "Using Project: $PROJECT_ID"

echo ""
echo "[2/4] Deploying Backend to Cloud Run..."
gcloud run deploy $BACKEND_SERVICE \
  --source ./backend \
  --region $REGION \
  --allow-unauthenticated \
  --memory 4Gi \
  --cpu 4 \
  --min-instances 1 \
  --env-vars-file ./backend/.env

echo ""
echo "[3/4] Capturing Backend URL..."
BACKEND_URL=$(gcloud run services describe $BACKEND_SERVICE --region $REGION --format 'value(status.url)')

if [ -z "$BACKEND_URL" ]; then
    echo "ERROR: Failed to retrieve backend URL."
    exit 1
fi
echo "Backend successfully deployed at: $BACKEND_URL"

echo ""
echo "[4/4] Building & Deploying Frontend to Cloud Run..."
# Cloud Build builds the Docker image and injects VITE_API_URL so the UI knows where the backend is
gcloud run deploy $FRONTEND_SERVICE \
  --source ./frontend \
  --region $REGION \
  --allow-unauthenticated \
  --port 8080 \
  --set-build-env-vars="VITE_API_URL=$BACKEND_URL" \
  --set-env-vars BACKEND_URL=$BACKEND_URL

FRONTEND_URL=$(gcloud run services describe $FRONTEND_SERVICE --region $REGION --format 'value(status.url)')

echo ""
echo "======================================================"
echo " DEPLOYMENT COMPLETE! "
echo "======================================================"
echo " Backend URL:  $BACKEND_URL"
echo " Frontend URL: $FRONTEND_URL"
echo "======================================================"
