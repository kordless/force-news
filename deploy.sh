#!/bin/bash
# force — deploy script
#
# Usage:
#   bash deploy.sh           # default: local (docker compose up)
#   bash deploy.sh local     # spin up grub + force on localhost
#   bash deploy.sh stop      # tear it down
#   bash deploy.sh cloudrun  # build + push + deploy to Google Cloud Run
set -e
cd "$(dirname "$0")"

TARGET="${1:-local}"

case "$TARGET" in

    local)
        echo "==> docker compose up — grub + force"
        docker compose up --build -d
        echo
        echo "  force:  http://localhost:8084   (open this)"
        echo "  grub:   http://localhost:6792"
        echo
        echo "  logs:   docker compose logs -f"
        echo "  stop:   bash deploy.sh stop"
        ;;

    stop)
        echo "==> docker compose down"
        docker compose down
        ;;

    logs)
        docker compose logs -f
        ;;

    cloudrun)
        PROJECT_ID="${PROJECT_ID:-gnosis-459403}"
        REGION="${REGION:-us-central1}"
        SERVICE="${SERVICE:-force}"
        DOMAIN="${DOMAIN:-force.nuts.services}"
        IMAGE="gcr.io/${PROJECT_ID}/${SERVICE}"

        echo "==> 1/3 Building + pushing"
        gcloud builds submit --tag "$IMAGE" . --project "$PROJECT_ID"

        echo "==> 2/3 Deploying to Cloud Run"
        gcloud run deploy "$SERVICE" \
            --image "$IMAGE" \
            --region "$REGION" \
            --project "$PROJECT_ID" \
            --platform managed \
            --allow-unauthenticated \
            --port 8080 \
            --memory 256Mi \
            --cpu 1 \
            --min-instances 0 \
            --max-instances 3 \
            --set-env-vars "NUTS_AUTH_URL=https://auth.nuts.services,GRUB_URL=https://grub.nuts.services,RETURN_URL=https://${DOMAIN}/auth,DEFAULT_TOPIC=war,YT_VIDEO_ID=_D0ZQPqeJkk"

        echo "==> 3/3 Domain map"
        gcloud beta run domain-mappings create \
            --service "$SERVICE" \
            --domain "$DOMAIN" \
            --region "$REGION" \
            --project "$PROJECT_ID" 2>/dev/null || echo "(domain mapping may already exist)"

        echo
        gcloud run services describe "$SERVICE" --region "$REGION" --project "$PROJECT_ID" --format 'value(status.url)'
        ;;

    *)
        echo "Usage: bash deploy.sh [local|stop|logs|cloudrun]"
        echo
        echo "  local      docker compose up — grub + force on localhost  (default)"
        echo "  stop       docker compose down"
        echo "  logs       tail container logs"
        echo "  cloudrun   build + deploy to Google Cloud Run"
        exit 1
        ;;

esac
