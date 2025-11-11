# Architectural Decisions - TelegramFunnel OCTOBER/10-26

**Last Updated:** 2025-11-11 Session 105 - **Donation Rework: Closed Channel Architecture**

This document records all significant architectural decisions made during the development of the TelegramFunnel payment system.

---

## Table of Contents
1. [Service Architecture](#service-architecture)
2. [Cloud Infrastructure](#cloud-infrastructure)
3. [Data Flow & Orchestration](#data-flow--orchestration)
4. [Security & Authentication](#security--authentication)
5. [Database Design](#database-design)
6. [Error Handling & Resilience](#error-handling--resilience)
7. [User Interface](#user-interface)
8. [Documentation Strategy](#documentation-strategy)
9. [Email Verification & Account Management](#email-verification--account-management)
10. [Deployment Strategy](#deployment-strategy)
11. [Rate Limiting Strategy](#rate-limiting-strategy)
12. [Password Reset Strategy](#password-reset-strategy)
13. [Email Service Configuration](#email-service-configuration)
14. [Donation Architecture](#donation-architecture)

---

## Recent Decisions

### 2025-11-11 Session 105: Donation Rework - Closed Channel Architecture 💝

**Decision:** Migrate donation functionality from open channels to closed channels with inline numeric keypad for custom amount input.

**Context:**
- Previous implementation: Donation button in open channels → ForceReply for amount input
- Problem: ForceReply doesn't work reliably in channels (Telegram limitation)
- User experience: Poor UX with text-based input, prone to errors
- Security concern: Open channel donations exposed sensitive payment flows publicly

**Architectural Decisions:**

#### 1. Channel Separation: Open vs Closed
**Decision:** Separate donation logic from broadcast logic into dedicated modules
- `broadcast_manager.py` → Handles only open channel subscription broadcasts
- `closed_channel_manager.py` → Handles only closed channel donation messages
- **Rationale:**
  - Single Responsibility Principle
  - Easier to maintain and test
  - Clear separation of concerns (subscriptions vs donations)
  - Allows independent evolution of each flow

#### 2. Inline Numeric Keypad UI
**Decision:** Implement calculator-style inline keyboard instead of text input
- **Alternatives Considered:**
  - ForceReply: ❌ Doesn't work in channels
  - Direct text messages: ❌ No validation, error-prone
  - Pre-set amount buttons: ❌ Not flexible enough
- **Chosen Solution:** Inline numeric keypad with real-time validation
- **Rationale:**
  - Works reliably in channels (inline keyboards supported)
  - Real-time validation prevents invalid inputs
  - Intuitive calculator-style UX
  - No need for text parsing or error recovery

#### 3. Input Validation Strategy
**Decision:** Client-side validation in button handlers, no server-side recovery needed
- **Validation Rules:**
  - Min: $1.00, Max: $9999.99
  - Single decimal point only
  - Max 2 decimal places
  - Max 4 digits before decimal
  - Replace leading zeros (e.g., "05" → "5")
- **Implementation:** Button press validation rejects invalid inputs with alerts
- **Rationale:**
  - Prevents invalid states from occurring
  - Better UX (immediate feedback)
  - Simpler error handling (no recovery needed)
  - Reduces server validation burden

#### 4. Security: Channel ID Validation
**Decision:** Validate channel IDs in callback data before processing donations
- **Attack Vector:** Malicious users could craft fake callback data
- **Protection:** `database.channel_exists()` verifies channel before accepting donation
- **Implementation:** Early validation in `start_donation_input()` handler
- **Rationale:**
  - Defense in depth
  - Prevents fake donations to non-existent channels
  - Logs suspicious attempts for monitoring

#### 5. Payment Gateway Integration
**Decision:** Reuse existing `PaymentGatewayManager` with compatible order_id format
- **Order ID Format:** `PGP-{user_id}|{open_channel_id}` (same as subscriptions)
- **Rationale:**
  - No webhook changes required
  - Existing IPN handlers work unchanged
  - Consistent order tracking across donations and subscriptions
  - Simpler testing and deployment

#### 6. State Management
**Decision:** Use `context.user_data` for donation flow state, not database
- **State Stored:**
  - `donation_amount_building`: Current amount being entered
  - `donation_open_channel_id`: Channel for payout routing
  - `donation_started_at`: Timestamp for timeout tracking
  - `is_donation`: Flag to distinguish from subscriptions
- **Rationale:**
  - In-memory state sufficient for short-lived flow
  - No database writes until payment confirmed
  - Simplifies error recovery (state auto-cleared on restart)
  - Reduces database load

#### 7. Error Handling Strategy
**Decision:** Graceful degradation with comprehensive logging
- **Channel-Level Errors:** Continue to next channel if broadcast fails
- **User-Level Errors:** Show user-friendly error messages, log detailed errors
- **Payment Errors:** Fallback to error message, allow user to retry
- **Rationale:**
  - One channel failure shouldn't block others
  - User experience prioritized over perfect accuracy
  - Detailed logs enable post-mortem analysis

#### 8. Module Organization
**Decision:** Two new standalone modules, minimal changes to existing code
- **New Files:**
  - `closed_channel_manager.py` - Broadcast donation messages
  - `donation_input_handler.py` - Handle keypad interactions
- **Modified Files:**
  - `database.py` - Added 2 query methods
  - `broadcast_manager.py` - Removed donation button
  - `app_initializer.py` - Initialize new managers
  - `bot_manager.py` - Register new handlers
- **Rationale:**
  - Minimizes risk of breaking existing functionality
  - New code isolated for easier testing
  - Clear migration path (old code commented, not deleted)

#### 9. Backward Compatibility
**Decision:** Keep old donation code commented, not deleted
- **Location:** `broadcast_manager.py` lines 69-75
- **Rationale:**
  - Easy rollback if critical issues found
  - Historical reference for future developers
  - Documents what was changed and why

#### 10. No Database Schema Changes
**Decision:** Use existing schema, no migrations required
- **Schema Used:**
  - `closed_channel_id` - Already exists in `main_clients_database`
  - `client_payout_strategy` - Already exists
  - `client_payout_threshold_usd` - Already exists
- **Rationale:**
  - Faster implementation
  - Lower deployment risk
  - Existing fields serve donation needs perfectly

**Impact:**
- ✅ Better UX: Calculator-style input vs text input
- ✅ More reliable: Inline keyboard works in channels
- ✅ More secure: Channel ID validation prevents abuse
- ✅ Cleaner architecture: Separation of concerns
- ✅ Easier to maintain: Modular design
- ⬜ Testing required: New code paths need validation

**Trade-offs:**
- Additional code complexity (2 new modules, ~890 lines)
- New callback patterns to monitor (`donate_*`)
- Requires manual testing before production deployment

**Reference Documents:**
- Architecture: `DONATION_REWORK.md`
- Implementation: `DONATION_REWORK_CHECKLIST.md`
- Progress: `DONATION_REWORK_CHECKLIST_PROGRESS.md`

---

### 2025-11-10 Session 104: Email Service BASE_URL Configuration - Critical Fix 📧

**Decision:** Configure `BASE_URL` environment variable for email service to use correct frontend URL in email links.

**Context:**
- Email service (`email_service.py`) generates links for password resets, email verification, and email change confirmations
- `BASE_URL` defaults to `https://app.telepay.com` (non-existent domain) when not explicitly set
- Emails were being sent successfully but contained broken links that users couldn't access

**Problem:**
- **Broken Email Links**: All email links pointed to `https://app.telepay.com` which doesn't exist
- **Password Reset Failure**: Users couldn't reset passwords despite receiving emails
- **Email Verification Failure**: New users couldn't verify email addresses
- **Silent Failure**: Backend logs showed "email sent successfully" but emails were useless

**Root Cause Analysis:**
```python
# email_service.py:42
self.base_url = os.getenv('BASE_URL', 'https://app.telepay.com')  # ❌ Default was wrong

# Line 138 (password reset):
reset_url = f"{self.base_url}/reset-password?token={token}"
# Generated: https://app.telepay.com/reset-password?token=XXX  ❌

# Line 72 (email verification):
verification_url = f"{self.base_url}/verify-email?token={token}"
# Generated: https://app.telepay.com/verify-email?token=XXX  ❌
```

**Solution Implemented:**

1. **Created GCP Secret**: `BASE_URL = "https://www.paygateprime.com"`
   ```bash
   echo -n "https://www.paygateprime.com" | gcloud secrets create BASE_URL --data-file=-
   ```

2. **Updated Backend Service**:
   ```bash
   gcloud run services update gcregisterapi-10-26 \
     --region=us-central1 \
     --update-secrets=BASE_URL=BASE_URL:latest
   ```

3. **New Revision Deployed**: `gcregisterapi-10-26-00023-dmg`

**Affected Email Types:**
- Password reset emails (`send_password_reset_email`)
- Email verification emails (`send_verification_email`)
- Email change confirmation (`send_email_change_confirmation`)
- Email change notification (`send_email_change_notification`)

**Trade-offs:**
- ✅ **Pro**: Emails now contain correct, functional links
- ✅ **Pro**: No code changes required - configuration only
- ✅ **Pro**: Uses GCP Secret Manager for secure configuration
- ⚠️ **Con**: Requires secret update if frontend domain changes
- ⚠️ **Con**: Environment-specific configuration (prod/dev/staging need different values)

**Alternatives Considered:**

1. **Hardcode URL in Code** ❌
   - Would require code changes for each environment
   - Less flexible for testing and deployment

2. **Use Request Headers** ❌
   - Email service runs in background, no active request context
   - Would require significant architectural changes

3. **Configuration File** ❌
   - Harder to manage across multiple environments
   - Less secure than Secret Manager
   - Requires container rebuild for changes

**Why BASE_URL is Critical:**
- Email service operates **independently** of HTTP requests
- No access to request headers or referrer URLs
- Must know frontend URL at runtime to generate valid links
- Same backend may serve multiple frontends (web, mobile, etc.)

**Future Considerations:**
- Consider multi-environment support (dev, staging, prod)
- May need separate BASE_URL for each environment
- Could implement template-based email URLs for more flexibility

**Follow-up: Code Cleanup - Removing CORS_ORIGIN Substitution**

After deploying the BASE_URL secret, discovered that code was using `CORS_ORIGIN` as a substitute for `BASE_URL` (both had identical values).

**Changes Made:**

1. **config_manager.py:67** - Changed to use `BASE_URL` secret instead of `CORS_ORIGIN`
   ```python
   # Before:
   'base_url': self.access_secret('CORS_ORIGIN') if self._secret_exists('CORS_ORIGIN') else ...

   # After:
   'base_url': self.access_secret('BASE_URL') if self._secret_exists('BASE_URL') else ...
   ```

2. **app.py:49** - Changed to use `base_url` config instead of hardcoded default
   ```python
   # Before:
   app.config['FRONTEND_URL'] = config.get('frontend_url', 'https://www.paygateprime.com')

   # After:
   app.config['FRONTEND_URL'] = config['base_url']
   ```

**Rationale:**
- **Semantic Correctness**: CORS_ORIGIN is for CORS security policy, BASE_URL is for application URLs
- **Single Source of Truth**: All frontend URL references now derive from BASE_URL secret
- **Separation of Concerns**: CORS policy and frontend URL are distinct architectural concerns
- **Future Flexibility**: If CORS needs differ from base URL (e.g., allowing multiple origins), changes are isolated

---

### 2025-11-09 Session 103: Password Reset Frontend Implementation - OWASP-Compliant Flow 🔐

**Decision:** Implement frontend password reset flow leveraging existing OWASP-compliant backend implementation.

**Context:**
- Users with verified email addresses had no way to recover forgotten passwords
- Backend already implemented complete OWASP-compliant password reset functionality
- Missing only frontend entry point (ForgotPasswordPage) to initiate the flow

**Problem:**
- **No Password Recovery**: Users locked out of accounts with no recovery method
- **Backend Ready**: `/api/auth/forgot-password` & `/api/auth/reset-password` endpoints fully implemented
- **Partial Frontend**: ResetPasswordPage exists but no way to trigger the flow

**Solution Implemented:**

**Architecture Decisions:**

1. **Anti-User Enumeration Pattern** 🔒
   - ForgotPasswordPage shows identical success message for existing/non-existing accounts
   - Backend returns 200 OK in both cases
   - Prevents attackers from discovering registered email addresses
   - Follows OWASP Forgot Password Cheat Sheet recommendations

2. **Token Security** 🛡️
   - Uses existing `itsdangerous.URLSafeTimedSerializer` from backend
   - Cryptographic signing with secret key + salt (`password-reset-v1`)
   - 1-hour expiration enforced both by itsdangerous and database timestamp
   - Single-use tokens (cleared from DB after successful reset)

3. **User Flow Design** 🔄
   ```
   LoginPage → [Forgot password?] → ForgotPasswordPage
   ↓
   Enter Email → Backend generates token → Email sent
   ↓
   User clicks email link → ResetPasswordPage?token=XXX
   ↓
   Enter new password → Token validated → Password updated → Redirect to Login
   ```

4. **Consistent UI/UX** 🎨
   - ForgotPasswordPage matches styling of LoginPage/SignupPage
   - Uses same `.auth-container` and `.auth-card` classes
   - "Forgot password?" link right-aligned below password field (standard pattern)
   - Success screen with clear instructions

**Files Created:**
- `src/pages/ForgotPasswordPage.tsx` - Email input form + success screen

**Files Modified:**
- `src/App.tsx` - Added route for `/forgot-password`
- `src/pages/LoginPage.tsx` - Added "Forgot password?" link

**Rate Limiting (Inherited from Backend):**
- `/auth/forgot-password`: 3 requests per hour per IP
- `/auth/reset-password`: 5 requests per 15 minutes per IP
- Prevents brute force token guessing

**Trade-offs:**

✅ **Benefits:**
- Complete password recovery functionality for users
- OWASP-compliant security (anti-enumeration, secure tokens)
- Minimal frontend code (leveraged existing backend)
- Consistent with existing verification flow patterns
- Single-use tokens prevent replay attacks

⚠️ **Considerations:**
- Requires SendGrid API key for production email delivery (already configured)
- Dev mode prints reset links to console (acceptable for development)
- Token expiration (1 hour) balances security vs usability

**Alternatives Considered:**

1. **Security Questions** ❌
   - Rejected: Weaker security than email-based reset
   - OWASP discourages security questions (guessable answers)

2. **SMS-Based Reset** ❌
   - Rejected: Adds cost, requires phone number collection
   - Email already verified during registration

3. **Admin-Assisted Reset** ❌
   - Rejected: Poor UX, doesn't scale, privacy concerns

**Future Considerations:**
- Add optional 2FA for password reset (extra verification step)
- Consider rate limiting per email address (not just IP)
- Add audit logging for password reset attempts

**Status**: ✅ IMPLEMENTED

---

### 2025-11-09 Session 99: Rate Limiting Adjustment - Global Limits Increased 3x ⏱️

**Decision:** Increase global default rate limits by 3x to prevent legitimate usage from being blocked.

**Context:**
- Session 87 introduced global rate limiting: 200 req/day, 50 req/hour
- Production usage revealed limits were too restrictive for normal operation
- Dashboard page makes frequent API calls to `/api/auth/me` and `/api/channels`
- Users hitting 50 req/hour limit during normal browsing/testing
- Website appeared broken with "Failed to load channels" error (429 responses)

**Problem:**
- **Overly Restrictive Global Limits**: 50 requests/hour is insufficient for:
  - React app making API calls on every page load/navigation
  - Header component checking auth status frequently
  - Dashboard polling for channel updates
  - Development/testing workflows
- **Poor User Experience**: Legitimate users seeing rate limit errors
- **Endpoint Misalignment**: Read-only endpoints treated same as write endpoints

**Solution Implemented:**

Changed global default limits in `api/middleware/rate_limiter.py`:
```python
# Before (Session 87):
default_limits=["200 per day", "50 per hour"]

# After (Session 99):
default_limits=["600 per day", "150 per hour"]
```

**Rationale:**
1. **3x Multiplier**: Provides headroom for normal usage patterns while still preventing abuse
2. **Hourly Limit**: 150 req/hour = ~2.5 req/minute (reasonable for SPA with multiple components)
3. **Daily Limit**: 600 req/day = ~25 req/hour average (allows burst usage during active sessions)
4. **Security Maintained**: Critical endpoints retain stricter specific limits:
   - `/auth/signup`: 5 per 15 minutes
   - `/auth/login`: 10 per 15 minutes
   - `/auth/resend-verification`: 3 per hour
   - `/auth/verify-email`: 10 per hour

**Trade-offs:**

✅ **Benefits:**
- Normal users won't hit rate limits during legitimate usage
- Better developer experience during testing
- Read-only endpoints can be accessed frequently
- Website functionality restored

⚠️ **Risks (Mitigated):**
- Slightly more exposure to brute force (still have endpoint-specific limits)
- Higher server load potential (Cloud Run auto-scales to handle)
- More lenient than industry standard (acceptable for private beta/controlled launch)

**Alternative Considered:**
- **Endpoint-specific limits only** (no global limit)
  - Rejected: Still want global protection against runaway clients/bots
  - Would require careful analysis of each endpoint's expected usage

**Future Considerations:**
- Monitor actual usage patterns in production
- Consider Redis-based distributed rate limiting for horizontal scaling
- May need to exempt certain endpoints (health checks, metrics) from global limits
- Consider user-tier based limits (free vs paid users)

**Deployment:**
- Revision: `gcregisterapi-10-26-00021-rc5`
- Zero downtime deployment via Cloud Run progressive rollout
- No database changes required

**Status**: ✅ IMPLEMENTED & DEPLOYED

---

### 2025-11-09 Session 96: Production Deployment Strategy - Zero Downtime Release

**Decision:** Deploy verification architecture to production using zero-downtime Cloud Run deployment with progressive rollout strategy.

**Context:**
- Full email verification architecture ready for production
- 87 tasks completed across 15 phases
- Need to deploy without disrupting existing users
- Migration 002 already applied to production database

**Implementation Approach:**

1. **Pre-Deployment Verification:**
   - ✅ Confirmed migration 002 already applied (7 new columns in production)
   - ✅ Verified all required secrets exist in Secret Manager
   - ✅ Backend code review complete
   - ✅ Frontend build tested successfully

2. **Backend Deployment (Cloud Run):**
   - **Service**: `gcregisterapi-10-26`
   - **Strategy**: Progressive rollout with traffic migration
   - **Build**: Docker image via Cloud Build (`gcloud builds submit`)
   - **Configuration**:
     - Service account: `291176869049-compute@developer.gserviceaccount.com`
     - Secrets: 10 total (JWT, database, email, CORS)
     - Cloud SQL: `telepay-459221:us-central1:telepaypsql`
     - Memory: 512Mi, CPU: 1, Max instances: 10
   - **Result**: New revision `gcregisterapi-10-26-00017-xwp` serving 100% traffic
   - **Downtime**: 0 seconds

3. **Frontend Deployment (Cloud Storage):**
   - **Target**: `gs://www-paygateprime-com/`
   - **Build**: Vite production build (380 modules, 5.05s)
   - **Strategy**: Atomic replacement with cache headers
   - **Cache Policy**:
     - `index.html`: `Cache-Control: no-cache` (always fetch latest)
     - `assets/*`: `Cache-Control: public, max-age=31536000` (1 year)
   - **Deployment**: `gsutil -m rsync -r -d` (atomic update)
   - **Result**: New build live instantly, old assets deleted

4. **Production Verification Tests:**
   - ✅ Health check: API returns healthy status
   - ✅ Signup auto-login: Returns access_token + refresh_token
   - ✅ Email verified field: Included in all auth responses
   - ✅ Verification endpoints: `/verification/status` and `/verification/resend` working
   - ✅ Account endpoints: All 4 account management endpoints deployed
   - ✅ Frontend routes: All new pages accessible

**Deployment Decisions:**

✅ **Decision 1: Secrets via Secret Manager**
- **Rationale**: All sensitive config in Secret Manager (not env vars)
- **Implementation**: `--update-secrets` flag with Secret Manager references
- **Benefit**: Automatic secret rotation, audit logging, secure storage

✅ **Decision 2: Cache Strategy**
- **Rationale**: Balance performance vs. instant updates
- **Implementation**:
  - HTML: No cache (immediate updates)
  - Assets: 1-year cache (hash-based filenames)
- **Benefit**: Fast loading + instant deployments

✅ **Decision 3: Zero-Downtime Deployment**
- **Rationale**: Existing users should not experience any interruption
- **Implementation**:
  - Cloud Run progressive rollout (automatic)
  - Frontend atomic replacement (gsutil rsync)
- **Benefit**: Seamless user experience

✅ **Decision 4: Migration Already Applied**
- **Rationale**: Migration 002 was already run in previous session
- **Verification**: Used `check_migration.py` to confirm 7 columns exist
- **Decision**: Skip migration step, proceed directly to deployment
- **Benefit**: Faster deployment, no database downtime

✅ **Decision 5: Production Testing Post-Deployment**
- **Rationale**: Verify all features work in production environment
- **Implementation**: Created `test_production_flow.sh` script
- **Tests Performed**:
  - Website accessibility (200 OK)
  - API health check
  - Signup with auto-login
  - Verification status endpoint
  - All new endpoints accessible
- **Result**: All tests passed ✅

**Rollback Plan (Not Needed):**
- Backend: Roll back to previous Cloud Run revision
- Frontend: Restore previous Cloud Storage files from backup
- Database: No rollback needed (migration already applied)

**Monitoring Strategy:**
- Cloud Logging: Monitor error rates via `gcloud run services logs`
- Health checks: API `/health` endpoint monitoring
- User feedback: Monitor support channels for issues
- Email delivery: Monitor SendGrid dashboard

**Results:**
- ✅ Zero downtime achieved
- ✅ All features working in production
- ✅ No user-reported issues
- ✅ Clean deployment logs
- ✅ All tests passing

**Impact:**
- Users can now sign up and get immediate access (auto-login)
- Unverified users can use the full application
- Visual verification indicator in header
- Complete account management for verified users
- Rate-limited email sending prevents abuse
- Dual-factor email change for security

---

### 2025-11-09 Session 95: Email Verification Architecture - Complete Implementation Strategy

**Decision:** Implement "soft verification" model with auto-login, allowing unverified users full app access while requiring verification only for sensitive account management operations.

**Context:**
- Traditional email verification blocks users from using the app until they verify their email
- Modern UX best practice is to reduce friction and allow immediate access
- Need balance between security and user experience
- Email changes and password changes are high-risk operations requiring verification
- Rate limiting needed to prevent abuse of verification emails

**Implementation Strategy:**

1. **Auto-Login on Signup - Remove Verification Barrier:**
   - **Decision**: Return JWT tokens immediately on signup (no verification required)
   - **Modified Endpoints**: `/auth/signup` now returns `access_token` and `refresh_token`
   - **User Flow**: Signup → Auto-login → Dashboard (unverified state)
   - **Rationale**: Reduces friction, improves conversion, matches modern SaaS patterns
   - **Security**: Email still sent for verification, required for account management

2. **Unverified User Access - "Soft Verification" Model:**
   - **Decision**: Allow unverified users to login and access dashboard
   - **Modified Service**: `AuthService.authenticate_user()` removed email verification check
   - **Modified Endpoint**: `/auth/login` now accepts unverified users
   - **User Access**: Unverified users can view all content, use app features
   - **Restrictions**: Cannot change email or password until verified
   - **Rationale**: Balance between security and UX, reduces support burden

3. **Verification Rate Limiting - Prevent Email Bombing:**
   - **Decision**: 1 verification resend per 5 minutes per user
   - **Implementation**: Database tracking (last_verification_resent_at, verification_resend_count)
   - **Response**: 429 Too Many Requests with retry_after timestamp
   - **Rationale**: Prevents abuse while allowing legitimate resends

4. **Email Change Security - Dual-Factor Email Verification:**
   - **Decision**: Send notification to OLD email + confirmation to NEW email
   - **Workflow**:
     - User requests change → password required → notification to old → confirmation to new
     - User clicks link in new email → race condition check → atomic update
   - **Token Expiration**: 1 hour (shorter than verification due to sensitivity)
   - **Password Confirmation**: Required for all email changes
   - **Pending Email**: Stored in database, protected by UNIQUE constraint
   - **Rationale**: Prevents account takeover, user informed of unauthorized attempts

5. **Password Change Security - Verification Requirement:**
   - **Decision**: Require email verification before allowing password changes
   - **Checks**: Email verified + current password correct + new password different + strength validation
   - **No Re-login**: User stays logged in after password change
   - **Confirmation Email**: Sent to user's email address
   - **Rationale**: Verified email ensures user has access to account recovery

6. **Database Schema - Pending Email Tracking:**
   - **New Columns**: pending_email, pending_email_token, pending_email_token_expires, pending_email_old_notification_sent
   - **New Columns**: last_verification_resent_at, verification_resend_count, last_email_change_requested_at
   - **Indexes**: idx_pending_email (UNIQUE), idx_verification_token_expires, idx_pending_email_token_expires
   - **Constraints**: CHECK(pending_email != email), UNIQUE(pending_email)
   - **Rationale**: Supports email change flow, prevents conflicts, enables cleanup queries

7. **Token Security - Separate Token Types:**
   - **Email Verification**: 24-hour expiration (long window for user convenience)
   - **Email Change**: 1-hour expiration (shorter for security)
   - **Password Reset**: 1-hour expiration (high security requirement)
   - **TokenService**: Separate methods for each token type with unique salts
   - **Rationale**: Prevents token re-use across different operations

8. **Modular Service Architecture - Separation of Concerns:**
   - **Decision**: Create separate `account.py` routes file for account management
   - **AuthService**: Focused on authentication (signup, login, password hashing)
   - **Account Endpoints**: Separate blueprint (`/api/auth/account/`)
   - **Email Service**: Extended with email change templates
   - **Token Service**: Extended with email change token methods
   - **Rationale**: Keeps files under 800 lines, clear separation of concerns, maintainability

9. **Frontend Services Layer - TypeScript Integration:**
   - **Decision**: Extend authService.ts with 6 new methods
   - **New Methods**: getCurrentUser(), getVerificationStatus(), resendVerification(), requestEmailChange(), cancelEmailChange(), changePassword()
   - **TypeScript Interfaces**: Created dedicated types file (auth.ts)
   - **Error Handling**: Axios interceptors handle token auto-attachment
   - **Rationale**: Type safety, consistent API client patterns, reusable service methods

10. **Frontend Component Strategy - Page-Level Components:**
    - **Decision**: Create separate pages for each user flow
    - **VerificationStatusPage**: Shows status, resend button, rate limit info, restrictions
    - **AccountManagePage**: Two sections (email change, password change), verification check on load
    - **EmailChangeConfirmPage**: Handles token confirmation with loading/success/error states
    - **Header Component**: Reusable across all pages, shows verification status
    - **Rationale**: Clear user journeys, easy to test, matches REST endpoint structure

11. **Rate Limiting Strategy - Endpoint-Specific Limits:**
    - **Verification Resend**: 1 per 5 minutes (prevents email bombing)
    - **Email Change**: 3 per hour (prevents rapid account changes)
    - **Password Change**: 5 per 15 minutes (prevents brute force)
    - **Signup**: 5 per 15 minutes (prevents bot accounts)
    - **Login**: 10 per 15 minutes (prevents brute force)
    - **Implementation**: Database-level tracking + Redis in production
    - **Rationale**: Tailored to each operation's risk profile

12. **Audit Logging - Comprehensive Security Tracking:**
    - **New Methods**: log_email_change_requested, log_email_changed, log_email_change_cancelled, log_password_changed
    - **Logged Data**: user_id, email, timestamp, IP address, reason (for failures)
    - **User Enumeration Protection**: Generic error messages externally, detailed logs internally
    - **Rationale**: Security monitoring, compliance, debugging, user support

**Impact:**
- ✅ Better user experience (no verification barrier)
- ✅ Improved security for account management operations
- ✅ Comprehensive audit trail
- ✅ Modular, maintainable codebase
- ✅ Type-safe frontend integration
- ✅ Clear separation of concerns

**Trade-offs:**
- ⚠️ Unverified users can use app (acceptable for non-sensitive features)
- ⚠️ More complex dual-email flow for email changes (better security)
- ⚠️ Additional database columns and indexes (necessary for features)

---

### 2025-11-09 Session 94 (Continued): Frontend Components - Visual Verification UX & Component Structure

**Decision:** Implement verification status with clear visual indicators (yellow/green) and separate page components for each user flow

**Context:**
- Users need clear visual feedback about their verification status
- Unverified users can use the app but need to know what features are restricted
- Email change and password change are sensitive operations requiring separate UX
- Email confirmation from link requires smooth landing page experience
- Need consistent header across all authenticated pages

**Implementation:**

1. **Header Component Decision - Reusable & Always Visible:**
   - Created standalone `Header.tsx` component (not integrated into pages)
   - Props-based design: accepts `user` object with `username` and `email_verified`
   - **Visual States:**
     - **Unverified**: Yellow button (#fbbf24) - "Please Verify E-Mail" (calls attention)
     - **Verified**: Green button (#22c55e) - "✓ Verified" (positive confirmation)
   - Click handler navigates to `/verification` page
   - Logo click returns to `/dashboard`
   - Logout button uses authService.logout()
   - **Rationale**: Persistent visual reminder without blocking user, matches "soft verification" architecture

2. **VerificationStatusPage Component - Dual State Design:**
   - **Verified State**: Green checkmark, congratulatory message, "Back to Dashboard" button
   - **Unverified State**: Yellow warning, resend button, restrictions notice box
   - Resend button disabled when rate limited (5-minute cooldown)
   - Rate limiting countdown shown in UI
   - Alert messages for success/error feedback
   - **Rationale**: Clear distinction between states, actionable UI for unverified users

3. **AccountManagePage Component - Verified Users Only:**
   - Auto-redirects to `/verification` if user is unverified
   - Two separate form sections (email change, password change)
   - Independent state management for each form
   - Client-side validation (passwords must match)
   - Clear success/error messages per section
   - Forms clear on success
   - **Rationale**: Enforce verification requirement, prevent confusion with separate forms

4. **EmailChangeConfirmPage Component - Token-Based Landing Page:**
   - Reads token from URL query parameter (`?token=...`)
   - Auto-executes confirmation on mount (no user interaction needed)
   - Three visual states: Loading (spinner), Success (green checkmark + countdown), Error (red X)
   - Auto-redirect countdown (3 seconds) with manual override button
   - **Rationale**: Smooth email link experience, clear feedback, automatic flow completion

5. **Routing Architecture:**
   - Public routes: `/confirm-email-change` (token-based)
   - Protected routes: `/verification`, `/account/manage`
   - ProtectedRoute wrapper enforces authentication
   - **Rationale**: Security enforcement at route level, clear separation of public/private flows

**Alternatives Considered:**
- **Alternative 1**: Integrate header directly into each page component
  - **Rejected**: Would require duplicate code, harder to maintain consistency
- **Alternative 2**: Modal dialogs for email/password change instead of separate page
  - **Rejected**: Forms are complex, separate page provides better UX and focus
- **Alternative 3**: Redirect/green verification indicator
  - **Rejected**: Yellow (warning) is more attention-grabbing for unverified state

**Benefits:**
- Clear visual feedback across entire app (yellow = action needed, green = verified)
- Reusable Header component reduces code duplication
- Separate pages provide focused UX for each flow
- Auto-redirect with countdown improves conversion (email confirmation)
- Protected routes enforce business logic (account management requires verification)
- Loading states prevent user confusion during async operations

**Trade-offs:**
- More page components = larger bundle size (minimal impact with code splitting)
- Auto-redirect countdown may feel rushed (3 seconds is standard, can be adjusted)

**File:** `GCRegisterWeb-10-26/src/components/Header.tsx`, `src/pages/VerificationStatusPage.tsx`, `src/pages/AccountManagePage.tsx`, `src/pages/EmailChangeConfirmPage.tsx`, `src/App.tsx`

---

### 2025-11-09 Session 94: Frontend Services - Type Safety & Auto-Login Decision

**Decision:** Implement comprehensive TypeScript interfaces for all verification and account management flows

**Context:**
- Frontend needs to call new backend verification and account management endpoints
- TypeScript provides compile-time type safety for API calls
- Backend responses include complex nested structures (VerificationStatus, EmailChangeResponse, etc.)
- Auto-login behavior requires signup to return tokens (breaking change from previous behavior)

**Implementation:**

1. **TypeScript Interfaces Added:**
   - Updated `User` interface to include `email_verified`, `created_at`, `last_login`
   - Updated `AuthResponse` to include `email_verified` field
   - Added `VerificationStatus` (6 fields: email_verified, email, token_expires, can_resend, last_resent_at, resend_count)
   - Added `EmailChangeRequest` (new_email, password)
   - Added `EmailChangeResponse` (success, message, pending_email, notifications status)
   - Added `PasswordChangeRequest` (current_password, new_password, confirm_password)
   - Added `PasswordChangeResponse` (success, message)

2. **AuthService Methods Added:**
   - `getCurrentUser()` - Fetches user with email_verified status
   - `getVerificationStatus()` - Fetches detailed verification info
   - `resendVerification()` - Authenticated resend (no email parameter needed)
   - `requestEmailChange(newEmail, password)` - Initiates email change
   - `cancelEmailChange()` - Cancels pending change
   - `changePassword(current, new)` - Changes password

3. **Auto-Login Behavior:**
   - **Modified:** `signup()` now stores access_token and refresh_token
   - **Rationale:** Matches backend's new auto-login flow (signup returns tokens)
   - **Impact:** Users auto-logged in after signup, can use app immediately

**Rationale:**

1. **Type Safety:**
   - Catches API contract mismatches at compile time
   - IntelliSense provides autocomplete for API responses
   - Prevents runtime errors from incorrect field access

2. **Developer Experience:**
   - Clear contract between frontend and backend
   - Self-documenting code (interfaces show what data looks like)
   - Easier refactoring (TypeScript shows all usages)

3. **Maintainability:**
   - Centralized type definitions in `src/types/auth.ts`
   - Easy to update when backend changes
   - Consistent typing across all components

4. **Auto-Login Decision:**
   - **Problem:** Old flow required email verification before login (high friction)
   - **Solution:** Signup returns tokens immediately, verification optional for account changes
   - **Security:** Unverified users can use app, but can't change email/password
   - **UX:** Zero-friction onboarding, clear verification prompts in UI

**Alternatives Considered:**

**Option 1: Use `any` types (rejected)**
- Pros: Faster initial implementation
- Cons: No type safety, runtime errors, poor developer experience

**Option 2: Inline types in service methods (rejected)**
- Pros: Types close to usage
- Cons: Duplication, inconsistency, harder to maintain

**Option 3: Centralized interfaces in types file (CHOSEN)**
- Pros: Single source of truth, reusable, maintainable
- Cons: Extra file to manage (minimal overhead)

**Impact:**
- ✅ All frontend API calls are now type-safe
- ✅ Signup flow auto-logs user in (matches backend)
- ✅ Ready for Phase 9 UI components
- ✅ No breaking changes for existing login flow
- ✅ Clear separation between authenticated and public endpoints

**Pattern:** Type-safe API client with centralized interface definitions

---

### 2025-11-09 Session 93: Verification Endpoints - Modular Design Decision

**Decision:** Add verification endpoints to existing `auth.py` instead of creating separate `verification.py` file

**Context:**
- VERIFICATION_ARCHITECTURE_1_CHECKLIST.md recommends creating separate file if auth.py exceeds 800 lines
- Current auth.py is 568 lines (well under threshold)
- Need to add 2 new verification endpoints: `/verification/status` and `/verification/resend`
- Must maintain clean code organization while avoiding premature optimization

**Options Considered:**

**Option 1: Create Separate verification.py File**
- Pros: Maximum modularity, clear separation of concerns, easier testing
- Cons: Overhead for small codebase, multiple files to navigate, may be premature
- Pattern: Microservices-style separation

**Option 2: Add to Existing auth.py with Clear Section Markers (CHOSEN)**
- Pros: All auth-related routes in one place, simpler navigation, no premature splitting
- Cons: File will grow (but still manageable at ~745 lines after additions)
- Pattern: Monolithic but organized

**Rationale:**
1. **File Size:** 568 + ~180 lines = ~748 lines (still under 800-line threshold)
2. **Cohesion:** Verification is closely related to authentication (same security context)
3. **Simplicity:** Easier for developers to find all auth-related endpoints
4. **Section Markers:** Used clear `# ===== VERIFICATION ENDPOINTS (Phase 5) =====` separator
5. **Future-Proofing:** Can split later if auth.py approaches 1000 lines

**Implementation Details:**
- Added clear section marker comment for verification endpoints
- Placed verification endpoints after existing auth endpoints
- Maintained consistent error handling and audit logging patterns
- Both endpoints require JWT authentication (same security model as other auth endpoints)

**Future Considerations:**
- If auth.py exceeds 900 lines, consider splitting:
  - `auth.py`: signup, login, logout, refresh, /me
  - `verification.py`: /verification/*, /verify-email
  - `account.py`: /account/* (email change, password change)

---

### 2025-11-09 Session 93: Rate Limiting Implementation - Database-Level Tracking

**Decision:** Implement rate limiting using database timestamps and counts instead of Redis/Memcached

**Context:**
- Need to enforce 5-minute rate limit on verification email resends
- Could use external cache (Redis) or database tracking
- System already has PostgreSQL with all user data

**Options Considered:**

**Option 1: Redis/Memcached for Rate Limiting**
- Pros: Fast, designed for this use case, atomic operations
- Cons: Additional infrastructure, data inconsistency risk, overengineering for current scale
- Pattern: High-scale distributed systems

**Option 2: Database-Level Tracking (CHOSEN)**
- Pros: Single source of truth, persistent tracking, simpler architecture, no new dependencies
- Cons: Slightly slower (negligible for current scale), DB load increase
- Pattern: Monolithic applications, startups

**Rationale:**
1. **Simplicity:** No additional infrastructure needed
2. **Data Consistency:** All rate limiting data lives with user data
3. **Auditability:** Can query resend history directly from database
4. **Scale:** Current user base doesn't justify Redis complexity
5. **Performance:** PostgreSQL is more than fast enough for this use case

**Implementation:**
- Added `last_verification_resent_at` TIMESTAMP column
- Added `verification_resend_count` INTEGER column
- Rate limiting check: `time_since_resend.total_seconds() > 300` (5 minutes)
- Increment count on each resend: `verification_resend_count = COALESCE(verification_resend_count, 0) + 1`

**Monitoring:**
- Track resend_count to identify users who repeatedly request verification
- Can analyze last_verification_resent_at patterns to detect abuse

---

### 2025-11-09 Session 92: Email Verification Architecture - Auto-Login Pattern

**Decision:** Implement "soft verification" with auto-login after signup instead of mandatory pre-login email verification

**Context:**
- Current system blocks login until email is verified (403 Forbidden)
- Users report frustration at not being able to access the dashboard immediately
- High signup abandonment rate due to verification friction
- Modern UX best practice favors immediate access with optional verification
- Based on OWASP guidelines and industry standards (GitHub, Twitter, LinkedIn pattern)

**Options Considered:**

**Option 1: Keep Mandatory Pre-Login Verification (Current)**
- Pros: Maximum email validity assurance, prevents fake accounts
- Cons: High friction, poor UX, signup abandonment, frustrated users
- Pattern: Traditional (outdated for most SaaS)

**Option 2: Auto-Login with Soft Verification (CHOSEN)**
- Pros: Zero friction onboarding, immediate value delivery, higher conversion, modern UX
- Cons: Some unverified accounts may exist, requires feature gating
- Pattern: Modern SaaS (GitHub, LinkedIn, most web apps)

**Option 3: Optional Verification (No Requirements)**
- Pros: Lowest friction possible
- Cons: No way to enforce email validity, security concerns for account recovery
