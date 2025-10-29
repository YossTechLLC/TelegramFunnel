export interface Channel {
  open_channel_id: string;
  open_channel_title: string;
  open_channel_description: string;
  closed_channel_id: string;
  closed_channel_title: string;
  closed_channel_description: string;
  sub_1_price: number;
  sub_1_time: number;
  sub_2_price?: number | null;
  sub_2_time?: number | null;
  sub_3_price?: number | null;
  sub_3_time?: number | null;
  client_wallet_address: string;
  client_payout_currency: string;
  client_payout_network: string;
  payout_strategy: 'instant' | 'threshold';
  payout_threshold_usd?: number | null;
  accumulated_amount?: number | null;
  created_at?: string;
  updated_at?: string;
}

export interface ChannelRegistrationRequest {
  open_channel_id: string;
  open_channel_title: string;
  open_channel_description: string;
  closed_channel_id: string;
  closed_channel_title: string;
  closed_channel_description: string;
  sub_1_price: number;
  sub_1_time: number;
  sub_2_price?: number | null;
  sub_2_time?: number | null;
  sub_3_price?: number | null;
  sub_3_time?: number | null;
  client_wallet_address: string;
  client_payout_currency: string;
  client_payout_network: string;
  payout_strategy: 'instant' | 'threshold';
  payout_threshold_usd?: number | null;
}

export interface ChannelsResponse {
  channels: Channel[];
  count: number;
  max_channels: number;
}
