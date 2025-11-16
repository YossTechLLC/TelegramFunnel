import { useState, useEffect } from 'react';
import { authService } from '../services/authService';
import { useNavigate } from 'react-router-dom';
import type { User } from '../types/auth';
import './AccountManagePage.css';

export default function AccountManagePage() {
  const navigate = useNavigate();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  // Email change state
  const [emailFormData, setEmailFormData] = useState({
    new_email: '',
    password: ''
  });
  const [emailLoading, setEmailLoading] = useState(false);
  const [emailMessage, setEmailMessage] = useState('');
  const [emailError, setEmailError] = useState('');

  // Password change state
  const [passwordFormData, setPasswordFormData] = useState({
    current_password: '',
    new_password: '',
    confirm_password: ''
  });
  const [passwordLoading, setPasswordLoading] = useState(false);
  const [passwordMessage, setPasswordMessage] = useState('');
  const [passwordError, setPasswordError] = useState('');

  useEffect(() => {
    loadUser();
  }, []);

  const loadUser = async () => {
    try {
      const userData = await authService.getCurrentUser();
      setUser(userData);

      // Redirect if not verified
      if (!userData.email_verified) {
        navigate('/verification');
      }
    } catch (err) {
      console.error('Error loading user:', err);
      navigate('/login');
    } finally {
      setLoading(false);
    }
  };

  const handleEmailChange = async (e: React.FormEvent) => {
    e.preventDefault();
    setEmailLoading(true);
    setEmailError('');
    setEmailMessage('');

    try {
      const result = await authService.requestEmailChange(
        emailFormData.new_email,
        emailFormData.password
      );

      setEmailMessage(result.message);
      setEmailFormData({ new_email: '', password: '' });
    } catch (err: any) {
      setEmailError(err.response?.data?.error || 'Failed to request email change');
    } finally {
      setEmailLoading(false);
    }
  };

  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordLoading(true);
    setPasswordError('');
    setPasswordMessage('');

    // Validate passwords match
    if (passwordFormData.new_password !== passwordFormData.confirm_password) {
      setPasswordError('New passwords do not match');
      setPasswordLoading(false);
      return;
    }

    try {
      const result = await authService.changePassword(
        passwordFormData.current_password,
        passwordFormData.new_password
      );

      setPasswordMessage(result.message);
      setPasswordFormData({
        current_password: '',
        new_password: '',
        confirm_password: ''
      });
    } catch (err: any) {
      setPasswordError(err.response?.data?.error || 'Failed to change password');
    } finally {
      setPasswordLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="account-container">
        <div className="loading">Loading...</div>
      </div>
    );
  }

  if (!user || !user.email_verified) {
    return null; // Will redirect
  }

  return (
    <div className="account-container">
      <div className="account-content">
        <h1>Account Management</h1>

        <div className="account-section">
          <h2>Change Email Address</h2>
          <p className="section-description">
            Update your email address. You'll need to verify the new email before the change takes effect.
          </p>

          {emailMessage && <div className="alert alert-success">{emailMessage}</div>}
          {emailError && <div className="alert alert-error">{emailError}</div>}

          <form onSubmit={handleEmailChange}>
            <div className="form-group">
              <label>Current Email</label>
              <input type="email" value={user.email} disabled />
            </div>

            <div className="form-group">
              <label>New Email Address</label>
              <input
                type="email"
                value={emailFormData.new_email}
                onChange={(e) => setEmailFormData({ ...emailFormData, new_email: e.target.value })}
                required
                disabled={emailLoading}
              />
            </div>

            <div className="form-group">
              <label>Confirm Password</label>
              <input
                type="password"
                value={emailFormData.password}
                onChange={(e) => setEmailFormData({ ...emailFormData, password: e.target.value })}
                required
                disabled={emailLoading}
                placeholder="Enter your current password"
              />
            </div>

            <button
              type="submit"
              className="btn btn-primary"
              disabled={emailLoading}
            >
              {emailLoading ? 'Processing...' : 'Request Email Change'}
            </button>
          </form>
        </div>

        <div className="account-section">
          <h2>Change Password</h2>
          <p className="section-description">
            Choose a strong password to keep your account secure.
          </p>

          {passwordMessage && <div className="alert alert-success">{passwordMessage}</div>}
          {passwordError && <div className="alert alert-error">{passwordError}</div>}

          <form onSubmit={handlePasswordChange}>
            <div className="form-group">
              <label>Current Password</label>
              <input
                type="password"
                value={passwordFormData.current_password}
                onChange={(e) => setPasswordFormData({ ...passwordFormData, current_password: e.target.value })}
                required
                disabled={passwordLoading}
              />
            </div>

            <div className="form-group">
              <label>New Password</label>
              <input
                type="password"
                value={passwordFormData.new_password}
                onChange={(e) => setPasswordFormData({ ...passwordFormData, new_password: e.target.value })}
                required
                minLength={8}
                disabled={passwordLoading}
              />
              <small className="form-help">
                Must contain 8+ characters, uppercase, lowercase, and a number
              </small>
            </div>

            <div className="form-group">
              <label>Confirm New Password</label>
              <input
                type="password"
                value={passwordFormData.confirm_password}
                onChange={(e) => setPasswordFormData({ ...passwordFormData, confirm_password: e.target.value })}
                required
                minLength={8}
                disabled={passwordLoading}
              />
            </div>

            <button
              type="submit"
              className="btn btn-primary"
              disabled={passwordLoading}
            >
              {passwordLoading ? 'Changing...' : 'Change Password'}
            </button>
          </form>
        </div>

        <button
          onClick={() => navigate('/dashboard')}
          className="btn btn-secondary"
          style={{ width: '100%', marginTop: '2rem' }}
        >
          Back to Dashboard
        </button>
      </div>
    </div>
  );
}
