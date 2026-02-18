#!/bin/bash

# ==========================================
# Deploy TEST Environment to GCP Cloud Run
# ==========================================

# 1. Configuration
BACKEND_SERVICE="veridoc-backend-test"
FRONTEND_SERVICE="veridoc-frontend-test"
REGION="asia-south1"

echo "🚀 Starting TEST deployment to $REGION..."
echo "---------------------------------------"
echo "Select deployment mode:"
echo "1) Both (Backend + Frontend) [Default]"
echo "2) Backend Only"
echo "3) Frontend Only"
read -p "Enter choice [1-3]: " MODE

# Default to 1 if empty
MODE=${MODE:-1}

APP_BACKEND_URL=""

# ==========================================
# 2. Deploy Backend
# ==========================================
if [[ "$MODE" == "1" || "$MODE" == "2" ]]; then
    echo "---------------------------------------"
    echo "📦 Deploying Backend ($BACKEND_SERVICE)..."
    echo "---------------------------------------"

    gcloud run deploy $BACKEND_SERVICE \
      --source ./backend \
      --region $REGION \
      --allow-unauthenticated \
      --memory 4Gi \
      --cpu 4 \
      --min-instances 1 \
      --env-vars-file ./backend/.env

    if [ $? -ne 0 ]; then
        echo "❌ Backend deployment failed."
        exit 1
    fi

    # Get Backend URL
    APP_BACKEND_URL=$(gcloud run services describe $BACKEND_SERVICE --region $REGION --format 'value(status.url)')
    echo "✅ Backend deployed at: $APP_BACKEND_URL"
fi

# ==========================================
# 3. Deploy Frontend
# ==========================================
if [[ "$MODE" == "1" || "$MODE" == "3" ]]; then

    echo "---------------------------------------"
    
    # If backend was not deployed in this run, we need the URL
    if [[ -z "$APP_BACKEND_URL" ]]; then
        read -p "🔗 Enter existing Backend URL (e.g. https://...): " INPUT_URL
        APP_BACKEND_URL=$INPUT_URL
    fi

    # Validation
    if [[ -z "$APP_BACKEND_URL" ]]; then
        echo "❌ Error: Backend URL is required for frontend deployment (to configure API calls)."
        exit 1
    fi

    echo "🔧 Configuring Frontend to point to: $APP_BACKEND_URL"
    # Backup and Temporary Config
    cp frontend/.env.production frontend/.env.production.bak
    echo "VITE_API_URL=$APP_BACKEND_URL" > frontend/.env.production

    echo "📦 Deploying Frontend ($FRONTEND_SERVICE)..."
    
    # Deploy
    gcloud run deploy $FRONTEND_SERVICE \
      --source ./frontend \
      --region $REGION \
      --allow-unauthenticated \
      --set-env-vars BACKEND_URL=$APP_BACKEND_URL

    DEPLOY_STATUS=$?

    # Restore Config
    mv frontend/.env.production.bak frontend/.env.production
    echo "🔄 Restored original frontend/.env.production"

    if [ $DEPLOY_STATUS -ne 0 ]; then
        echo "❌ Frontend deployment failed."
        exit 1
    fi
fi

echo "---------------------------------------"
echo "🎉 Deployment Activity Complete!"
if [[ ! -z "$APP_BACKEND_URL" ]]; then
    echo "Backend URL: $APP_BACKEND_URL"
fi

if [[ "$MODE" == "1" || "$MODE" == "3" ]]; then
    FRONTEND_URL=$(gcloud run services describe $FRONTEND_SERVICE --region $REGION --format 'value(status.url)')
    echo "Frontend URL: $FRONTEND_URL"
fi
echo "---------------------------------------"
