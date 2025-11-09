import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { authService } from '../services/authService';

export default function VerifyEmailPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState<'verifying' | 'success' | 'error'>('verifying');
  const [message, setMessage] = useState('');

  useEffect(() => {
    const verifyEmail = async () => {
      const token = searchParams.get('token');

      if (!token) {
        setStatus('error');
        setMessage('Verification token is missing');
        return;
      }

      try {
        const response = await authService.verifyEmail(token);
        setStatus('success');
        setMessage(response.message || 'Email verified successfully!');

        // Redirect to login after 3 seconds
        setTimeout(() => {
          navigate('/login');
        }, 3000);
      } catch (err: any) {
        setStatus('error');
        setMessage(err.response?.data?.error || 'Email verification failed');
      }
    };

    verifyEmail();
  }, [searchParams, navigate]);

  return (
    <div className="auth-container">
      <div className="auth-card">
        <h1 className="auth-title">Email Verification</h1>

        {status === 'verifying' && (
          <div className="alert alert-info">
            <div className="spinner"></div>
            <p>Verifying your email address...</p>
          </div>
        )}

        {status === 'success' && (
          <div className="alert alert-success">
            <svg
              className="icon-success"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              width="48"
              height="48"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <h2>✅ {message}</h2>
            <p>You can now log in to your account.</p>
            <p style={{ fontSize: '14px', color: '#666', marginTop: '10px' }}>
              Redirecting to login in 3 seconds...
            </p>
          </div>
        )}

        {status === 'error' && (
          <div className="alert alert-error">
            <svg
              className="icon-error"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              width="48"
              height="48"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <h2>❌ {message}</h2>
            <p>Your verification link may have expired or is invalid.</p>
            <div style={{ marginTop: '20px' }}>
              <Link to="/login" className="btn btn-primary">
                Go to Login
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
