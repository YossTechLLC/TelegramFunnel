import { useState, useEffect } from 'react';
import { authService } from '../services/authService';
import { useNavigate } from 'react-router-dom';
import type { VerificationStatus } from '../types/auth';
import './VerificationStatusPage.css';

export default function VerificationStatusPage() {
  const navigate = useNavigate();
  const [status, setStatus] = useState<VerificationStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [resending, setResending] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    loadStatus();
  }, []);

  const loadStatus = async () => {
    try {
      const data = await authService.getVerificationStatus();
      setStatus(data);
    } catch (err: any) {
      setError('Failed to load verification status');
      console.error('Error loading verification status:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleResendVerification = async () => {
    if (!status?.can_resend) return;

    setResending(true);
    setError('');
    setMessage('');

    try {
      const result = await authService.resendVerification();
      setMessage(result.message || 'Verification email sent successfully');
      // Reload status
      await loadStatus();
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to resend verification email');
    } finally {
      setResending(false);
    }
  };

  const handleManageAccount = () => {
    navigate('/account/manage');
  };

  if (loading) {
    return (
      <div className="verification-container">
        <div className="verification-card">
          <div className="loading">Loading...</div>
        </div>
      </div>
    );
  }

  if (!status) {
    return (
      <div className="verification-container">
        <div className="verification-card">
          <div className="alert alert-error">Failed to load verification status</div>
        </div>
      </div>
    );
  }

  return (
    <div className="verification-container">
      <div className="verification-card">
        {/* Verified State */}
        {status.email_verified && (
          <>
            <div className="status-icon verified">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h1 className="status-title verified">Email Verified</h1>
            <p className="status-description">
              Your email <strong>{status.email}</strong> has been verified.
            </p>

            <button
              onClick={handleManageAccount}
              className="btn btn-primary"
              style={{ width: '100%' }}
            >
              Manage Account Settings
            </button>
          </>
        )}

        {/* Unverified State */}
        {!status.email_verified && (
          <>
            <div className="status-icon unverified">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h1 className="status-title unverified">Email Not Verified</h1>
            <p className="status-description">
              Please verify your email address <strong>{status.email}</strong> to access account management features.
            </p>

            {message && <div className="alert alert-success">{message}</div>}
            {error && <div className="alert alert-error">{error}</div>}

            <div className="verification-info">
              <p>
                {status.resend_count > 0 && (
                  <>Verification emails sent: {status.resend_count}<br /></>
                )}
                {status.last_resent_at && (
                  <>Last sent: {new Date(status.last_resent_at).toLocaleString()}<br /></>
                )}
              </p>
            </div>

            <button
              onClick={handleResendVerification}
              disabled={!status.can_resend || resending}
              className="btn btn-primary"
              style={{ width: '100%' }}
            >
              {resending ? 'Sending...' : 'Resend Verification Email'}
            </button>

            {!status.can_resend && (
              <p className="rate-limit-notice">
                Please wait a few minutes before requesting another verification email.
              </p>
            )}

            <div className="restriction-notice">
              <h3>Account Restrictions</h3>
              <p>
                While your email is unverified, you cannot:
              </p>
              <ul>
                <li>Change your email address</li>
                <li>Change your password</li>
              </ul>
              <p>
                Please verify your email to unlock these features.
              </p>
            </div>
          </>
        )}

        <button
          onClick={() => navigate('/dashboard')}
          className="btn btn-secondary"
          style={{ width: '100%', marginTop: '1rem' }}
        >
          Back to Dashboard
        </button>
      </div>
    </div>
  );
}
