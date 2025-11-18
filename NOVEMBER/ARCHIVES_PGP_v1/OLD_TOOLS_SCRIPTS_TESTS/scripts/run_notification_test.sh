#!/bin/bash
DB_PASSWORD=$(gcloud secrets versions access latest --secret="DATABASE_PASSWORD_SECRET" --project=pgp-live)
NOWPAYMENTS_IPN_SECRET=$(gcloud secrets versions access latest --secret="NOWPAYMENTS_IPN_SECRET" --project=pgp-live)

export DB_PASSWORD
export NOWPAYMENTS_IPN_SECRET

python3 test_notification_flow.py
