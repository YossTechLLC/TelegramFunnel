# API Documentation: Verification & Account Management Endpoints

**Version:** 1.0
**Last Updated:** 2025-11-09
**Base URL:** `https://gcregisterapi-10-26-291176869049.us-central1.run.app`

---

## Table of Contents

1. [Authentication Endpoints](#authentication-endpoints)
2. [Verification Endpoints](#verification-endpoints)
3. [Account Management Endpoints](#account-management-endpoints)
4. [Error Codes](#error-codes)
5. [Rate Limiting](#rate-limiting)

---

## Authentication Endpoints

### Modified Endpoints

#### POST /api/auth/signup

**Description:** Create a new user account with automatic login

**Changes from Previous Version:**
- Now returns JWT tokens immediately (auto-login)
- User can access dashboard without email verification
- Email verification required only for account management features

**Request Body:**
```json
{
  "username": "string (3-50 characters)",
  "email": "string (valid email format)",
  "password": "string (min 8 chars, 1 uppercase, 1 lowercase, 1 number, 1 special)"
}
```

**Response:** `200 OK`
```json
{
  "access_token": "eyJhbGci...",
  "refresh_token": "eyJhbGci...",
  "token_type": "Bearer",
  "expires_in": 900,
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "username": "john_doe",
  "email": "john@example.com",
  "email_verified": false,
  "message": "Account created successfully. Please verify your email to unlock all features."
}
```

**Error Responses:**
- `400 Bad Request` - Invalid input data
- `422 Unprocessable Entity` - Validation failed
- `409 Conflict` - Username or email already exists

---

#### POST /api/auth/login

**Description:** Authenticate user and receive JWT tokens

**Changes from Previous Version:**
- Now allows unverified users to login
- Returns `email_verified` status in response

**Request Body:**
```json
{
  "username": "string",
  "password": "string"
}
```

**Response:** `200 OK`
```json
{
  "access_token": "eyJhbGci...",
  "refresh_token": "eyJhbGci...",
  "token_type": "Bearer",
  "expires_in": 900,
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "username": "john_doe",
  "email": "john@example.com",
  "email_verified": true,
  "message": "Login successful"
}
```

**Error Responses:**
- `401 Unauthorized` - Invalid username or password

---

#### GET /api/auth/me

**Description:** Get current user information

**Changes from Previous Version:**
- Now includes `email_verified` field in response

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response:** `200 OK`
```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "username": "john_doe",
  "email": "john@example.com",
  "email_verified": true,
  "created_at": "2025-11-09T10:00:00Z",
  "last_login": "2025-11-09T14:30:00Z"
}
```

**Error Responses:**
- `401 Unauthorized` - Invalid or missing JWT token

---

## Verification Endpoints

### GET /api/auth/verification/status

**Description:** Get detailed email verification status for authenticated user

**Authentication:** Required (JWT)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response:** `200 OK`
```json
{
  "email_verified": false,
  "email": "john@example.com",
  "verification_token_expires": "2025-11-10T10:00:00Z",
  "can_resend": true,
  "last_resent_at": "2025-11-09T09:00:00Z",
  "resend_count": 2
}
```

**Response Fields:**
- `email_verified` (boolean) - Whether email is verified
- `email` (string) - User's email address
- `verification_token_expires` (string|null) - Token expiration datetime (ISO 8601)
- `can_resend` (boolean) - Whether user can resend verification email (rate limit check)
- `last_resent_at` (string|null) - Last time verification email was resent (ISO 8601)
- `resend_count` (integer) - Total number of times verification email has been resent

**Error Responses:**
- `401 Unauthorized` - Invalid or missing JWT token
- `404 Not Found` - User not found

---

### POST /api/auth/verification/resend

**Description:** Resend verification email to authenticated user

**Authentication:** Required (JWT)

**Rate Limit:** 1 request per 5 minutes per user

**Headers:**
```
Authorization: Bearer <access_token>
```

**Request Body:** None (empty body)

**Response:** `200 OK`
```json
{
  "message": "Verification email sent successfully",
  "can_resend_at": "2025-11-09T14:40:00Z"
}
```

**Response Fields:**
- `message` (string) - Success message
- `can_resend_at` (string) - Datetime when user can resend again (ISO 8601)

**Error Responses:**
- `400 Bad Request` - Email already verified
```json
{
  "error": "Email is already verified"
}
```

- `429 Too Many Requests` - Rate limit exceeded
```json
{
  "error": "Please wait before requesting another verification email",
  "retry_after": "2025-11-09T14:40:00Z"
}
```

- `401 Unauthorized` - Invalid or missing JWT token
- `404 Not Found` - User not found
- `500 Internal Server Error` - Email sending failed

---

### GET /api/auth/verify-email

**Description:** Verify user's email address using token from email link

**Authentication:** Not required (uses token from email)

**Query Parameters:**
- `token` (required) - Verification token from email

**Example:**
```
GET /api/auth/verify-email?token=eyJhbGci...
```

**Success Response:** `302 Found` (Redirect to frontend)
- Redirects to: `{FRONTEND_URL}/dashboard?verified=true`

**Error Responses:**
- `400 Bad Request` - Invalid or expired token
  - Redirects to: `{FRONTEND_URL}/dashboard?error=invalid_token`
- `404 Not Found` - User not found
  - Redirects to: `{FRONTEND_URL}/dashboard?error=user_not_found`

---

## Account Management Endpoints

**Note:** All account management endpoints require:
1. Valid JWT authentication
2. Verified email address (email_verified = true)

### POST /api/auth/account/change-email

**Description:** Request email address change (verified users only)

**Authentication:** Required (JWT)

**Email Verification:** Required

**Rate Limit:** 3 requests per hour per user

**Headers:**
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "new_email": "newemail@example.com",
  "password": "CurrentPassword123!"
}
```

**Request Fields:**
- `new_email` (string, required) - New email address (must be valid format)
- `password` (string, required) - Current password for confirmation

**Response:** `200 OK`
```json
{
  "success": true,
  "message": "Email change initiated. Check both email addresses for next steps.",
  "pending_email": "newemail@example.com",
  "notification_sent_to_old": true,
  "confirmation_sent_to_new": true
}
```

**Response Fields:**
- `success` (boolean) - Operation success status
- `message` (string) - User-friendly message
- `pending_email` (string) - New email address pending confirmation
- `notification_sent_to_old` (boolean) - Whether notification sent to old email
- `confirmation_sent_to_new` (boolean) - Whether confirmation sent to new email

**Workflow:**
1. User submits new email and current password
2. System validates: email verified, password correct, new email different, new email not in use
3. System generates secure token (1-hour expiration)
4. System sends notification email to OLD address (security alert with cancel link)
5. System sends confirmation email to NEW address (with confirmation link)
6. User clicks confirmation link in new email to complete change

**Error Responses:**
- `401 Unauthorized` - Invalid password
```json
{
  "error": "Current password is incorrect"
}
```

- `403 Forbidden` - Email not verified
```json
{
  "error": "Email must be verified to change email address"
}
```

- `400 Bad Request` - Validation errors
```json
{
  "error": "New email must be different from current email"
}
```
```json
{
  "error": "Email address is already in use"
}
```

- `422 Unprocessable Entity` - Invalid email format
- `429 Too Many Requests` - Rate limit exceeded
- `500 Internal Server Error` - Email sending failed

---

### GET /api/auth/account/confirm-email-change

**Description:** Confirm email address change using token from email link

**Authentication:** Not required (uses token from email)

**Query Parameters:**
- `token` (required) - Email change confirmation token

**Example:**
```
GET /api/auth/account/confirm-email-change?token=eyJhbGci...
```

**Response:** `200 OK`
```json
{
  "success": true,
  "message": "Email address updated successfully",
  "new_email": "newemail@example.com",
  "redirect_url": "{FRONTEND_URL}/dashboard"
}
```

**Workflow:**
1. User clicks confirmation link in new email
2. System validates token signature and expiration
3. System checks new email still available (race condition check)
4. System atomically updates email and clears pending fields
5. System sends success confirmation to new email
6. User redirected to dashboard

**Error Responses:**
- `400 Bad Request` - Invalid or expired token
```json
{
  "error": "Invalid or expired email change token"
}
```

- `400 Bad Request` - Email no longer available (race condition)
```json
{
  "error": "Email address is no longer available"
}
```

- `404 Not Found` - User not found

---

### POST /api/auth/account/cancel-email-change

**Description:** Cancel pending email address change

**Authentication:** Required (JWT)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Request Body:** None (empty body)

**Response:** `200 OK`
```json
{
  "success": true,
  "message": "Email change cancelled successfully"
}
```

**Error Responses:**
- `401 Unauthorized` - Invalid or missing JWT token
- `404 Not Found` - User not found

---

### POST /api/auth/account/change-password

**Description:** Change account password (verified users only)

**Authentication:** Required (JWT)

**Email Verification:** Required

**Rate Limit:** 5 requests per 15 minutes per user

**Headers:**
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "current_password": "OldPassword123!",
  "new_password": "NewPassword456!"
}
```

**Request Fields:**
- `current_password` (string, required) - Current password for confirmation
- `new_password` (string, required) - New password (min 8 chars, 1 uppercase, 1 lowercase, 1 number, 1 special)

**Response:** `200 OK`
```json
{
  "success": true,
  "message": "Password changed successfully"
}
```

**Workflow:**
1. User submits current and new passwords
2. System validates: email verified, current password correct, new password different, new password meets strength requirements
3. System hashes new password with bcrypt
4. System updates database
5. System sends confirmation email
6. User stays logged in (no re-login required)

**Error Responses:**
- `401 Unauthorized` - Invalid current password
```json
{
  "error": "Current password is incorrect"
}
```

- `403 Forbidden` - Email not verified
```json
{
  "error": "Email must be verified to change password"
}
```

- `400 Bad Request` - Same password
```json
{
  "error": "New password must be different from current password"
}
```

- `422 Unprocessable Entity` - Weak password
```json
{
  "error": "Password must be at least 8 characters and contain uppercase, lowercase, number, and special character"
}
```

- `429 Too Many Requests` - Rate limit exceeded

---

## Error Codes

### Standard Error Response Format

All error responses follow this structure:

```json
{
  "error": "Human-readable error message"
}
```

For validation errors (422):
```json
{
  "error": "Validation failed",
  "details": [
    {
      "field": "email",
      "message": "Invalid email format"
    }
  ]
}
```

### HTTP Status Codes Used

- `200 OK` - Request successful
- `302 Found` - Redirect (verification/email change confirmation)
- `400 Bad Request` - Invalid request data
- `401 Unauthorized` - Authentication required or failed
- `403 Forbidden` - Insufficient permissions (email not verified)
- `404 Not Found` - Resource not found
- `409 Conflict` - Resource conflict (duplicate username/email)
- `422 Unprocessable Entity` - Validation failed
- `429 Too Many Requests` - Rate limit exceeded
- `500 Internal Server Error` - Server error

---

## Rate Limiting

### Rate Limits by Endpoint

| Endpoint | Rate Limit | Window |
|----------|------------|--------|
| POST /api/auth/signup | 5 requests | 15 minutes |
| POST /api/auth/login | 10 requests | 15 minutes |
| GET /api/auth/verify-email | 10 requests | 1 hour |
| POST /api/auth/verification/resend | 1 request | 5 minutes |
| POST /api/auth/account/change-email | 3 requests | 1 hour |
| POST /api/auth/account/change-password | 5 requests | 15 minutes |

### Rate Limit Headers

When rate limited, the response includes:
```
HTTP/1.1 429 Too Many Requests
Content-Type: application/json

{
  "error": "Rate limit exceeded",
  "retry_after": "2025-11-09T14:45:00Z"
}
```

### Rate Limit Strategy

- **Fixed Window:** Rate limits reset at fixed intervals
- **Per-User:** Limits apply per authenticated user (for protected endpoints)
- **Per-IP:** Limits apply per IP address (for public endpoints)
- **Production:** Redis-backed distributed rate limiting
- **Development:** In-memory rate limiting

---

## Security Considerations

### Authentication

- All protected endpoints require valid JWT access token
- Tokens expire after 15 minutes (900 seconds)
- Refresh tokens can be used to obtain new access tokens

### Password Security

- Passwords hashed with bcrypt (cost factor 12)
- Password strength enforced:
  - Minimum 8 characters
  - At least 1 uppercase letter
  - At least 1 lowercase letter
  - At least 1 number
  - At least 1 special character

### Email Verification Security

- Verification tokens signed with HMAC-SHA256
- Tokens expire after 24 hours
- Tokens are single-use (cleared after verification)
- User enumeration protected (generic error messages)

### Email Change Security

- Dual-factor email verification (old + new email)
- Password re-authentication required
- Email change tokens expire after 1 hour
- Race condition protection (re-check email availability)
- Pending email tracked to prevent conflicts

### Audit Logging

All security-sensitive operations are logged:
- User signup, login, logout
- Email verification attempts
- Email change requests, confirmations, cancellations
- Password change attempts
- Failed authentication attempts
- Rate limit violations

---

## Examples

### Complete Signup → Verification → Email Change Flow

```bash
# 1. Signup (receives tokens immediately)
curl -X POST https://api.example.com/api/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "username": "john_doe",
    "email": "john@example.com",
    "password": "SecurePass123!"
  }'

# Response includes access_token, email_verified: false

# 2. Check verification status
curl -X GET https://api.example.com/api/auth/verification/status \
  -H "Authorization: Bearer <access_token>"

# 3. Resend verification email (if needed)
curl -X POST https://api.example.com/api/auth/verification/resend \
  -H "Authorization: Bearer <access_token>"

# 4. User clicks link in email
# GET /api/auth/verify-email?token=... (handled by clicking email link)

# 5. Change email (now that email is verified)
curl -X POST https://api.example.com/api/auth/account/change-email \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "new_email": "john.doe@example.com",
    "password": "SecurePass123!"
  }'

# 6. User clicks confirmation link in new email
# GET /api/auth/account/confirm-email-change?token=... (handled by clicking email link)

# 7. Change password
curl -X POST https://api.example.com/api/auth/account/change-password \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "current_password": "SecurePass123!",
    "new_password": "NewSecurePass456!"
  }'
```

---

## Frontend Integration Notes

### Required Frontend Pages

1. **Signup Page** - Already exists, now stores tokens
2. **Login Page** - Already exists, no changes needed
3. **Dashboard Page** - Already exists, add Header component
4. **Verification Status Page** - New page at `/verification`
5. **Account Management Page** - New page at `/account/manage`
6. **Email Change Confirm Page** - New page at `/confirm-email-change`

### Required Frontend Components

1. **Header Component** - Shows verification status button (yellow/green)
2. **VerificationStatusPage** - Shows status, resend button, rate limit info
3. **AccountManagePage** - Email change form, password change form

### localStorage Token Storage

```typescript
// After signup or login
localStorage.setItem('access_token', response.access_token);
localStorage.setItem('refresh_token', response.refresh_token);

// Attach to all requests
axios.defaults.headers.common['Authorization'] = `Bearer ${localStorage.getItem('access_token')}`;
```

### Verification Status Check

```typescript
// On dashboard load
const user = await authService.getCurrentUser();
if (!user.email_verified) {
  // Show yellow verification button in header
  // Redirect to /verification if accessing /account/manage
}
```

---

**End of Documentation**

*For implementation details, see: VERIFICATION_ARCHITECTURE_1.md*
*For testing details, see: tests/test_api_verification.py, tests/test_api_account.py*
