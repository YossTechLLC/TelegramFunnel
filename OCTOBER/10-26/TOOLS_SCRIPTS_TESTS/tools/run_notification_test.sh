#!/bin/bash
DB_PASSWORD=$(gcloud secrets versions access latest --secret="DATABASE_PASSWORD_SECRET" --project=telepay-459221)
NOWPAYMENTS_IPN_SECRET=$(gcloud secrets versions access latest --secret="NOWPAYMENTS_IPN_SECRET" --project=telepay-459221)

export DB_PASSWORD
export NOWPAYMENTS_IPN_SECRET

python3 test_notification_flow.py
