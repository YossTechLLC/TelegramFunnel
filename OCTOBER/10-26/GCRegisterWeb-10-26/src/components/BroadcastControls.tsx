import { useState } from 'react';
import { broadcastService } from '../services/broadcastService';

interface BroadcastControlsProps {
  broadcastId: string | null | undefined;
  channelTitle: string;
}

export default function BroadcastControls({ broadcastId, channelTitle }: BroadcastControlsProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error' | 'info'; text: string } | null>(null);
  const [retryAfter, setRetryAfter] = useState<number | null>(null);

  const handleResendMessages = async () => {
    // Validate broadcast_id exists
    if (!broadcastId) {
      setMessage({
        type: 'error',
        text: 'Broadcast not configured for this channel. Please try again later.',
      });
      setTimeout(() => setMessage(null), 5000);
      return;
    }

    // Get JWT token from localStorage
    const token = localStorage.getItem('access_token');
    if (!token) {
      setMessage({
        type: 'error',
        text: 'Authentication required. Please log in again.',
      });
      setTimeout(() => setMessage(null), 5000);
      return;
    }

    // Confirm action
    const confirmed = window.confirm(
      `Resend subscription and donation messages to "${channelTitle}"?\n\nThis will send:\n- Subscription tier buttons to your open channel\n- Donation message to your closed channel\n\nNote: You can only resend messages once every 5 minutes.`
    );

    if (!confirmed) {
      return;
    }

    setIsLoading(true);
    setMessage(null);
    setRetryAfter(null);

    try {
      const response = await broadcastService.triggerBroadcast(broadcastId, token);

      if (response.success) {
        setMessage({
          type: 'success',
          text: 'Messages queued for sending! They will be sent within the next minute.',
        });

        // Clear success message after 5 seconds
        setTimeout(() => setMessage(null), 5000);
      }
    } catch (error: any) {
      console.error('❌ Broadcast trigger failed:', error);

      // Handle rate limiting
      if (error.status === 429) {
        const seconds = error.retryAfterSeconds || 300;
        const minutes = Math.ceil(seconds / 60);

        setRetryAfter(seconds);
        setMessage({
          type: 'info',
          text: `Please wait ${minutes} minute${minutes !== 1 ? 's' : ''} before resending messages again.`,
        });

        // Countdown timer
        const interval = setInterval(() => {
          setRetryAfter((prev) => {
            if (prev === null || prev <= 1) {
              clearInterval(interval);
              setMessage(null);
              return null;
            }
            return prev - 1;
          });
        }, 1000);
      }
      // Handle authentication error
      else if (error.status === 401) {
        setMessage({
          type: 'error',
          text: 'Session expired. Please log in again.',
        });

        // Redirect to login after 2 seconds
        setTimeout(() => {
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          window.location.href = '/login';
        }, 2000);
      }
      // Handle other errors
      else {
        setMessage({
          type: 'error',
          text: error.message || 'Failed to trigger broadcast. Please try again.',
        });
        setTimeout(() => setMessage(null), 5000);
      }
    } finally {
      setIsLoading(false);
    }
  };

  // Format retry countdown
  const formatCountdown = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div style={{ marginTop: '16px' }}>
      <button
        className="btn btn-secondary"
        onClick={handleResendMessages}
        disabled={isLoading || !broadcastId || retryAfter !== null}
        style={{
          width: '100%',
          opacity: (isLoading || !broadcastId || retryAfter !== null) ? 0.6 : 1,
          cursor: (isLoading || !broadcastId || retryAfter !== null) ? 'not-allowed' : 'pointer',
        }}
      >
        {isLoading ? (
          '⏳ Sending...'
        ) : retryAfter !== null ? (
          `⏰ Wait ${formatCountdown(retryAfter)}`
        ) : !broadcastId ? (
          '📭 Not Configured'
        ) : (
          '📬 Resend Messages'
        )}
      </button>

      {message && (
        <div
          style={{
            marginTop: '12px',
            padding: '12px',
            borderRadius: '6px',
            fontSize: '13px',
            lineHeight: '1.5',
            background:
              message.type === 'success'
                ? '#d4edda'
                : message.type === 'error'
                ? '#f8d7da'
                : '#d1ecf1',
            color:
              message.type === 'success'
                ? '#155724'
                : message.type === 'error'
                ? '#721c24'
                : '#0c5460',
            border:
              message.type === 'success'
                ? '1px solid #c3e6cb'
                : message.type === 'error'
                ? '1px solid #f5c6cb'
                : '1px solid #bee5eb',
          }}
        >
          {message.text}
        </div>
      )}
    </div>
  );
}
