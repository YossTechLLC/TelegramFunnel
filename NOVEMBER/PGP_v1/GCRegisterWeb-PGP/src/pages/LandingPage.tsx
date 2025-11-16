import { useNavigate } from 'react-router-dom';
import { authService } from '../services/authService';
import { useEffect } from 'react';

export default function LandingPage() {
  const navigate = useNavigate();

  // If user is already logged in, redirect to dashboard
  useEffect(() => {
    if (authService.isAuthenticated()) {
      navigate('/dashboard');
    }
  }, [navigate]);

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #A8E870 0%, #5AB060 100%)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '20px'
    }}>
      <div style={{
        maxWidth: '900px',
        width: '100%',
        background: 'white',
        borderRadius: '16px',
        boxShadow: '0 20px 60px rgba(0, 0, 0, 0.3)',
        padding: '60px 40px',
        textAlign: 'center'
      }}>
        {/* Logo/Title */}
        <div style={{ marginBottom: '40px' }}>
          <h1 style={{
            fontSize: '48px',
            fontWeight: 'bold',
            background: 'linear-gradient(135deg, #1E3A20 0%, #5AB060 100%)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            marginBottom: '16px'
          }}>
            PayGatePrime
          </h1>
          <p style={{
            fontSize: '20px',
            color: '#666',
            fontWeight: '500'
          }}>
            Monetize Your Telegram Channels with Cryptocurrency Payments
          </p>
        </div>

        {/* Key Features */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
          gap: '24px',
          marginBottom: '40px',
          textAlign: 'left'
        }}>
          <div style={{
            padding: '24px',
            border: '1px solid #e5e7eb',
            borderRadius: '12px',
            transition: 'transform 0.2s',
          }}>
            <div style={{ fontSize: '32px', marginBottom: '12px' }}>💰</div>
            <h3 style={{ fontSize: '18px', fontWeight: 'bold', marginBottom: '8px', color: '#1f2937' }}>
              Accept Crypto Payments
            </h3>
            <p style={{ fontSize: '14px', color: '#6b7280' }}>
              Receive payments in ETH, USDT, and other cryptocurrencies for your exclusive Telegram content
            </p>
          </div>

          <div style={{
            padding: '24px',
            border: '1px solid #e5e7eb',
            borderRadius: '12px',
            transition: 'transform 0.2s',
          }}>
            <div style={{ fontSize: '32px', marginBottom: '12px' }}>🔒</div>
            <h3 style={{ fontSize: '18px', fontWeight: 'bold', marginBottom: '8px', color: '#1f2937' }}>
              Tiered Subscriptions
            </h3>
            <p style={{ fontSize: '14px', color: '#6b7280' }}>
              Create up to 3 subscription tiers with custom pricing and durations for your paid channel
            </p>
          </div>

          <div style={{
            padding: '24px',
            border: '1px solid #e5e7eb',
            borderRadius: '12px',
            transition: 'transform 0.2s',
          }}>
            <div style={{ fontSize: '32px', marginBottom: '12px' }}>⚡</div>
            <h3 style={{ fontSize: '18px', fontWeight: 'bold', marginBottom: '8px', color: '#1f2937' }}>
              Instant or Threshold Payouts
            </h3>
            <p style={{ fontSize: '14px', color: '#6b7280' }}>
              Choose instant payouts or accumulate earnings to minimize transaction fees with batch processing
            </p>
          </div>
        </div>

        {/* How It Works */}
        <div style={{
          background: '#f9fafb',
          padding: '32px',
          borderRadius: '12px',
          marginBottom: '40px',
          textAlign: 'left'
        }}>
          <h2 style={{ fontSize: '24px', fontWeight: 'bold', marginBottom: '20px', color: '#1f2937', textAlign: 'center' }}>
            How It Works
          </h2>
          <ol style={{ fontSize: '16px', color: '#4b5563', lineHeight: '1.8', paddingLeft: '20px' }}>
            <li><strong>Sign Up:</strong> Create your free account in seconds</li>
            <li><strong>Register Channels:</strong> Add up to 10 Telegram channels (1 open + 1 closed per channel)</li>
            <li><strong>Set Pricing:</strong> Configure subscription tiers with your preferred cryptocurrency</li>
            <li><strong>Share Link:</strong> Users pay via secure payment gateway and get instant channel access</li>
            <li><strong>Earn Money:</strong> Receive payouts directly to your wallet (instant or accumulated)</li>
          </ol>
        </div>

        {/* CTA Buttons */}
        <div style={{
          display: 'flex',
          gap: '16px',
          justifyContent: 'center',
          flexWrap: 'wrap'
        }}>
          <button
            onClick={() => navigate('/signup')}
            style={{
              padding: '16px 40px',
              fontSize: '18px',
              fontWeight: '600',
              color: 'white',
              background: '#1E3A20',
              border: 'none',
              borderRadius: '8px',
              cursor: 'pointer',
              transition: 'transform 0.2s, box-shadow 0.2s, background 0.2s',
              boxShadow: '0 4px 14px rgba(30, 58, 32, 0.4)'
            }}
            onMouseOver={(e) => {
              e.currentTarget.style.transform = 'translateY(-2px)';
              e.currentTarget.style.boxShadow = '0 6px 20px rgba(30, 58, 32, 0.6)';
              e.currentTarget.style.background = '#2D4A32';
            }}
            onMouseOut={(e) => {
              e.currentTarget.style.transform = 'translateY(0)';
              e.currentTarget.style.boxShadow = '0 4px 14px rgba(30, 58, 32, 0.4)';
              e.currentTarget.style.background = '#1E3A20';
            }}
          >
            Get Started Free
          </button>

          <button
            onClick={() => navigate('/login')}
            style={{
              padding: '16px 40px',
              fontSize: '18px',
              fontWeight: '600',
              color: '#1E3A20',
              background: 'white',
              border: '2px solid #1E3A20',
              borderRadius: '8px',
              cursor: 'pointer',
              transition: 'all 0.2s'
            }}
            onMouseOver={(e) => {
              e.currentTarget.style.background = '#f3f4f6';
            }}
            onMouseOut={(e) => {
              e.currentTarget.style.background = 'white';
            }}
          >
            Login to Dashboard
          </button>
        </div>

        {/* Footer Info */}
        <div style={{
          marginTop: '40px',
          paddingTop: '24px',
          borderTop: '1px solid #e5e7eb',
          fontSize: '14px',
          color: '#9ca3af'
        }}>
          <p>🔐 Secure | ⚡ Fast | 💎 No Monthly Fees</p>
          <p style={{ marginTop: '8px' }}>
            Manage up to 10 channels • Multiple currencies supported • Automated payment processing
          </p>
        </div>
      </div>
    </div>
  );
}
