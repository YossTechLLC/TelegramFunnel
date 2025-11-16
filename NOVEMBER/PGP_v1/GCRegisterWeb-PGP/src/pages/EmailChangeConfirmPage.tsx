import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import api from '../services/api';
import './EmailChangeConfirmPage.css';

export default function EmailChangeConfirmPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [message, setMessage] = useState('');
  const [countdown, setCountdown] = useState(3);

  useEffect(() => {
    confirmEmailChange();
  }, []);

  useEffect(() => {
    if (status === 'success' && countdown > 0) {
      const timer = setTimeout(() => {
        setCountdown(countdown - 1);
      }, 1000);
      return () => clearTimeout(timer);
    } else if (status === 'success' && countdown === 0) {
      navigate('/dashboard');
    }
  }, [status, countdown, navigate]);

  const confirmEmailChange = async () => {
    const token = searchParams.get('token');

    if (!token) {
      setStatus('error');
      setMessage('No confirmation token provided');
      return;
    }

    try {
      const response = await api.get(`/api/auth/account/confirm-email-change?token=${token}`);
      setStatus('success');
      setMessage(response.data.message || 'Email changed successfully!');
    } catch (err: any) {
      setStatus('error');
      setMessage(
        err.response?.data?.error ||
        'Failed to confirm email change. The link may have expired or already been used.'
      );
    }
  };

  return (
    <div className="email-confirm-container">
      <div className="email-confirm-card">
        {status === 'loading' && (
          <>
            <div className="spinner"></div>
            <h1>Confirming Email Change...</h1>
            <p>Please wait while we process your request.</p>
          </>
        )}

        {status === 'success' && (
          <>
            <div className="icon-success">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h1 className="title-success">Email Changed Successfully!</h1>
            <p>{message}</p>
            <p className="redirect-notice">
              Redirecting to dashboard in {countdown} seconds...
            </p>
            <button
              onClick={() => navigate('/dashboard')}
              className="btn btn-primary"
            >
              Go to Dashboard Now
            </button>
          </>
        )}

        {status === 'error' && (
          <>
            <div className="icon-error">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </div>
            <h1 className="title-error">Email Change Failed</h1>
            <p>{message}</p>
            <button
              onClick={() => navigate('/dashboard')}
              className="btn btn-secondary"
            >
              Return to Dashboard
            </button>
          </>
        )}
      </div>
    </div>
  );
}
