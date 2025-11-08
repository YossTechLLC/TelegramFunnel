import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { channelService } from '../services/channelService';
import { authService } from '../services/authService';
import api from '../services/api';

interface CurrencyNetworkMappings {
  network_to_currencies: Record<string, Array<{ currency: string; currency_name: string }>>;
  currency_to_networks: Record<string, Array<{ network: string; network_name: string }>>;
  networks_with_names: Record<string, string>;
  currencies_with_names: Record<string, string>;
}

export default function RegisterChannelPage() {
  const navigate = useNavigate();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mappings, setMappings] = useState<CurrencyNetworkMappings | null>(null);

  // Form state
  const [openChannelId, setOpenChannelId] = useState('');
  const [openChannelTitle, setOpenChannelTitle] = useState('');
  const [openChannelDescription, setOpenChannelDescription] = useState('');
  const [closedChannelId, setClosedChannelId] = useState('');
  const [closedChannelTitle, setClosedChannelTitle] = useState('');
  const [closedChannelDescription, setClosedChannelDescription] = useState('');

  const [tierCount, setTierCount] = useState(1);
  const [sub1Price, setSub1Price] = useState('');
  const [sub1Time, setSub1Time] = useState('');
  const [sub2Price, setSub2Price] = useState('');
  const [sub2Time, setSub2Time] = useState('');
  const [sub3Price, setSub3Price] = useState('');
  const [sub3Time, setSub3Time] = useState('');

  const [clientWalletAddress, setClientWalletAddress] = useState('');
  const [clientPayoutCurrency, setClientPayoutCurrency] = useState('');
  const [clientPayoutNetwork, setClientPayoutNetwork] = useState('');

  const [payoutStrategy, setPayoutStrategy] = useState('instant');
  const [payoutThresholdUsd, setPayoutThresholdUsd] = useState('');

  // Load currency/network mappings
  useEffect(() => {
    const loadMappings = async () => {
      try {
        const response = await api.get('/api/mappings/currency-network');
        setMappings(response.data);
        // Removed auto-default logic - will use empty strings from state initialization
      } catch (err) {
        console.error('Failed to load mappings:', err);
        // Do not set defaults on error - let user select manually
      }
    };

    loadMappings();
  }, []);

  const handleLogout = () => {
    authService.logout();
    navigate('/login');
  };

  const handleNetworkChange = (network: string) => {
    setClientPayoutNetwork(network);
    // Dropdowns are independent - no auto-population of currency
  };

  const handleCurrencyChange = (currency: string) => {
    setClientPayoutCurrency(currency);
    // Dropdowns are independent - no auto-population of network
  };

  const handleResetNetwork = () => {
    setClientPayoutNetwork('');
    // Repopulate currencies with all options
  };

  const handleResetCurrency = () => {
    setClientPayoutCurrency('');
    // Repopulate networks with all options
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      // Validate required fields
      if (!openChannelId || !openChannelTitle || !closedChannelId || !closedChannelTitle) {
        throw new Error('Please fill in all required channel fields');
      }

      if (!sub1Price || !sub1Time) {
        throw new Error('Tier 1 price and duration are required');
      }

      if (parseFloat(sub1Price) < 4.99) {
        throw new Error('Tier 1 price must be at least $4.99');
      }

      if (tierCount >= 2 && (!sub2Price || !sub2Time)) {
        throw new Error('Tier 2 price and duration are required when tier count is 2 or 3');
      }

      if (tierCount >= 2 && parseFloat(sub2Price) < 4.99) {
        throw new Error('Tier 2 price must be at least $4.99');
      }

      if (tierCount === 3 && (!sub3Price || !sub3Time)) {
        throw new Error('Tier 3 price and duration are required when tier count is 3');
      }

      if (tierCount === 3 && parseFloat(sub3Price) < 4.99) {
        throw new Error('Tier 3 price must be at least $4.99');
      }

      if (!clientWalletAddress || !clientPayoutCurrency || !clientPayoutNetwork) {
        throw new Error('Please fill in all payment configuration fields');
      }

      if (payoutStrategy === 'threshold' && (!payoutThresholdUsd || parseFloat(payoutThresholdUsd) < 20.00)) {
        throw new Error('Threshold amount must be at least $20.00');
      }

      // Validate channel ID format
      if (!openChannelId.startsWith('-100')) {
        throw new Error('Open channel ID must start with -100');
      }
      if (!closedChannelId.startsWith('-100')) {
        throw new Error('Closed channel ID must start with -100');
      }

      // Build request payload
      const payload = {
        open_channel_id: openChannelId,
        open_channel_title: openChannelTitle,
        open_channel_description: openChannelDescription || '',
        closed_channel_id: closedChannelId,
        closed_channel_title: closedChannelTitle,
        closed_channel_description: closedChannelDescription || '',
        tier_count: tierCount,
        sub_1_price: parseFloat(sub1Price),
        sub_1_time: parseInt(sub1Time),
        sub_2_price: tierCount >= 2 ? parseFloat(sub2Price) : null,
        sub_2_time: tierCount >= 2 ? parseInt(sub2Time) : null,
        sub_3_price: tierCount === 3 ? parseFloat(sub3Price) : null,
        sub_3_time: tierCount === 3 ? parseInt(sub3Time) : null,
        client_wallet_address: clientWalletAddress,
        client_payout_currency: clientPayoutCurrency,
        client_payout_network: clientPayoutNetwork,
        payout_strategy: payoutStrategy as 'instant' | 'threshold',
        payout_threshold_usd: payoutStrategy === 'threshold' ? parseFloat(payoutThresholdUsd) : null,
      };

      await channelService.registerChannel(payload);

      // Success - navigate to dashboard
      navigate('/dashboard');
    } catch (err: any) {
      console.error('Channel registration error:', err);
      setError(err.response?.data?.error || err.message || 'Failed to register channel');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Get available currencies based on selected network (or all if no network selected)
  const availableCurrencies = mappings
    ? clientPayoutNetwork && mappings.network_to_currencies[clientPayoutNetwork]
      ? mappings.network_to_currencies[clientPayoutNetwork]
      : Object.keys(mappings.currencies_with_names).map(curr => ({
          currency: curr,
          currency_name: mappings.currencies_with_names[curr]
        }))
    : [];

  // Get available networks based on selected currency (or all if no currency selected)
  const availableNetworks = mappings
    ? clientPayoutCurrency && mappings.currency_to_networks[clientPayoutCurrency]
      ? mappings.currency_to_networks[clientPayoutCurrency]
      : Object.keys(mappings.networks_with_names).map(net => ({
          network: net,
          network_name: mappings.networks_with_names[net]
        }))
    : [];

  return (
    <div>
      <div className="header">
        <div className="header-content">
          <div className="logo dashboard-logo" onClick={() => navigate('/dashboard')}>PayGatePrime</div>
          <button onClick={handleLogout} className="btn btn-logout">Logout</button>
        </div>
      </div>

      <div className="container" style={{ maxWidth: '800px' }}>
        <div style={{ marginBottom: '24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <h1 style={{ fontSize: '32px', fontWeight: '700' }}>Register New Channel</h1>
            <button onClick={() => navigate('/dashboard')} className="btn btn-green">
              ← Back to Dashboard
            </button>
          </div>
          <p style={{ color: '#666' }}>Set up a new Telegram channel to accept crypto payments</p>
        </div>

        {error && (
          <div className="alert alert-error" style={{ marginBottom: '24px' }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          {/* Open Channel Section */}
          <div className="card" style={{ marginBottom: '24px' }}>
            <h2 style={{ fontSize: '20px', fontWeight: '600', marginBottom: '16px' }}>Open Channel (Public)</h2>
            <p style={{ fontSize: '14px', color: '#666', marginBottom: '16px' }}>
              This is your public announcement channel where users can see subscription options.
            </p>

            <div className="form-group">
              <label>Channel ID *</label>
              <input
                type="text"
                placeholder="-1001234567890"
                value={openChannelId}
                onChange={(e) => setOpenChannelId(e.target.value)}
                required
              />
              <small style={{ color: '#666', fontSize: '12px' }}>Must start with -100</small>
            </div>

            <div className="form-group">
              <label>Channel Title *</label>
              <input
                type="text"
                placeholder="My Public Channel"
                value={openChannelTitle}
                onChange={(e) => setOpenChannelTitle(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label>Channel Description</label>
              <textarea
                placeholder="Description of your public channel"
                value={openChannelDescription}
                onChange={(e) => setOpenChannelDescription(e.target.value)}
                rows={3}
              />
            </div>
          </div>

          {/* Closed Channel Section */}
          <div className="card" style={{ marginBottom: '24px' }}>
            <h2 style={{ fontSize: '20px', fontWeight: '600', marginBottom: '16px' }}>Closed Channel (Private/Paid)</h2>
            <p style={{ fontSize: '14px', color: '#666', marginBottom: '16px' }}>
              This is your private channel where paid subscribers get access to exclusive content.
            </p>

            <div className="form-group">
              <label>Channel ID *</label>
              <input
                type="text"
                placeholder="-1009876543210"
                value={closedChannelId}
                onChange={(e) => setClosedChannelId(e.target.value)}
                required
              />
              <small style={{ color: '#666', fontSize: '12px' }}>Must start with -100</small>
            </div>

            <div className="form-group">
              <label>Channel Title *</label>
              <input
                type="text"
                placeholder="My VIP Channel"
                value={closedChannelTitle}
                onChange={(e) => setClosedChannelTitle(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label>Channel Description</label>
              <textarea
                placeholder="Description of your private channel"
                value={closedChannelDescription}
                onChange={(e) => setClosedChannelDescription(e.target.value)}
                rows={3}
              />
            </div>
          </div>

          {/* Subscription Tiers Section */}
          <div className="card" style={{ marginBottom: '24px' }}>
            <h2 style={{ fontSize: '20px', fontWeight: '600', marginBottom: '16px' }}>Subscription Tiers</h2>
            <p style={{ fontSize: '14px', color: '#666', marginBottom: '16px' }}>
              Select how many tiers you want to offer and configure their pricing
            </p>

            <div className="form-group">
              <label style={{ display: 'block', marginBottom: '12px' }}>Number of Subscription Tiers *</label>
              <div style={{ display: 'flex', gap: '12px', marginBottom: '8px' }}>
                <button
                  type="button"
                  onClick={() => setTierCount(1)}
                  style={{
                    flex: 1,
                    padding: '12px',
                    border: tierCount === 1 ? '2px solid #4F46E5' : '2px solid #E5E7EB',
                    background: tierCount === 1 ? '#EEF2FF' : 'white',
                    borderRadius: '8px',
                    cursor: 'pointer',
                    fontWeight: tierCount === 1 ? '600' : '400',
                    color: tierCount === 1 ? '#4F46E5' : '#374151',
                    transition: 'all 0.2s'
                  }}
                >
                  1 Tier
                </button>
                <button
                  type="button"
                  onClick={() => setTierCount(2)}
                  style={{
                    flex: 1,
                    padding: '12px',
                    border: tierCount === 2 ? '2px solid #4F46E5' : '2px solid #E5E7EB',
                    background: tierCount === 2 ? '#EEF2FF' : 'white',
                    borderRadius: '8px',
                    cursor: 'pointer',
                    fontWeight: tierCount === 2 ? '600' : '400',
                    color: tierCount === 2 ? '#4F46E5' : '#374151',
                    transition: 'all 0.2s'
                  }}
                >
                  2 Tiers
                </button>
                <button
                  type="button"
                  onClick={() => setTierCount(3)}
                  style={{
                    flex: 1,
                    padding: '12px',
                    border: tierCount === 3 ? '2px solid #4F46E5' : '2px solid #E5E7EB',
                    background: tierCount === 3 ? '#EEF2FF' : 'white',
                    borderRadius: '8px',
                    cursor: 'pointer',
                    fontWeight: tierCount === 3 ? '600' : '400',
                    color: tierCount === 3 ? '#4F46E5' : '#374151',
                    transition: 'all 0.2s'
                  }}
                >
                  3 Tiers
                </button>
              </div>
              <small style={{ color: '#666', fontSize: '12px' }}>
                💡 <strong>Tier 1 (Gold)</strong> is always shown. Add <strong>Tier 2 (Silver)</strong> and <strong>Tier 3 (Bronze)</strong> as needed.
              </small>
            </div>

            {/* Tier 1 (Gold - Always Required) */}
            <div style={{ padding: '16px', background: '#fff9e6', borderRadius: '8px', marginBottom: '16px' }}>
              <h3 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '12px', color: '#d4af37' }}>
                🥇 Gold Tier (Premium)
              </h3>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label>Price (USD) *</label>
                  <input
                    type="number"
                    step="0.01"
                    min="4.99"
                    placeholder="50.00"
                    value={sub1Price}
                    onChange={(e) => setSub1Price(e.target.value)}
                    required
                  />
                  <small style={{ color: '#666', fontSize: '11px' }}>Min: $4.99</small>
                </div>
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label>Duration (Days) *</label>
                  <input
                    type="number"
                    placeholder="30"
                    value={sub1Time}
                    onChange={(e) => setSub1Time(e.target.value)}
                    required
                  />
                </div>
              </div>
            </div>

            {/* Tier 2 (Silver - Conditional) */}
            {tierCount >= 2 && (
              <div style={{ padding: '16px', background: '#f5f5f5', borderRadius: '8px', marginBottom: '16px' }}>
                <h3 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '12px', color: '#c0c0c0' }}>
                  🥈 Silver Tier (Standard)
                </h3>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <div className="form-group" style={{ marginBottom: 0 }}>
                    <label>Price (USD) *</label>
                    <input
                      type="number"
                      step="0.01"
                      min="4.99"
                      placeholder="30.00"
                      value={sub2Price}
                      onChange={(e) => setSub2Price(e.target.value)}
                      required
                    />
                    <small style={{ color: '#666', fontSize: '11px' }}>Min: $4.99</small>
                  </div>
                  <div className="form-group" style={{ marginBottom: 0 }}>
                    <label>Duration (Days) *</label>
                    <input
                      type="number"
                      placeholder="30"
                      value={sub2Time}
                      onChange={(e) => setSub2Time(e.target.value)}
                      required
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Tier 3 (Bronze - Conditional) */}
            {tierCount === 3 && (
              <div style={{ padding: '16px', background: '#fef3f0', borderRadius: '8px' }}>
                <h3 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '12px', color: '#cd7f32' }}>
                  🥉 Bronze Tier (Basic)
                </h3>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <div className="form-group" style={{ marginBottom: 0 }}>
                    <label>Price (USD) *</label>
                    <input
                      type="number"
                      step="0.01"
                      min="4.99"
                      placeholder="15.00"
                      value={sub3Price}
                      onChange={(e) => setSub3Price(e.target.value)}
                      required
                    />
                    <small style={{ color: '#666', fontSize: '11px' }}>Min: $4.99</small>
                  </div>
                  <div className="form-group" style={{ marginBottom: 0 }}>
                    <label>Duration (Days) *</label>
                    <input
                      type="number"
                      placeholder="30"
                      value={sub3Time}
                      onChange={(e) => setSub3Time(e.target.value)}
                      required
                    />
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Payment Configuration Section */}
          <div className="card" style={{ marginBottom: '24px' }}>
            <h2 style={{ fontSize: '20px', fontWeight: '600', marginBottom: '16px' }}>Payment Configuration</h2>
            <p style={{ fontSize: '14px', color: '#666', marginBottom: '16px' }}>
              Your cryptocurrency wallet details for receiving payouts
            </p>

            <div className="form-group">
              <label>Payout Network *</label>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-start' }}>
                <select
                  value={clientPayoutNetwork}
                  onChange={(e) => handleNetworkChange(e.target.value)}
                  required
                  style={{ flex: 1 }}
                >
                  <option value="">-- Select Network --</option>
                  {availableNetworks.map(net => (
                    <option key={net.network} value={net.network}>
                      {net.network} - {net.network_name}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={handleResetNetwork}
                  style={{
                    padding: '10px 14px',
                    border: '1px solid #E5E7EB',
                    background: 'white',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    fontSize: '16px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    transition: 'all 0.2s'
                  }}
                  title="Reset Network Selection"
                >
                  🔄
                </button>
              </div>
              <small style={{ color: '#666', fontSize: '12px' }}>Select the blockchain network for your payouts</small>
            </div>

            <div className="form-group">
              <label>Payout Currency *</label>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-start' }}>
                <select
                  value={clientPayoutCurrency}
                  onChange={(e) => handleCurrencyChange(e.target.value)}
                  required
                  style={{ flex: 1 }}
                >
                  <option value="">-- Select Currency --</option>
                  {availableCurrencies.map(curr => (
                    <option key={curr.currency} value={curr.currency}>
                      {curr.currency} - {curr.currency_name}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={handleResetCurrency}
                  style={{
                    padding: '10px 14px',
                    border: '1px solid #E5E7EB',
                    background: 'white',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    fontSize: '16px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    transition: 'all 0.2s'
                  }}
                  title="Reset Currency Selection"
                >
                  🔄
                </button>
              </div>
              <small style={{ color: '#666', fontSize: '12px' }}>The cryptocurrency you want to receive as payment</small>
            </div>

            <div className="form-group">
              <label>Your Wallet Address *</label>
              <input
                type="text"
                placeholder="0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb"
                value={clientWalletAddress}
                onChange={(e) => setClientWalletAddress(e.target.value)}
                required
              />
              <small style={{ color: '#666', fontSize: '12px' }}>Address where you'll receive payments (max 110 characters)</small>
            </div>
          </div>

          {/* Payout Strategy Section */}
          <div className="card" style={{ marginBottom: '24px' }}>
            <h2 style={{ fontSize: '20px', fontWeight: '600', marginBottom: '16px' }}>Payout Strategy</h2>

            <div className="form-group">
              <label>Strategy *</label>
              <select value={payoutStrategy} onChange={(e) => setPayoutStrategy(e.target.value)} required>
                <option value="instant">Instant - Get paid immediately for each subscription</option>
                <option value="threshold">Threshold - Accumulate payments and batch process to save fees</option>
              </select>
            </div>

            {payoutStrategy === 'threshold' && (
              <div className="form-group">
                <label>Threshold Amount (USD) *</label>
                <input
                  type="number"
                  step="0.01"
                  min="20.00"
                  placeholder="100.00"
                  value={payoutThresholdUsd}
                  onChange={(e) => setPayoutThresholdUsd(e.target.value)}
                  required
                />
                <small style={{ color: '#666', fontSize: '12px' }}>
                  Minimum threshold is $20.00. Payments will accumulate until reaching this amount, then batch process automatically.
                </small>
              </div>
            )}

            {payoutStrategy === 'instant' && (
              <div style={{ padding: '12px', background: '#e7f3ff', borderRadius: '8px', fontSize: '14px', color: '#0066cc' }}>
                ⚡ Each subscription payment will be processed and sent to your wallet immediately
              </div>
            )}
          </div>

          {/* Submit Button */}
          <div style={{ display: 'flex', gap: '12px' }}>
            <button
              type="button"
              onClick={() => navigate('/dashboard')}
              className="btn btn-secondary"
              style={{ flex: 1 }}
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn-green"
              style={{ flex: 2 }}
              disabled={isSubmitting}
            >
              {isSubmitting ? 'Registering...' : 'Register Channel'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
