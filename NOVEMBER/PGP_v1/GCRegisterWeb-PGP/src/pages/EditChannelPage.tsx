import { useState, useEffect, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import debounce from 'lodash/debounce';
import { channelService } from '../services/channelService';
import { authService } from '../services/authService';
import api from '../services/api';
import { detectNetworkFromAddress, detectPrivateKey, validateWalletAddress } from '../utils/walletAddressValidator';
import Header from '../components/Header';

interface CurrencyNetworkMappings {
  network_to_currencies: Record<string, Array<{ currency: string; currency_name: string }>>;
  currency_to_networks: Record<string, Array<{ network: string; network_name: string }>>;
  networks_with_names: Record<string, string>;
  currencies_with_names: Record<string, string>;
}

export default function EditChannelPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { channelId } = useParams<{ channelId: string }>();

  // Fetch current user data for Header component
  const { data: userData } = useQuery({
    queryKey: ['currentUser'],
    queryFn: authService.getCurrentUser,
  });

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
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

  // Wallet validation state
  const [validationWarning, setValidationWarning] = useState('');
  const [validationSuccess, setValidationSuccess] = useState('');
  const [initialLoadComplete, setInitialLoadComplete] = useState(false);

  // Load channel data and mappings
  useEffect(() => {
    const loadData = async () => {
      try {
        setIsLoading(true);

        // Load mappings
        const mappingsResponse = await api.get('/api/mappings/currency-network');
        setMappings(mappingsResponse.data);

        // Load channel data
        if (!channelId) {
          throw new Error('No channel ID provided');
        }

        const channel = await channelService.getChannel(channelId);

        // Populate form with existing data
        setOpenChannelId(channel.open_channel_id);
        setOpenChannelTitle(channel.open_channel_title);
        setOpenChannelDescription(channel.open_channel_description || '');
        setClosedChannelId(channel.closed_channel_id);
        setClosedChannelTitle(channel.closed_channel_title);
        setClosedChannelDescription(channel.closed_channel_description || '');

        // Determine tier count based on which tiers have values
        let calculatedTierCount = 1;
        if (channel.sub_3_price !== null && channel.sub_3_time !== null) {
          calculatedTierCount = 3;
        } else if (channel.sub_2_price !== null && channel.sub_2_time !== null) {
          calculatedTierCount = 2;
        }
        setTierCount(calculatedTierCount);

        setSub1Price(channel.sub_1_price.toString());
        setSub1Time(channel.sub_1_time.toString());
        setSub2Price(channel.sub_2_price?.toString() || '');
        setSub2Time(channel.sub_2_time?.toString() || '');
        setSub3Price(channel.sub_3_price?.toString() || '');
        setSub3Time(channel.sub_3_time?.toString() || '');

        setClientWalletAddress(channel.client_wallet_address);
        setClientPayoutCurrency(channel.client_payout_currency);
        setClientPayoutNetwork(channel.client_payout_network);

        setPayoutStrategy(channel.payout_strategy);
        setPayoutThresholdUsd(channel.payout_threshold_usd?.toString() || '');

        setIsLoading(false);
        setInitialLoadComplete(true); // Mark initial load complete
      } catch (err: any) {
        console.error('Failed to load channel data:', err);
        setError(err.response?.data?.error || err.message || 'Failed to load channel');
        setIsLoading(false);
      }
    };

    loadData();
  }, [channelId]);

  // Auto-populate currency based on detected network
  const autoPopulateCurrency = (detectedNetwork: string) => {
    if (!mappings) return;

    const availableCurrencies = mappings.network_to_currencies[detectedNetwork] || [];

    if (availableCurrencies.length === 1) {
      // Only one currency available - safe to auto-populate
      setClientPayoutCurrency(availableCurrencies[0].currency);
      setValidationSuccess(
        `✅ Auto-selected ${availableCurrencies[0].currency_name} (only currency on ${detectedNetwork})`
      );
    } else if (availableCurrencies.length > 1) {
      // Multiple currencies available - just show info
      setValidationSuccess(
        `✅ Detected ${detectedNetwork} network. Please select your payout currency from ${availableCurrencies.length} options.`
      );
    }
  };

  // Debounced wallet address validation
  // Only triggers on user changes (not on initial load)
  const debouncedDetection = useCallback(
    debounce((address: string) => {
      // Don't validate on initial load - only when user changes the address
      if (!initialLoadComplete) {
        return;
      }

      // Clear previous messages
      setValidationWarning('');
      setValidationSuccess('');

      // Too short to validate
      if (address.trim().length < 26) {
        return;
      }

      // Check for private key first (security)
      if (detectPrivateKey(address)) {
        setValidationWarning('⛔ NEVER share your private key! This appears to be a private key, not a public address.');
        return;
      }

      // Detect network from address format
      const detection = detectNetworkFromAddress(address);

      // Handle detection results
      if (detection.networks.length === 0) {
        setValidationWarning('⚠️ Address format not recognized. Please verify your wallet address.');
      } else if (detection.networks.length === 1 && detection.confidence === 'high') {
        // Single network detected with high confidence - auto-populate
        const detectedNetwork = detection.networks[0];

        // Check if user already selected a different network
        if (clientPayoutNetwork && clientPayoutNetwork !== detectedNetwork) {
          // Conflict detected
          setValidationWarning(
            `⚠️ Address appears to be for ${detectedNetwork} network, but you selected ${clientPayoutNetwork}. Please verify.`
          );
        } else {
          // Auto-populate network
          setClientPayoutNetwork(detectedNetwork);

          // Try to auto-populate currency as well
          autoPopulateCurrency(detectedNetwork);
        }
      } else if (detection.ambiguous) {
        if (detection.networks.includes('ETH')) {
          // EVM case - don't auto-populate
          setValidationWarning(
            `ℹ️ EVM address detected. Compatible with: ${detection.networks.join(', ')}. Please select your network.`
          );
        } else {
          // Other ambiguous cases
          setValidationWarning(
            `ℹ️ Address could be for: ${detection.networks.join(', ')}. Please select the correct network.`
          );
        }
      }
    }, 300),
    [initialLoadComplete, clientPayoutNetwork, mappings]
  );

  const handleNetworkChange = (network: string) => {
    setClientPayoutNetwork(network);

    // Check if manually selected network conflicts with detected network
    if (clientWalletAddress.trim().length >= 26) {
      const detection = detectNetworkFromAddress(clientWalletAddress);

      if (detection.networks.length === 1 && detection.confidence === 'high') {
        const detectedNetwork = detection.networks[0];
        if (network !== detectedNetwork) {
          setValidationWarning(
            `⚠️ Manually selected ${network}, but address format appears to be ${detectedNetwork}. Please verify.`
          );
        } else {
          // Network matches - clear warning and try to auto-populate currency
          setValidationWarning('');
          autoPopulateCurrency(network);
        }
      }
    }
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
      // Validate wallet address format and checksum
      const walletValidation = validateWalletAddress(clientWalletAddress, clientPayoutNetwork);
      if (!walletValidation.valid) {
        throw new Error(walletValidation.error || 'Invalid wallet address');
      }

      // Validate required fields
      if (!openChannelTitle || !closedChannelTitle) {
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

      // Build request payload (channel IDs and tier_count cannot be changed)
      // NOTE: tier_count is calculated dynamically from sub_X_price fields
      const payload = {
        open_channel_title: openChannelTitle,
        open_channel_description: openChannelDescription || '',
        closed_channel_title: closedChannelTitle,
        closed_channel_description: closedChannelDescription || '',
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

      if (!channelId) {
        throw new Error('No channel ID provided');
      }

      await channelService.updateChannel(channelId, payload);

      // Invalidate channels cache to trigger refetch on dashboard
      await queryClient.invalidateQueries({ queryKey: ['channels'] });

      // Success - navigate to dashboard
      navigate('/dashboard');
    } catch (err: any) {
      console.error('Channel update error:', err);
      setError(err.response?.data?.error || err.message || 'Failed to update channel');
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

  if (isLoading) {
    return (
      <div>
        <Header user={userData ? { username: userData.username, email_verified: userData.email_verified } : undefined} />
        <div className="container" style={{ textAlign: 'center', padding: '48px 0' }}>
          <p style={{ fontSize: '18px', color: '#666' }}>Loading channel data...</p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <Header user={userData ? { username: userData.username, email_verified: userData.email_verified } : undefined} />

      <div className="container" style={{ maxWidth: '800px' }}>
        <div style={{ marginBottom: '24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <h1 style={{ fontSize: '32px', fontWeight: '700', flex: '2 1 0%' }}>Edit Channel</h1>
            <button onClick={() => navigate('/dashboard')} className="btn btn-green" style={{ flex: '1 1 0%' }}>
              ← Back to Dashboard
            </button>
          </div>
          <p style={{ color: '#666' }}>Update your Telegram channel configuration</p>
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
              <label>Channel ID</label>
              <input
                type="text"
                value={openChannelId}
                disabled
                style={{ background: '#f5f5f5', cursor: 'not-allowed' }}
              />
              <small style={{ color: '#666', fontSize: '12px' }}>Channel IDs cannot be changed</small>
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
              <label>Channel ID</label>
              <input
                type="text"
                value={closedChannelId}
                disabled
                style={{ background: '#f5f5f5', cursor: 'not-allowed' }}
              />
              <small style={{ color: '#666', fontSize: '12px' }}>Channel IDs cannot be changed</small>
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
                placeholder="Paste your wallet address here"
                value={clientWalletAddress}
                onChange={(e) => {
                  setClientWalletAddress(e.target.value);
                  debouncedDetection(e.target.value);
                }}
                onPaste={(e) => {
                  e.preventDefault();
                  const pastedText = e.clipboardData.getData('text');
                  setClientWalletAddress(pastedText);
                  debouncedDetection(pastedText);
                }}
                required
              />
              <small style={{ color: '#666', fontSize: '12px' }}>Address where you'll receive payments (max 110 characters)</small>

              {/* Validation messages */}
              {validationWarning && (
                <div style={{
                  color: '#f59e0b',
                  fontSize: '13px',
                  marginTop: '8px',
                  padding: '8px',
                  background: '#fef3c7',
                  borderRadius: '4px',
                  borderLeft: '3px solid #f59e0b'
                }}>
                  {validationWarning}
                </div>
              )}
              {validationSuccess && (
                <div style={{
                  color: '#10b981',
                  fontSize: '13px',
                  marginTop: '8px',
                  padding: '8px',
                  background: '#d1fae5',
                  borderRadius: '4px',
                  borderLeft: '3px solid #10b981'
                }}>
                  {validationSuccess}
                </div>
              )}
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
              {isSubmitting ? 'Updating...' : 'Update Channel'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
