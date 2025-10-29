import api from './api';
import type { Channel, ChannelRegistrationRequest, ChannelsResponse } from '@/types/channel';

export const channelService = {
  async registerChannel(data: ChannelRegistrationRequest): Promise<{ success: boolean; message: string; channel_id: string }> {
    const response = await api.post('/api/channels/register', data);
    return response.data;
  },

  async getChannels(): Promise<ChannelsResponse> {
    const response = await api.get<ChannelsResponse>('/api/channels');
    return response.data;
  },

  async getChannel(channelId: string): Promise<Channel> {
    const response = await api.get<Channel>(`/api/channels/${channelId}`);
    return response.data;
  },

  async updateChannel(channelId: string, data: Partial<ChannelRegistrationRequest>): Promise<{ success: boolean; message: string; channel: Channel }> {
    const response = await api.put(`/api/channels/${channelId}`, data);
    return response.data;
  },

  async deleteChannel(channelId: string): Promise<{ success: boolean; message: string }> {
    const response = await api.delete(`/api/channels/${channelId}`);
    return response.data;
  },
};
