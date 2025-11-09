import api from './api';
import type {
  AuthResponse,
  LoginRequest,
  SignupRequest,
  User,
  VerificationStatus,
  EmailChangeResponse,
  PasswordChangeResponse,
} from '@/types/auth';

interface VerifyEmailResponse {
  success: boolean;
  message: string;
  redirect_url?: string;
}

interface ResetPasswordResponse {
  success: boolean;
  message: string;
}

export const authService = {
  async login(credentials: LoginRequest): Promise<AuthResponse> {
    const response = await api.post<AuthResponse>('/api/auth/login', credentials);
    const { access_token, refresh_token } = response.data;

    // Store tokens
    localStorage.setItem('access_token', access_token);
    localStorage.setItem('refresh_token', refresh_token);

    return response.data;
  },

  async signup(data: SignupRequest): Promise<AuthResponse> {
    const response = await api.post<AuthResponse>('/api/auth/signup', data);
    const { access_token, refresh_token } = response.data;

    // Store tokens (NEW BEHAVIOR: signup now returns tokens for auto-login)
    localStorage.setItem('access_token', access_token);
    localStorage.setItem('refresh_token', refresh_token);

    return response.data;
  },

  async verifyEmail(token: string): Promise<VerifyEmailResponse> {
    const response = await api.get<VerifyEmailResponse>(`/api/auth/verify-email?token=${token}`);
    return response.data;
  },

  async getCurrentUser(): Promise<User> {
    const response = await api.get<User>('/api/auth/me');
    return response.data;
  },

  async getVerificationStatus(): Promise<VerificationStatus> {
    const response = await api.get<VerificationStatus>('/api/auth/verification/status');
    return response.data;
  },

  async resendVerification(): Promise<{ success: boolean; message: string; can_resend_at?: string }> {
    const response = await api.post('/api/auth/verification/resend');
    return response.data;
  },

  async requestEmailChange(newEmail: string, password: string): Promise<EmailChangeResponse> {
    const response = await api.post<EmailChangeResponse>('/api/auth/account/change-email', {
      new_email: newEmail,
      password,
    });
    return response.data;
  },

  async cancelEmailChange(): Promise<{ success: boolean; message: string }> {
    const response = await api.post('/api/auth/account/cancel-email-change');
    return response.data;
  },

  async changePassword(currentPassword: string, newPassword: string): Promise<PasswordChangeResponse> {
    const response = await api.post<PasswordChangeResponse>('/api/auth/account/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    });
    return response.data;
  },

  async requestPasswordReset(email: string): Promise<{ success: boolean; message: string }> {
    const response = await api.post('/api/auth/forgot-password', { email });
    return response.data;
  },

  async resetPassword(token: string, newPassword: string): Promise<ResetPasswordResponse> {
    const response = await api.post<ResetPasswordResponse>('/api/auth/reset-password', {
      token,
      new_password: newPassword,
    });
    return response.data;
  },

  logout() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
  },

  isAuthenticated(): boolean {
    return !!localStorage.getItem('access_token');
  },
};
