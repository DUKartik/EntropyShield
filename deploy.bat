@echo off

echo Starting parallel deployment to asia-south1...

REM Deploy Backend
start /B gcloud run deploy veridoc-backend ^
  --source ./backend ^
  --region asia-south1 ^
  --allow-unauthenticated ^
  --memory 1Gi ^
  --env-vars-file ./backend/.env

REM Deploy Frontend
start /B gcloud run deploy veridoc-frontend ^
  --source ./frontend ^
  --region asia-south1 ^
  --allow-unauthenticated

echo Deployment initiated. Please check the individual windows/logs for completion.
pause
