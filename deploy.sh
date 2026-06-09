#!/bin/bash
# force.nuts.services — Google News, rendered as a Star Wars crawl.
set -e
cd "$(dirname "$0")"

PROJECT_ID="gnosis-459403"
REGION="us-central1"
SERVICE="force"
IMAGE="gcr.io/${PROJECT_ID}/${SERVICE}"
DOMAIN="force.nuts.services"

echo "==> 1. Building + pushing"
gcloud builds submit --tag $IMAGE . --project $PROJECT_ID

echo "==> 2. Deploying"
gcloud run deploy $SERVICE \
  --image $IMAGE \
  --region $REGION \
  --project $PROJECT_ID \
  --platform managed \
  --allow-unauthenticated \
  --port 8080 \
  --memory 256Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 3 \
  --set-env-vars "NUTS_AUTH_URL=https://auth.nuts.services,GRUB_URL=https://grub.nuts.services,RETURN_URL=https://${DOMAIN}/auth,DEFAULT_TOPIC=war,YT_VIDEO_ID=_D0ZQPqeJkk"

echo "==> 3. Domain map (idempotent)"
gcloud beta run domain-mappings create \
  --service $SERVICE \
  --domain $DOMAIN \
  --region $REGION \
  --project $PROJECT_ID 2>/dev/null || echo "(domain mapping may already exist)"

echo "==> 4. Service URL"
gcloud run services describe $SERVICE --region $REGION --project $PROJECT_ID --format 'value(status.url)'
