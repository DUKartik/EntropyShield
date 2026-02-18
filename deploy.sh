#!/bin/bash

# Deploy Backend and Frontend to GCP Cloud Run in parallel

echo "Starting parallel deployment to asia-south1..."

# Deploy Backend
gcloud run deploy veridoc-backend \
  --source ./backend \
  --region asia-south1 \
  --allow-unauthenticated \
  --memory 4Gi \
  --cpu 4 \
  --min-instances 1 \
  --env-vars-file ./backend/.env && \
echo "Backend deployed. Fetching URL..." && \
BACKEND_URL=$(gcloud run services describe veridoc-backend --region asia-south1 --format 'value(status.url)') && \
echo "Backend URL: $BACKEND_URL"

# Deploy Frontend
echo "Deploying Frontend with BACKEND_URL=$BACKEND_URL..."
gcloud run deploy veridoc-frontend \
  --source ./frontend \
  --region asia-south1 \
  --allow-unauthenticated \
  --set-env-vars BACKEND_URL=$BACKEND_URL &

# Wait for frontend deployment
wait

echo "Deployment complete!"
