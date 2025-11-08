import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { channelService } from '../services/channelService';
import { authService } from '../services/authService';

export default function DashboardPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deletingChannelId, setDeletingChannelId] = useState<string | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ['channels'],
    queryFn: channelService.getChannels,
  });

  const handleLogout = () => {
    authService.logout();
    navigate('/login');
  };

  const handleDeleteChannel = async (channelId: string, channelTitle: string) => {
    const confirmed = window.confirm(
      `Are you sure you want to delete "${channelTitle}"?\n\nThis action cannot be undone and will remove:\n- All channel configuration\n- All subscriber data\n- All payment history\n\nType DELETE to confirm.`
    );

    if (!confirmed) {
      return;
    }

    setDeletingChannelId(channelId);
    setDeleteError(null);

    try {
      await channelService.deleteChannel(channelId);

      // Invalidate and refetch channels
      await queryClient.invalidateQueries({ queryKey: ['channels'] });

      // Optional: Show success message (you could add a success state if needed)
      console.log('✅ Channel deleted successfully');
    } catch (err: any) {
      console.error('❌ Failed to delete channel:', err);
      setDeleteError(err.response?.data?.error || err.message || 'Failed to delete channel');

      // Clear error after 5 seconds
      setTimeout(() => setDeleteError(null), 5000);
    } finally {
      setDeletingChannelId(null);
    }
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
        {deleteError && (
          <div className="alert alert-error" style={{ marginBottom: '24px' }}>
            {deleteError}
          </div>
        )}

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
                  <button
                    className="btn btn-secondary"
                    style={{ flex: 1 }}
                    onClick={() => navigate(`/edit/${channel.open_channel_id}`)}
                    disabled={deletingChannelId === channel.open_channel_id}
                  >
                    Edit
                  </button>
                  <button
                    className="btn"
                    style={{
                      flex: 1,
                      background: '#DC2626',
                      color: 'white',
                      border: '1px solid #DC2626',
                      transition: 'all 0.2s'
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = '#B91C1C';
                      e.currentTarget.style.borderColor = '#B91C1C';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = '#DC2626';
                      e.currentTarget.style.borderColor = '#DC2626';
                    }}
                    onClick={() => handleDeleteChannel(channel.open_channel_id, channel.open_channel_title)}
                    disabled={deletingChannelId === channel.open_channel_id}
                  >
                    {deletingChannelId === channel.open_channel_id ? 'Deleting...' : '🗑️ Delete'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
