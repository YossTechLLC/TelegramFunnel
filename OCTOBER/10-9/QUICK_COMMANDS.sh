#!/bin/bash
# Quick Commands for Troubleshooting ChangeNow API Issue

echo "==============================================================================="
echo "QUICK COMMANDS FOR CHANGENOW API TROUBLESHOOTING"
echo "==============================================================================="

# ===== DEPLOYMENT =====

echo -e "\n📦 DEPLOY TPS10-9 WITH ENHANCED LOGGING:"
echo "cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-9/GCSplit7-14"
echo ""
echo "gcloud run deploy tps10-9 \\"
echo "    --source . \\"
echo "    --region us-central1 \\"
echo "    --port 8080 \\"
echo "    --allow-unauthenticated \\"
echo "    --service-account=291176869049-compute@developer.gserviceaccount.com \\"
echo "    --set-env-vars CHANGENOW_API_KEY=projects/291176869049/secrets/CHANGENOW_API_KEY/versions/latest \\"
echo "    --set-env-vars WEBHOOK_SIGNING_KEY=projects/291176869049/secrets/WEBHOOK_SIGNING_KEY/versions/latest \\"
echo "    --set-env-vars TELEGRAM_BOT_USERNAME=projects/291176869049/secrets/TELEGRAM_BOT_USERNAME/versions/latest \\"
echo "    --set-env-vars HPW_WEBHOOK_URL=https://hpw10-9-291176869049.us-central1.run.app/gcsplit"

# ===== VERIFICATION =====

echo -e "\n🔍 CHECK IF TPH10-13 HAS TPS_WEBHOOK_URL:"
echo "gcloud run services describe tph10-13 --region us-central1 --format=\"value(spec.template.spec.containers[0].env)\" | grep TPS_WEBHOOK_URL"

echo -e "\n✅ ADD TPS_WEBHOOK_URL TO TPH10-13 (if missing):"
echo "gcloud run services update tph10-13 \\"
echo "    --region us-central1 \\"
echo "    --set-env-vars TPS_WEBHOOK_URL=https://tps10-9-291176869049.us-central1.run.app"

echo -e "\n🔍 CHECK IF TPS10-9 SERVICE EXISTS:"
echo "gcloud run services list --region us-central1 | grep tps10-9"

echo -e "\n🏥 TEST TPS10-9 HEALTH ENDPOINT:"
echo "curl https://tps10-9-291176869049.us-central1.run.app/health"

echo -e "\n🔍 CHECK CHANGENOW_API_KEY SECRET:"
echo "gcloud secrets versions access latest --secret=\"CHANGENOW_API_KEY\""

echo -e "\n✅ CREATE CHANGENOW_API_KEY SECRET (if missing):"
echo "echo -n \"0e7ab0b9cfd8dd81479e811eb583b01a2b5c7f3aac00d5075225a4241e0a5bde\" | gcloud secrets create CHANGENOW_API_KEY --data-file=-"

# ===== LOG SEARCHING =====

echo -e "\n📋 KEY LOG SEARCHES:"
echo ""
echo "In Cloud Console → Cloud Run → tph10-13 → Logs:"
echo "  Search: \"PAYMENT_SPLITTING\""
echo "  Look for: \"Webhook triggered successfully\" or \"TPS_WEBHOOK_URL not configured\""
echo ""
echo "In Cloud Console → Cloud Run → tps10-9 → Logs:"
echo "  Search: \"CHANGENOW_API\""
echo "  Look for: \"POST /exchange\" and \"Response status:\""

# ===== MANUAL CURL TEST =====

echo -e "\n🧪 TEST CHANGENOW API DIRECTLY (your working curl):"
echo "curl --location 'https://api.changenow.io/v2/exchange' \\"
echo "  --header 'Content-Type: application/json' \\"
echo "  --header 'x-changenow-api-key: 0e7ab0b9cfd8dd81479e811eb583b01a2b5c7f3aac00d5075225a4241e0a5bde' \\"
echo "  --data '{"
echo "      \"fromCurrency\": \"eth\","
echo "      \"toCurrency\": \"link\","
echo "      \"fromNetwork\": \"eth\","
echo "      \"toNetwork\": \"eth\","
echo "      \"fromAmount\": \"0.00024\","
echo "      \"toAmount\": \"\","
echo "      \"address\": \"0xBc29Be20D4F90cF94f994cfADCf24742118C0Fe5\","
echo "      \"extraId\": \"\","
echo "      \"refundAddress\": \"\","
echo "      \"refundExtraId\": \"\","
echo "      \"userId\": \"\","
echo "      \"payload\": \"\","
echo "      \"contactEmail\": \"\","
echo "      \"source\": \"\","
echo "      \"flow\": \"standard\","
echo "      \"type\": \"direct\","
echo "      \"rateId\": \"\""
echo "  }'"

echo -e "\n==============================================================================="
echo "See DEPLOY_AND_TEST_GUIDE.md for complete testing procedure"
echo "See QUICK_REFERENCE_LOGS.md for log patterns to search"
echo "See TROUBLESHOOTING_SUMMARY.md for issue summary"
echo "==============================================================================="
