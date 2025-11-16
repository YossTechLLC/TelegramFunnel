export interface User {
  user_id: string;
  username: string;
  email: string;
  email_verified: boolean;
  created_at?: string;
  last_login?: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface SignupRequest {
  username: string;
  email: string;
  password: string;
}

export interface AuthResponse {
  user_id: string;
  username: string;
  email: string;
  email_verified: boolean;
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface VerificationStatus {
  email_verified: boolean;
  email: string;
  verification_token_expires: string | null;
  can_resend: boolean;
  last_resent_at: string | null;
  resend_count: number;
}

export interface EmailChangeRequest {
  new_email: string;
  password: string;
}

export interface EmailChangeResponse {
  success: boolean;
  message: string;
  pending_email: string;
  notification_sent_to_old: boolean;
  confirmation_sent_to_new: boolean;
}

export interface PasswordChangeRequest {
  current_password: string;
  new_password: string;
  confirm_password: string;
}

export interface PasswordChangeResponse {
  success: boolean;
  message: string;
}
