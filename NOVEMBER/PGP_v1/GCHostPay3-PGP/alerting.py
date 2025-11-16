#!/usr/bin/env python
"""
Alerting Service for GCHostPay3-10-26.
Sends multi-channel notifications when ETH payments fail permanently.
"""
import requests
import json
import time
from typing import Optional


class AlertingService:
    """
    Handles failure notifications via multiple channels:
    - Slack webhook (optional)
    - Cloud Logging structured events (always)
    """

    def __init__(self, slack_webhook_url: Optional[str] = None, alerting_enabled: bool = True):
        """
        Initialize AlertingService.

        Args:
            slack_webhook_url: Optional Slack webhook URL for notifications
            alerting_enabled: Whether alerting is enabled (default: True)
        """
        self.slack_webhook_url = slack_webhook_url
        self.enabled = alerting_enabled

        if self.enabled:
            print(f"✅ [ALERTING] Alerting service initialized")
            if self.slack_webhook_url:
                print(f"📢 [ALERTING] Slack webhook configured")
            else:
                print(f"📝 [ALERTING] Slack webhook not configured (Cloud Logging only)")
        else:
            print(f"⚠️ [ALERTING] Alerting service disabled")

    def send_payment_failure_alert(
        self,
        unique_id: str,
        cn_api_id: str,
        error_code: str,
        error_message: str,
        context: str,
        amount: float,
        from_currency: str,
        payin_address: str,
        attempt_count: int = 3
    ) -> bool:
        """
        Send multi-channel alert for permanent payment failure.

        Channels:
        1. Cloud Logging structured event (always)
        2. Slack webhook (if configured)

        Args:
            unique_id: Unique payment identifier
            cn_api_id: ChangeNow transaction ID
            error_code: Classified error code
            error_message: Raw error message
            context: Payment context (instant/threshold/batch)
            amount: Payment amount
            from_currency: Source currency
            payin_address: ChangeNow payin address
            attempt_count: Number of attempts made (default: 3)

        Returns:
            True if alert sent successfully, False otherwise
        """
        if not self.enabled:
            print(f"⚠️ [ALERT] Alerting disabled - skipping")
            return False

        # Build alert title and body
        alert_title = f"🚨 ETH Payment Failed After {attempt_count} Attempts"
        alert_body = f"""
**Transaction Details:**
- Unique ID: `{unique_id}`
- ChangeNow ID: `{cn_api_id}`
- Context: `{context}`
- Amount: `{amount} {from_currency.upper()}`
- Payin Address: `{payin_address}`

**Failure Details:**
- Error Code: `{error_code}`
- Error Message: `{error_message}`
- Attempts: `{attempt_count}`

**Next Steps:**
1. Review failed transaction in database:
   ```sql
   SELECT * FROM failed_transactions WHERE unique_id='{unique_id}';
   ```
2. Investigate error code: `{error_code}`
3. Decide on recovery action:
   - Manual retry (if transient error)
   - Cancel transaction (if permanent error)
   - Fix upstream service (if configuration issue)

**Database Query:**
```bash
gcloud run services logs read gchostpay3-10-26 --region=us-central1 --filter="jsonPayload.unique_id={unique_id}"
```
        """

        # 1. Log structured event to Cloud Logging (ALWAYS)
        self._log_structured_alert(
            unique_id=unique_id,
            cn_api_id=cn_api_id,
            error_code=error_code,
            error_message=error_message,
            context=context,
            amount=amount,
            from_currency=from_currency,
            payin_address=payin_address,
            attempt_count=attempt_count
        )

        print(f"🚨 [ALERT] {alert_title}")
        print(f"📝 [ALERT] Alert details logged")

        # 2. Send Slack notification (if configured)
        if self.slack_webhook_url:
            slack_success = self._send_slack_alert(alert_title, alert_body)
            return slack_success

        return True  # Cloud Logging always succeeds

    def _log_structured_alert(
        self,
        unique_id: str,
        cn_api_id: str,
        error_code: str,
        error_message: str,
        context: str,
        amount: float,
        from_currency: str,
        payin_address: str,
        attempt_count: int
    ):
        """
        Log structured alert event to Cloud Logging for querying and monitoring.

        This creates a JSON log entry that can be:
        - Queried via Cloud Logging Explorer
        - Used for custom metrics
        - Trigger alert policies
        """
        log_entry = {
            'severity': 'ERROR',
            'event_type': 'eth_payment_failed_permanently',
            'unique_id': unique_id,
            'cn_api_id': cn_api_id,
            'error_code': error_code,
            'error_message': error_message,
            'context': context,
            'amount': amount,
            'from_currency': from_currency,
            'payin_address': payin_address,
            'attempt_count': attempt_count,
            'timestamp': int(time.time()),
            'alert_sent': True
        }

        # Print as JSON for Cloud Logging ingestion
        print(json.dumps(log_entry))

    def _send_slack_alert(self, title: str, body: str) -> bool:
        """
        Send alert to Slack webhook.

        Args:
            title: Alert title
            body: Alert body (markdown formatted)

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            print(f"📢 [ALERT] Sending Slack notification")

            slack_payload = {
                "text": title,
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": title
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": body
                        }
                    },
                    {
                        "type": "divider"
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f"⏰ Alert time: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}"
                            }
                        ]
                    }
                ]
            }

            response = requests.post(
                self.slack_webhook_url,
                json=slack_payload,
                timeout=10,
                headers={'Content-Type': 'application/json'}
            )

            if response.status_code == 200:
                print(f"✅ [ALERT] Slack notification sent successfully")
                return True
            else:
                print(f"❌ [ALERT] Slack notification failed: HTTP {response.status_code}")
                print(f"❌ [ALERT] Response: {response.text}")
                return False

        except requests.exceptions.Timeout:
            print(f"❌ [ALERT] Slack notification timeout (10s)")
            return False

        except requests.exceptions.ConnectionError as e:
            print(f"❌ [ALERT] Slack notification connection error: {e}")
            return False

        except Exception as e:
            print(f"❌ [ALERT] Slack notification unexpected error: {e}")
            return False


# Example usage:
if __name__ == "__main__":
    # Test without Slack webhook
    print("Testing AlertingService (Cloud Logging only)...")
    alerting = AlertingService(alerting_enabled=True)

    alerting.send_payment_failure_alert(
        unique_id="TEST123456789012",
        cn_api_id="test_cn_id_12345",
        error_code="RATE_LIMIT_EXCEEDED",
        error_message="429 Too Many Requests",
        context="instant",
        amount=0.001234,
        from_currency="eth",
        payin_address="0x1234567890abcdef",
        attempt_count=3
    )

    print("\n✅ Test completed")
