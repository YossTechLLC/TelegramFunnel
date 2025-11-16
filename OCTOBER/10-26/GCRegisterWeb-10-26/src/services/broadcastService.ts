import axios from 'axios';

/**
 * Broadcast API Service
 *
 * Communicates with GCBroadcastScheduler-10-26 service for manual broadcast triggers
 * and status queries.
 */

const BROADCAST_API_URL = 'https://gcbroadcastscheduler-10-26-291176869049.us-central1.run.app';

interface TriggerBroadcastRequest {
  broadcast_id: string;
}

interface TriggerBroadcastResponse {
  success: boolean;
  message: string;
  broadcast_id?: string;
  queued_for_next_send?: boolean;
  retry_after_seconds?: number; // Present if rate limited
}

interface BroadcastStatusResponse {
  success: boolean;
  broadcast_id: string;
  open_channel_id: string;
  closed_channel_id: string;
  last_sent_time: string | null;
  next_send_time: string;
  broadcast_status: 'pending' | 'in_progress' | 'completed' | 'failed';
  total_broadcasts: number;
  successful_broadcasts: number;
  failed_broadcasts: number;
  last_error_message: string | null;
  is_active: boolean;
}

export const broadcastService = {
  /**
   * Trigger a manual broadcast for a specific channel pair.
   *
   * @param broadcastId - UUID of the broadcast_manager entry
   * @param token - JWT access token for authentication
   * @returns Promise with trigger response
   * @throws Error if broadcast_id is invalid, rate limited, or server error
   */
  async triggerBroadcast(broadcastId: string, token: string): Promise<TriggerBroadcastResponse> {
    try {
      const response = await axios.post<TriggerBroadcastResponse>(
        `${BROADCAST_API_URL}/api/broadcast/trigger`,
        {
          broadcast_id: broadcastId,
        } as TriggerBroadcastRequest,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        }
      );
      return response.data;
    } catch (error: any) {
      // Handle rate limiting (429)
      if (error.response?.status === 429) {
        const retryAfter = error.response.data?.retry_after_seconds || 300;
        throw {
          status: 429,
          message: error.response.data?.error || 'Rate limit exceeded',
          retryAfterSeconds: retryAfter,
        };
      }

      // Handle authentication errors (401)
      if (error.response?.status === 401) {
        throw {
          status: 401,
          message: 'Authentication failed. Please log in again.',
        };
      }

      // Handle server errors (500)
      if (error.response?.status === 500) {
        throw {
          status: 500,
          message: error.response.data?.error || 'Server error occurred',
        };
      }

      // Handle other errors
      throw {
        status: error.response?.status || 0,
        message: error.response?.data?.error || error.message || 'Failed to trigger broadcast',
      };
    }
  },

  /**
   * Get broadcast status for a specific channel pair.
   *
   * @param broadcastId - UUID of the broadcast_manager entry
   * @param token - JWT access token for authentication
   * @returns Promise with broadcast status
   * @throws Error if broadcast_id is invalid, unauthorized, or server error
   */
  async getBroadcastStatus(broadcastId: string, token: string): Promise<BroadcastStatusResponse> {
    try {
      const response = await axios.get<BroadcastStatusResponse>(
        `${BROADCAST_API_URL}/api/broadcast/status/${broadcastId}`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
          },
        }
      );
      return response.data;
    } catch (error: any) {
      // Handle authentication errors (401)
      if (error.response?.status === 401) {
        throw {
          status: 401,
          message: 'Authentication failed. Please log in again.',
        };
      }

      // Handle not found (404)
      if (error.response?.status === 404) {
        throw {
          status: 404,
          message: 'Broadcast not found',
        };
      }

      // Handle server errors (500)
      if (error.response?.status === 500) {
        throw {
          status: 500,
          message: error.response.data?.error || 'Server error occurred',
        };
      }

      // Handle other errors
      throw {
        status: error.response?.status || 0,
        message: error.response?.data?.error || error.message || 'Failed to get broadcast status',
      };
    }
  },
};

export default broadcastService;
