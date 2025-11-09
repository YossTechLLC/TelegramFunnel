import { useNavigate } from 'react-router-dom';
import { authService } from '../services/authService';
import './Header.css';

interface HeaderProps {
  user?: {
    username: string;
    email_verified: boolean;
  };
}

export default function Header({ user }: HeaderProps) {
  const navigate = useNavigate();

  const handleLogout = () => {
    authService.logout();
    navigate('/login');
  };

  const handleVerificationClick = () => {
    if (user?.email_verified) {
      navigate('/account/manage');
    } else {
      navigate('/verification');
    }
  };

  return (
    <header className="app-header">
      <div className="header-content">
        <div className="header-logo" onClick={() => navigate('/dashboard')}>
          <h2>PayGatePrime</h2>
        </div>

        {user && (
          <div className="header-user">
            <button
              onClick={handleVerificationClick}
              className={`btn ${user.email_verified ? 'btn-verified' : 'btn-verify'}`}
            >
              {user.email_verified ? 'Verified | Manage Account Settings' : 'Please Verify E-Mail'}
            </button>

            <button onClick={handleLogout} className="btn btn-logout">
              Logout
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
