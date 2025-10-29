import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { channelService } from '../services/channelService';
import { authService } from '../services/authService';

export default function DashboardPage() {
  const navigate = useNavigate();

  const { data, isLoading, error } = useQuery({
    queryKey: ['channels'],
    queryFn: channelService.getChannels,
  });

  const handleLogout = () => {
    authService.logout();
    navigate('/login');
  };

  if (isLoading) {
    return (
      <div>
        <div className="header">
          <div className="header-content">
            <div className="logo">PayGate Prime</div>
            <button onClick={handleLogout} className="btn btn-secondary">Logout</button>
          </div>
        </div>
        <div className="container">
          <div className="loading">Loading your channels...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div>
        <div className="header">
          <div className="header-content">
            <div className="logo">PayGate Prime</div>
            <button onClick={handleLogout} className="btn btn-secondary">Logout</button>
          </div>
        </div>
        <div className="container">
          <div className="alert alert-error">Failed to load channels</div>
        </div>
      </div>
    );
  }

  const channels = data?.channels || [];
  const channelCount = data?.count || 0;
  const maxChannels = data?.max_channels || 10;

  return (
    <div>
      <div className="header">
        <div className="header-content">
          <div className="logo">PayGate Prime</div>
          <div className="nav">
            <span style={{ color: '#666', fontSize: '14px' }}>
              {channelCount} / {maxChannels} channels
            </span>
            <button onClick={handleLogout} className="btn btn-secondary">Logout</button>
          </div>
        </div>
      </div>

      <div className="container">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
          <h1 style={{ fontSize: '32px', fontWeight: '700' }}>Your Channels</h1>
          {channelCount < maxChannels && (
            <button className="btn btn-primary" onClick={() => navigate('/register')}>+ Add Channel</button>
          )}
        </div>

        {channelCount === 0 ? (
          <div className="card" style={{ textAlign: 'center', padding: '60px 20px' }}>
            <h2 style={{ marginBottom: '16px', color: '#666' }}>No channels yet</h2>
            <p style={{ color: '#999', marginBottom: '24px' }}>
              Register your first Telegram channel to start accepting payments
            </p>
            <button className="btn btn-primary" onClick={() => navigate('/register')}>Register Channel</button>
          </div>
        ) : (
          <div className="channel-grid">
            {channels.map((channel) => (
              <div key={channel.open_channel_id} className="channel-card">
                <div className="channel-header">
                  <div>
                    <div className="channel-title">{channel.open_channel_title}</div>
                    <div className="channel-id">{channel.open_channel_id}</div>
                  </div>
                  <span className="badge badge-success">Active</span>
                </div>

                <div className="tier-list">
                  {channel.sub_1_price && (
                    <div className="tier-item">
                      <span className="tier-label">Gold Tier</span>
                      <span className="tier-value">${channel.sub_1_price} / {channel.sub_1_time}d</span>
                    </div>
                  )}
                  {channel.sub_2_price && (
                    <div className="tier-item">
                      <span className="tier-label">Silver Tier</span>
                      <span className="tier-value">${channel.sub_2_price} / {channel.sub_2_time}d</span>
                    </div>
                  )}
                  {channel.sub_3_price && (
                    <div className="tier-item">
                      <span className="tier-label">Bronze Tier</span>
                      <span className="tier-value">${channel.sub_3_price} / {channel.sub_3_time}d</span>
                    </div>
                  )}
                </div>

                <div style={{ borderTop: '1px solid #f0f0f0', paddingTop: '12px', marginTop: '12px' }}>
                  <div style={{ fontSize: '12px', color: '#666', marginBottom: '4px' }}>Payout</div>
                  <div style={{ fontSize: '14px', fontWeight: '500' }}>
                    {channel.payout_strategy === 'instant' ? 'Instant' : `Threshold ($${channel.payout_threshold_usd})`}
                    {' → '}
                    {channel.client_payout_currency.toUpperCase()}
                  </div>
                </div>

                {channel.payout_strategy === 'threshold' && channel.accumulated_amount !== undefined && channel.accumulated_amount !== null && (
                  <div style={{ marginTop: '12px' }}>
                    <div style={{ fontSize: '12px', color: '#666', marginBottom: '4px' }}>
                      Accumulated: ${channel.accumulated_amount.toFixed(2)} / ${channel.payout_threshold_usd}
                    </div>
                    <div style={{
                      height: '6px',
                      background: '#f0f0f0',
                      borderRadius: '3px',
                      overflow: 'hidden'
                    }}>
                      <div style={{
                        height: '100%',
                        background: '#4CAF50',
                        width: `${Math.min((channel.accumulated_amount / (channel.payout_threshold_usd || 1)) * 100, 100)}%`,
                        transition: 'width 0.3s'
                      }} />
                    </div>
                  </div>
                )}

                <div className="btn-group">
                  <button className="btn btn-secondary" style={{ flex: 1 }}>Edit</button>
                  <button className="btn btn-secondary">Analytics</button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
