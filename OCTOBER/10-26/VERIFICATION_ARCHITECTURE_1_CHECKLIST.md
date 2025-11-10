# Implementation Checklist: Email Verification & Account Management

**Based on:** VERIFICATION_ARCHITECTURE_1.md
**Date:** 2025-11-09
**Status:** Ready for Implementation

---

## 📋 Checklist Overview

This checklist breaks down the implementation into modular, file-specific tasks to ensure:
- Clean code organization
- No single file becomes too large
- Proper separation of concerns
- Testable components
- Maintainable codebase

**Total Tasks:** 87
**Estimated Duration:** 14 days

---

## ✅ Task Status Legend

- [ ] Not Started
- [🔄] In Progress
- [✅] Completed
- [🧪] Needs Testing
- [📝] Needs Review

---

## Phase 1: Database Schema Changes (Day 1)

### 1.1 Database Migration File

**File:** `GCRegisterAPI-10-26/database/migrations/002_add_email_change_support.sql`

- [ ] Create new migration file
- [ ] Add columns for pending email changes (`pending_email`, `pending_email_token`, `pending_email_token_expires`, `pending_email_old_notification_sent`)
- [ ] Add columns for verification rate limiting (`last_verification_resent_at`, `verification_resend_count`)
- [ ] Add column for email change tracking (`last_email_change_requested_at`)
- [ ] Create index on `pending_email` for faster lookups
- [ ] Create index on `verification_token_expires` for cleanup
- [ ] Create index on `pending_email_token_expires` for cleanup
- [ ] Add constraint: `CHECK (pending_email IS NULL OR pending_email != email)`
- [ ] Create unique index on `pending_email` (partial index)
- [ ] Add comprehensive comments explaining each change
- [ ] Include rollback script at bottom of migration

**Acceptance Criteria:**
- Migration runs without errors on test database
- All indexes created successfully
- Constraints enforced correctly
- Rollback script tested and works

### 1.2 Database Migration Execution

**File:** `GCRegisterAPI-10-26/database/execute_migration.py` (create if doesn't exist)

- [ ] Create migration execution script
- [ ] Add dry-run mode to preview changes
- [ ] Add database backup before migration
- [ ] Execute migration on development database
- [ ] Verify all columns added with `\d registered_users`
- [ ] Verify all indexes created
- [ ] Test constraint enforcement (try inserting invalid data)
- [ ] Document migration in migration log

**Acceptance Criteria:**
- Migration executes successfully
- Schema matches design specifications
- All constraints and indexes working

---

## Phase 2: Backend Services Layer (Days 2-3)

### 2.1 Token Service - Email Change Methods

**File:** `GCRegisterAPI-10-26/api/services/token_service.py`

- [ ] Add method `generate_email_change_token(user_id: str, new_email: str) -> str`
- [ ] Add method `verify_email_change_token(token: str) -> dict`
- [ ] Add expiration time constant for email change tokens (1 hour)
- [ ] Update `get_expiration_datetime()` to handle 'email_change' type
- [ ] Add comprehensive docstrings
- [ ] Add error handling for invalid tokens

**Acceptance Criteria:**
- Tokens generated with correct payload (user_id, new_email)
- Tokens expire after 1 hour
- Token verification returns correct data
- Invalid tokens raise appropriate exceptions

### 2.2 Auth Service - Verification Methods

**File:** `GCRegisterAPI-10-26/api/services/auth_service.py`

#### 2.2.1 Modify Existing Methods

- [ ] **`create_user()`**: Ensure it returns `verification_token` for email sending
- [ ] **`authenticate_user()`**: Remove email verification check (allow unverified logins)
- [ ] **`authenticate_user()`**: Add `email_verified` to return dict
- [ ] Update docstrings to reflect new behavior

#### 2.2.2 Add New Methods

- [ ] Add method `get_verification_status(conn, user_id: str) -> dict`
  - Returns: email_verified, email, token_expires, last_resent_at, resend_count, can_resend
  - Calculate `can_resend` based on 5-minute rate limit

- [ ] Add method `resend_verification_email_for_user(conn, user_id: str) -> dict`
  - Check rate limiting (5 minutes since last resend)
  - Generate new verification token
  - Update database with new token and resend tracking
  - Return user data with new token

**Acceptance Criteria:**
- All methods have proper error handling
- Rate limiting correctly enforced
- Database updates are atomic
- Methods return consistent data structures

### 2.3 Auth Service - Email Change Methods

**File:** `GCRegisterAPI-10-26/api/services/auth_service.py`

- [ ] Add method `request_email_change(conn, user_id: str, new_email: str, password: str) -> dict`
  - Verify user exists and email is verified
  - Verify password is correct
  - Check new email is different from current
  - Check new email not in use (including pending_email)
  - Generate email change token
  - Store pending email and token in database
  - Return success with pending email info

- [ ] Add method `confirm_email_change(conn, token: str) -> dict`
  - Verify token signature and expiration
  - Check token matches database
  - Check new email still available (race condition check)
  - Update email, clear pending fields
  - Return success with new email

- [ ] Add method `cancel_email_change(conn, user_id: str) -> dict`
  - Clear pending_email fields for user
  - Return success message

**Acceptance Criteria:**
- All security checks implemented
- Race conditions handled
- Atomic database transactions
- Clear error messages

### 2.4 Auth Service - Password Change Method

**File:** `GCRegisterAPI-10-26/api/services/auth_service.py`

- [ ] Add method `change_password(conn, user_id: str, current_password: str, new_password: str) -> dict`
  - Verify user exists and email is verified
  - Verify current password
  - Verify new password is different
  - Hash new password
  - Update database
  - Return success

**Acceptance Criteria:**
- Email verification check enforced
- Password validation works
- Bcrypt hashing applied correctly
- Clear error messages

### 2.5 Email Service - New Email Templates

**File:** `GCRegisterAPI-10-26/api/services/email_service.py`

#### 2.5.1 Add Email Template Methods

- [ ] Add method `send_email_change_notification(to_email: str, username: str, new_email: str) -> bool`
  - Template: Notification to OLD email
  - Include new email address
  - Include cancel link

- [ ] Add method `send_email_change_confirmation(to_email: str, username: str, token: str) -> bool`
  - Template: Confirmation link to NEW email
  - Include confirmation URL with token
  - 1-hour expiration notice

- [ ] Add method `send_email_changed_confirmation(to_email: str, username: str) -> bool`
  - Template: Success confirmation to NEW email
  - Notify change is complete

- [ ] Add method `send_password_changed_confirmation(to_email: str, username: str) -> bool`
  - Template: Password change confirmation
  - Security alert notice

#### 2.5.2 Update Existing Methods (if needed)

- [ ] Review `send_verification_email()` - ensure it works with new flow
- [ ] Add rate limiting checks to prevent email bombing

**Acceptance Criteria:**
- All email templates are clear and professional
- Links correctly formatted with environment-specific URLs
- HTML and plain text versions available
- Error handling for failed sends

### 2.6 Verification Service (NEW)

**File:** `GCRegisterAPI-10-26/api/services/verification_service.py` (CREATE NEW)

**Purpose:** Separate verification logic from AuthService for better modularity

- [ ] Create new file `verification_service.py`
- [ ] Add class `VerificationService`
- [ ] Add method `get_status(conn, user_id: str) -> dict`
- [ ] Add method `can_resend(last_resent_at: datetime) -> bool`
- [ ] Add method `resend_verification(conn, user_id: str) -> dict`
- [ ] Move verification-specific logic from AuthService to this service

**Acceptance Criteria:**
- Clean separation from AuthService
- All methods properly documented
- Comprehensive error handling

### 2.7 Account Service (NEW)

**File:** `GCRegisterAPI-10-26/api/services/account_service.py` (CREATE NEW)

**Purpose:** Handle account management operations separately

- [ ] Create new file `account_service.py`
- [ ] Add class `AccountService`
- [ ] Add method `request_email_change(conn, user_id: str, new_email: str, password: str) -> dict`
- [ ] Add method `confirm_email_change(conn, token: str) -> dict`
- [ ] Add method `cancel_email_change(conn, user_id: str) -> dict`
- [ ] Add method `change_password(conn, user_id: str, current_password: str, new_password: str) -> dict`

**Acceptance Criteria:**
- Modular, focused service
- All security checks implemented
- Proper error handling

---

## Phase 3: Backend Models (Day 3)

### 3.1 Pydantic Models - New Request/Response Models

**File:** `GCRegisterAPI-10-26/api/models/auth.py`

- [ ] Add model `VerificationStatusResponse`
  - Fields: email_verified, email, verification_token_expires, can_resend, last_resent_at, resend_count

- [ ] Add model `EmailChangeRequest`
  - Fields: new_email (EmailStr), password (str)
  - Validators: email format

- [ ] Add model `EmailChangeResponse`
  - Fields: success, message, pending_email, notification_sent_to_old, confirmation_sent_to_new

- [ ] Add model `PasswordChangeRequest`
  - Fields: current_password, new_password
  - Validators: new password strength (reuse from SignupRequest)

- [ ] Add model `PasswordChangeResponse`
  - Fields: success, message

- [ ] Update `SignupResponse` model if needed (should now include tokens)

**Acceptance Criteria:**
- All models validate correctly
- Validators enforce business rules
- Models match API specifications

---

## Phase 4: Backend Routes - Modifications (Days 4-5)

### 4.1 Modify Signup Route

**File:** `GCRegisterAPI-10-26/api/routes/auth.py`

- [ ] Update `/signup` endpoint to create tokens after user creation
- [ ] Add token creation: `tokens = AuthService.create_tokens(user['user_id'], user['username'])`
- [ ] Include tokens in response: `**tokens`
- [ ] Update response to include `email_verified: False`
- [ ] Update audit logging to note auto-login
- [ ] Update docstring to reflect new behavior
- [ ] Update success message

**Acceptance Criteria:**
- Signup returns access_token and refresh_token
- User can login immediately after signup
- Email verification still sent
- Audit logs updated

### 4.2 Modify Login Route

**File:** `GCRegisterAPI-10-26/api/routes/auth.py`

- [ ] Verify that login works for unverified users (should already work after AuthService changes)
- [ ] Ensure `email_verified` status included in response
- [ ] Update error handling to remove email verification error case
- [ ] Update docstring
- [ ] Test with both verified and unverified users

**Acceptance Criteria:**
- Unverified users can login successfully
- Response includes email_verified status
- No 403 error for unverified emails

### 4.3 Modify /me Route

**File:** `GCRegisterAPI-10-26/api/routes/auth.py`

- [ ] Update SQL query to include `email_verified` column
- [ ] Add `email_verified` to response dict
- [ ] Update docstring

**Acceptance Criteria:**
- Response includes email_verified field
- Field accurately reflects database state

---

## Phase 5: Backend Routes - New Verification Endpoints (Day 5)

### 5.1 Create Verification Routes File (Optional - for modularity)

**File:** `GCRegisterAPI-10-26/api/routes/verification.py` (CREATE NEW - OPTIONAL)

**Alternative:** Add to existing `api/routes/auth.py` in a clearly marked section

**Decision Point:** If auth.py is getting too large (>800 lines), create separate file

- [ ] Decide: Separate file or section in auth.py?
- [ ] If separate: Create `verification.py` blueprint
- [ ] If separate: Register blueprint in `app.py`

### 5.2 Add /verification/status Endpoint

**Location:** `api/routes/auth.py` or `api/routes/verification.py`

- [ ] Create route `@auth_bp.route('/verification/status', methods=['GET'])`
- [ ] Add `@jwt_required()` decorator
- [ ] Get user_id from JWT: `user_id = get_jwt_identity()`
- [ ] Call `VerificationService.get_status(conn, user_id)` or query database directly
- [ ] Calculate `can_resend` based on rate limiting (5 minutes)
- [ ] Return verification status
- [ ] Add error handling
- [ ] Add docstring

**Acceptance Criteria:**
- Returns accurate verification status
- Rate limiting calculation correct
- Requires authentication

### 5.3 Add /verification/resend Endpoint

**Location:** `api/routes/auth.py` or `api/routes/verification.py`

- [ ] Create route `@auth_bp.route('/verification/resend', methods=['POST'])`
- [ ] Add `@jwt_required()` decorator
- [ ] Get user_id from JWT
- [ ] Check if already verified (return 400 if true)
- [ ] Check rate limiting (5 minutes)
- [ ] If rate limited, return 429 with retry_after
- [ ] Generate new verification token
- [ ] Update database with new token and resend tracking
- [ ] Send verification email
- [ ] Return success with can_resend_at timestamp
- [ ] Add audit logging
- [ ] Add error handling

**Acceptance Criteria:**
- Rate limiting enforced (1 per 5 minutes)
- New token generated and sent
- Database tracking updated
- Proper HTTP status codes

### 5.4 Modify /verify-email Endpoint (if needed)

**File:** `GCRegisterAPI-10-26/api/routes/auth.py`

- [ ] Review existing implementation
- [ ] Ensure it works with new flow (should be unchanged)
- [ ] Update redirect URL if needed
- [ ] Update success message

**Acceptance Criteria:**
- Email verification still works
- User marked as verified in database

---

## Phase 6: Backend Routes - New Account Management Endpoints (Days 6-7)

### 6.1 Create Account Routes File

**File:** `GCRegisterAPI-10-26/api/routes/account.py` (CREATE NEW)

**Purpose:** Separate account management from authentication routes

- [ ] Create new file `account.py`
- [ ] Create Blueprint: `account_bp = Blueprint('account', __name__)`
- [ ] Import required services (AccountService, EmailService, AuditLogger)
- [ ] Add rate limiter setup

**Acceptance Criteria:**
- File created with proper structure
- Blueprint configured correctly

### 6.2 Add /account/change-email Endpoint

**File:** `GCRegisterAPI-10-26/api/routes/account.py`

- [ ] Create route `@account_bp.route('/change-email', methods=['POST'])`
- [ ] Add `@jwt_required()` decorator
- [ ] Add rate limiting (3 per hour)
- [ ] Validate request body (EmailChangeRequest model)
- [ ] Get user_id from JWT
- [ ] Get user from database
- [ ] **Security Check 1:** Verify email is already verified (403 if not)
- [ ] **Security Check 2:** Verify password is correct (401 if not)
- [ ] **Security Check 3:** Verify new email is different (400 if same)
- [ ] **Security Check 4:** Verify new email not in use (400 if taken)
- [ ] Generate email change token
- [ ] Store pending email in database
- [ ] Send notification to OLD email
- [ ] Send confirmation to NEW email
- [ ] Add audit logging
- [ ] Return success response
- [ ] Add comprehensive error handling

**Acceptance Criteria:**
- All security checks implemented
- Both emails sent successfully
- Database updated correctly
- Proper HTTP status codes for each error type

### 6.3 Add /account/confirm-email-change Endpoint

**File:** `GCRegisterAPI-10-26/api/routes/account.py`

- [ ] Create route `@account_bp.route('/confirm-email-change', methods=['GET'])`
- [ ] Get token from query parameter
- [ ] Verify token signature and expiration
- [ ] Get user from database using user_id from token
- [ ] Verify token matches database token
- [ ] Check token not expired (database check)
- [ ] Verify pending_email matches token new_email
- [ ] **Race condition check:** Verify new email still available
- [ ] Update email in database
- [ ] Clear pending_email fields
- [ ] Send confirmation email to new address
- [ ] Add audit logging
- [ ] Return success with redirect URL
- [ ] Handle token errors (expired, invalid)

**Acceptance Criteria:**
- Token verification works correctly
- Race conditions handled
- Database transaction is atomic
- User email updated successfully

### 6.4 Add /account/cancel-email-change Endpoint

**File:** `GCRegisterAPI-10-26/api/routes/account.py`

- [ ] Create route `@account_bp.route('/cancel-email-change', methods=['POST'])`
- [ ] Add `@jwt_required()` decorator
- [ ] Get user_id from JWT
- [ ] Clear pending_email fields in database
- [ ] Add audit logging
- [ ] Return success message

**Acceptance Criteria:**
- Pending email change cancelled
- Database fields cleared
- Audit log created

### 6.5 Add /account/change-password Endpoint

**File:** `GCRegisterAPI-10-26/api/routes/account.py`

- [ ] Create route `@account_bp.route('/change-password', methods=['POST'])`
- [ ] Add `@jwt_required()` decorator
- [ ] Add rate limiting (5 per 15 minutes)
- [ ] Validate request body (PasswordChangeRequest model)
- [ ] Get user_id from JWT
- [ ] Get user from database
- [ ] **Security Check 1:** Verify email is verified (403 if not)
- [ ] **Security Check 2:** Verify current password (401 if wrong)
- [ ] **Security Check 3:** Verify new password is different (400 if same)
- [ ] Validate new password strength (Pydantic validator)
- [ ] Hash new password
- [ ] Update database
- [ ] Send confirmation email
- [ ] Add audit logging
- [ ] Return success message

**Acceptance Criteria:**
- All security checks enforced
- Password properly hashed
- Confirmation email sent
- Audit log created

### 6.6 Register Account Blueprint

**File:** `GCRegisterAPI-10-26/app.py`

- [ ] Import account blueprint: `from api.routes.account import account_bp`
- [ ] Register blueprint: `app.register_blueprint(account_bp, url_prefix='/auth/account')`
- [ ] Update API documentation if maintained

**Acceptance Criteria:**
- Blueprint registered correctly
- All routes accessible under `/auth/account/` prefix

---

## Phase 7: Backend - Audit Logging (Day 7)

### 7.1 Add New Audit Log Methods

**File:** `GCRegisterAPI-10-26/api/utils/audit_logger.py`

- [ ] Add method `log_email_change_requested(user_id: str, old_email: str, new_email: str)`
- [ ] Add method `log_email_change_failed(user_id: str, reason: str)`
- [ ] Add method `log_email_changed(user_id: str, old_email: str, new_email: str)`
- [ ] Add method `log_email_change_cancelled(user_id: str, email: str)`
- [ ] Add method `log_password_changed(user_id: str, email: str)`
- [ ] Add method `log_password_change_failed(user_id: str, reason: str)`
- [ ] Add method `log_verification_resent_authenticated(user_id: str, email: str)`

**Acceptance Criteria:**
- All new events logged
- Log messages are clear and informative
- Logs include relevant context (user_id, email, reason)

---

## Phase 8: Frontend - Services Layer (Day 8)

### 8.1 Update Auth Service

**File:** `GCRegisterWeb-10-26/src/services/authService.ts`

#### 8.1.1 Modify Existing Methods

- [ ] **`signup()`**: Expect and store tokens in response
- [ ] **`signup()`**: Store access_token and refresh_token in localStorage
- [ ] **`login()`**: No changes needed (already stores tokens)

#### 8.1.2 Add New Methods

- [ ] Add method `getCurrentUser(): Promise<any>`
  - GET /auth/me
  - Returns user data with email_verified status

- [ ] Add method `getVerificationStatus(): Promise<VerificationStatus>`
  - GET /auth/verification/status
  - Returns detailed verification status

- [ ] Add method `resendVerification(): Promise<any>`
  - POST /auth/verification/resend
  - Returns success message and can_resend_at

- [ ] Add method `requestEmailChange(new_email: string, password: string): Promise<any>`
  - POST /auth/account/change-email
  - Returns success message

- [ ] Add method `cancelEmailChange(): Promise<any>`
  - POST /auth/account/cancel-email-change
  - Returns success message

- [ ] Add method `changePassword(current_password: string, new_password: string): Promise<any>`
  - POST /auth/account/change-password
  - Returns success message

**Acceptance Criteria:**
- All methods properly typed
- Error handling implemented
- Token auto-attached via interceptor
- Responses parsed correctly

### 8.2 Create TypeScript Interfaces

**File:** `GCRegisterWeb-10-26/src/types/auth.ts` (CREATE NEW)

- [ ] Create file `auth.ts`
- [ ] Add interface `User`
  - user_id, username, email, email_verified, created_at, last_login

- [ ] Add interface `VerificationStatus`
  - email_verified, email, verification_token_expires, can_resend, last_resent_at, resend_count

- [ ] Add interface `EmailChangeRequest`
  - new_email, password

- [ ] Add interface `PasswordChangeRequest`
  - current_password, new_password, confirm_password

- [ ] Export all interfaces

**Acceptance Criteria:**
- All interfaces match API responses
- TypeScript compilation passes
- Interfaces used in components

---

## Phase 9: Frontend - Components (Days 9-10)

### 9.1 Create Header Component

**File:** `GCRegisterWeb-10-26/src/components/Header.tsx` (CREATE NEW)

- [ ] Create functional component `Header`
- [ ] Add props interface: `{ user: { username: string; email_verified: boolean } }`
- [ ] Render logo/title
- [ ] Render username
- [ ] Render verification button:
  - If unverified: yellow border, text "Please Verify E-Mail"
  - If verified: green border, text "✓ Verified"
- [ ] Render logout button
- [ ] Add click handlers:
  - Verification button → navigate to `/verification`
  - Logout button → call authService.logout(), navigate to `/login`
- [ ] Add proper TypeScript types
- [ ] Import and use in Dashboard/Layout

**Acceptance Criteria:**
- Component renders correctly
- Buttons styled according to spec (yellow/green borders)
- Click handlers work
- Responsive design

### 9.2 Create Header CSS

**File:** `GCRegisterWeb-10-26/src/components/Header.css` (CREATE NEW)

- [ ] Create CSS file
- [ ] Style `.app-header` - white background, border-bottom, shadow
- [ ] Style `.header-content` - flex layout, max-width 1200px
- [ ] Style `.header-logo` - logo/title styles
- [ ] Style `.header-user` - flex layout for user section
- [ ] Style `.username` - text color, font-weight
- [ ] Style `.btn` - base button styles
- [ ] Style `.btn-verify` - yellow/gold border, background #fffbeb
- [ ] Style `.btn-verified` - green border, background #f0fdf4
- [ ] Style `.btn-logout` - neutral gray styles
- [ ] Add hover states for all buttons
- [ ] Add responsive breakpoints if needed

**Acceptance Criteria:**
- Matches design specification
- Yellow button for unverified
- Green button for verified
- Professional appearance

### 9.3 Create VerificationStatusPage Component

**File:** `GCRegisterWeb-10-26/src/pages/VerificationStatusPage.tsx` (CREATE NEW)

- [ ] Create functional component `VerificationStatusPage`
- [ ] Add state: `status`, `loading`, `resending`, `message`, `error`
- [ ] Add `useEffect` to load verification status on mount
- [ ] Create `loadStatus()` function - calls authService.getVerificationStatus()
- [ ] Create `handleResendVerification()` function
  - Check `status.can_resend`
  - Call authService.resendVerification()
  - Show success message
  - Reload status
- [ ] Create `handleManageAccount()` function - navigate to `/account/manage`
- [ ] Render loading state
- [ ] Render verified state:
  - Green checkmark icon
  - "Email Verified" title
  - Email address
  - "Manage Account Settings" button
- [ ] Render unverified state:
  - Warning icon
  - "Email Not Verified" title
  - Email address
  - Verification info (resend count, last sent)
  - "Resend Verification Email" button (disabled if can't resend)
  - Rate limit notice if applicable
  - Restriction notice (can't change email/password)
- [ ] Render "Back to Dashboard" button
- [ ] Add error handling
- [ ] Add TypeScript types

**Acceptance Criteria:**
- Both states render correctly
- Resend functionality works
- Rate limiting enforced
- Professional UI

### 9.4 Create VerificationStatusPage CSS

**File:** `GCRegisterWeb-10-26/src/pages/VerificationStatusPage.css` (CREATE NEW)

- [ ] Style `.verification-container` - full viewport, centered, gradient background
- [ ] Style `.verification-card` - white card, shadow, rounded corners
- [ ] Style `.status-icon` - circular icon containers
- [ ] Style `.status-icon.verified` - green background
- [ ] Style `.status-icon.unverified` - yellow/gold background
- [ ] Style icon SVGs
- [ ] Style `.status-title` - large, centered title
- [ ] Style `.status-title.verified` - green color
- [ ] Style `.status-title.unverified` - yellow/gold color
- [ ] Style `.status-description` - centered, gray text
- [ ] Style `.verification-info` - gray box with resend info
- [ ] Style `.rate-limit-notice` - warning text
- [ ] Style `.restriction-notice` - yellow box with restrictions list
- [ ] Style alerts (success, error)
- [ ] Style buttons
- [ ] Add responsive design

**Acceptance Criteria:**
- Matches design specification
- Professional, clean appearance
- Responsive layout

### 9.5 Create AccountManagePage Component

**File:** `GCRegisterWeb-10-26/src/pages/AccountManagePage.tsx` (CREATE NEW)

- [ ] Create functional component `AccountManagePage`
- [ ] Add state for user, loading states, form data, messages, errors
- [ ] Add `useEffect` to load current user on mount
  - If not verified, redirect to `/verification`
- [ ] Create email change form section:
  - Current email (disabled input)
  - New email input
  - Password input
  - Submit button
- [ ] Create `handleEmailChange()` function
  - Validate inputs
  - Call authService.requestEmailChange()
  - Show success message
  - Clear form
- [ ] Create password change form section:
  - Current password input
  - New password input
  - Confirm new password input
  - Submit button
- [ ] Create `handlePasswordChange()` function
  - Validate passwords match
  - Call authService.changePassword()
  - Show success message
  - Clear form
- [ ] Add "Back to Dashboard" button
- [ ] Add error handling for both forms
- [ ] Add loading states for both forms
- [ ] Add form validation
- [ ] Add TypeScript types

**Acceptance Criteria:**
- Only accessible to verified users
- Both forms work correctly
- Validation enforced
- Error messages clear
- Success feedback shown

### 9.6 Create AccountManagePage CSS

**File:** `GCRegisterWeb-10-26/src/pages/AccountManagePage.css` (CREATE NEW)

- [ ] Style `.account-container` - page container
- [ ] Style `.account-content` - max-width, padding
- [ ] Style page title
- [ ] Style `.account-section` - each form section
- [ ] Style section titles and descriptions
- [ ] Style form groups
- [ ] Style input fields
- [ ] Style labels
- [ ] Style submit buttons
- [ ] Style alerts (success, error)
- [ ] Add spacing between sections
- [ ] Add responsive design

**Acceptance Criteria:**
- Clean, professional layout
- Forms are easy to use
- Clear visual hierarchy

### 9.7 Update SignupPage Component

**File:** `GCRegisterWeb-10-26/src/pages/SignupPage.tsx`

- [ ] Review existing handleSubmit function
- [ ] Ensure it navigates to `/dashboard` after successful signup (should already do this)
- [ ] Verify tokens are stored (authService handles this)
- [ ] Add password strength hint below password field
- [ ] Update any success messages if needed

**Acceptance Criteria:**
- Signup flow works end-to-end
- User auto-logged in after signup
- Redirected to dashboard
- Password hint visible

### 9.8 Update Dashboard/Layout Component

**File:** `GCRegisterWeb-10-26/src/pages/DashboardPage.tsx` or `src/components/Layout.tsx`

- [ ] Import Header component
- [ ] Get current user data (email_verified status)
- [ ] Pass user data to Header component
- [ ] Render Header at top of dashboard/layout

**Acceptance Criteria:**
- Header displayed on all authenticated pages
- User data passed correctly
- Verification status accurate

---

## Phase 10: Frontend - Routing (Day 10)

### 10.1 Update Router Configuration

**File:** `GCRegisterWeb-10-26/src/App.tsx` or `src/router/index.tsx`

- [ ] Import new pages:
  - VerificationStatusPage
  - AccountManagePage

- [ ] Add route `/verification`
  - Component: VerificationStatusPage
  - Protected: Yes (requires auth)

- [ ] Add route `/account/manage`
  - Component: AccountManagePage
  - Protected: Yes (requires auth + verification check)

- [ ] Add route `/auth/account/confirm-email-change`
  - Component: EmailChangeConfirmPage (simple page to handle token)
  - Protected: No (uses token from email)

- [ ] Update route protection logic if needed

**Acceptance Criteria:**
- All routes accessible
- Protected routes require authentication
- Email change confirm route works from email link

### 10.2 Create EmailChangeConfirmPage (Simple)

**File:** `GCRegisterWeb-10-26/src/pages/EmailChangeConfirmPage.tsx` (CREATE NEW)

- [ ] Create functional component
- [ ] Extract token from URL query params
- [ ] Call backend `/auth/account/confirm-email-change?token={token}`
- [ ] Show loading state
- [ ] Show success state with redirect to login/dashboard
- [ ] Show error state (expired token, invalid token)
- [ ] Add countdown redirect (3 seconds)

**Acceptance Criteria:**
- Handles email link clicks
- Shows appropriate feedback
- Redirects correctly

---

## Phase 11: Backend - Email Templates (Day 11)

### 11.1 Create Email Template Directory

**Directory:** `GCRegisterAPI-10-26/api/templates/emails/` (if doesn't exist)

- [ ] Create directory structure
- [ ] Decide on template format (HTML, plain text, or both)

### 11.2 Create Email Change Notification Template

**File:** `api/templates/emails/email_change_notification.html`

- [ ] Create HTML template
- [ ] Include: username, old_email, new_email, cancel_link
- [ ] Add professional styling
- [ ] Create plain text version

**File:** `api/templates/emails/email_change_notification.txt`

- [ ] Create plain text version

### 11.3 Create Email Change Confirmation Template

**File:** `api/templates/emails/email_change_confirmation.html`

- [ ] Create HTML template
- [ ] Include: username, confirmation_link, expiration notice (1 hour)
- [ ] Add professional styling
- [ ] Create plain text version

**File:** `api/templates/emails/email_change_confirmation.txt`

- [ ] Create plain text version

### 11.4 Create Email Changed Confirmation Template

**File:** `api/templates/emails/email_changed_confirmation.html`

- [ ] Create HTML template
- [ ] Include: username, new_email, support link
- [ ] Add professional styling
- [ ] Create plain text version

**File:** `api/templates/emails/email_changed_confirmation.txt`

- [ ] Create plain text version

### 11.5 Create Password Changed Confirmation Template

**File:** `api/templates/emails/password_changed_confirmation.html`

- [ ] Create HTML template
- [ ] Include: username, timestamp, security notice, support link
- [ ] Add professional styling
- [ ] Create plain text version

**File:** `api/templates/emails/password_changed_confirmation.txt`

- [ ] Create plain text version

### 11.6 Update Email Service to Use Templates

**File:** `GCRegisterAPI-10-26/api/services/email_service.py`

- [ ] Add template loading logic (use Jinja2 or similar)
- [ ] Update all email methods to use templates
- [ ] Add error handling for missing templates

**Acceptance Criteria:**
- All templates professional and clear
- Both HTML and text versions available
- Templates render correctly with data
- Links work correctly

---

## Phase 12: Testing - Backend (Days 12-13)

### 12.1 Unit Tests - Services

**File:** `GCRegisterAPI-10-26/tests/test_auth_service.py`

- [ ] Test `create_user()` returns verification token
- [ ] Test `authenticate_user()` allows unverified users
- [ ] Test `authenticate_user()` returns email_verified status

**File:** `GCRegisterAPI-10-26/tests/test_verification_service.py` (CREATE NEW)

- [ ] Test `get_status()` returns correct data
- [ ] Test `can_resend()` rate limiting logic
- [ ] Test `resend_verification()` updates database correctly

**File:** `GCRegisterAPI-10-26/tests/test_account_service.py` (CREATE NEW)

- [ ] Test `request_email_change()` security checks:
  - Requires verified email
  - Requires correct password
  - Rejects duplicate emails
  - Stores pending email correctly
- [ ] Test `confirm_email_change()` updates email
- [ ] Test `confirm_email_change()` handles race conditions
- [ ] Test `cancel_email_change()` clears pending fields
- [ ] Test `change_password()` security checks:
  - Requires verified email
  - Requires correct current password
  - Rejects same password
  - Hashes new password

**File:** `GCRegisterAPI-10-26/tests/test_token_service.py`

- [ ] Test `generate_email_change_token()` creates valid token
- [ ] Test `verify_email_change_token()` validates correctly
- [ ] Test token expiration (1 hour)

### 12.2 Integration Tests - API Endpoints

**File:** `GCRegisterAPI-10-26/tests/test_api_auth.py`

- [ ] Test `/signup` returns tokens
- [ ] Test `/signup` creates unverified user
- [ ] Test `/login` works for unverified users
- [ ] Test `/me` includes email_verified field

**File:** `GCRegisterAPI-10-26/tests/test_api_verification.py` (CREATE NEW)

- [ ] Test `/verification/status` returns correct data
- [ ] Test `/verification/resend` rate limiting (1 per 5 min)
- [ ] Test `/verification/resend` generates new token
- [ ] Test `/verify-email` marks user as verified

**File:** `GCRegisterAPI-10-26/tests/test_api_account.py` (CREATE NEW)

- [ ] Test `/account/change-email` rejects unverified users
- [ ] Test `/account/change-email` requires password
- [ ] Test `/account/change-email` sends both emails
- [ ] Test `/account/confirm-email-change` updates email
- [ ] Test `/account/cancel-email-change` works
- [ ] Test `/account/change-password` rejects unverified users
- [ ] Test `/account/change-password` requires current password
- [ ] Test `/account/change-password` validates new password

### 12.3 End-to-End Flow Tests

**File:** `GCRegisterAPI-10-26/tests/test_flows.py` (CREATE NEW)

- [ ] Test complete signup → auto-login → dashboard flow
- [ ] Test complete verification flow:
  - Signup
  - Get verification status (unverified)
  - Resend verification
  - Verify email
  - Get verification status (verified)

- [ ] Test complete email change flow:
  - Login as verified user
  - Request email change
  - Confirm new email
  - Verify email updated

- [ ] Test complete password change flow:
  - Login as verified user
  - Change password
  - Logout
  - Login with new password

### 12.4 Security Tests

**File:** `GCRegisterAPI-10-26/tests/test_security.py` (CREATE NEW)

- [ ] Test rate limiting on all endpoints
- [ ] Test token expiration
- [ ] Test invalid token rejection
- [ ] Test SQL injection attempts
- [ ] Test XSS in email templates
- [ ] Test CSRF protection (if applicable)
- [ ] Test password complexity requirements
- [ ] Test email enumeration prevention

**Acceptance Criteria:**
- All tests pass
- Code coverage >80%
- Edge cases covered
- Security vulnerabilities addressed

---

## Phase 13: Testing - Frontend (Day 13)

### 13.1 Component Tests

**File:** `GCRegisterWeb-10-26/src/components/Header.test.tsx` (CREATE NEW)

- [ ] Test component renders correctly
- [ ] Test unverified state shows yellow button
- [ ] Test verified state shows green button
- [ ] Test logout button works
- [ ] Test verification button navigation

**File:** `GCRegisterWeb-10-26/src/pages/VerificationStatusPage.test.tsx` (CREATE NEW)

- [ ] Test unverified state renders correctly
- [ ] Test verified state renders correctly
- [ ] Test resend button works
- [ ] Test rate limiting message shown
- [ ] Test error handling

**File:** `GCRegisterWeb-10-26/src/pages/AccountManagePage.test.tsx` (CREATE NEW)

- [ ] Test redirects unverified users
- [ ] Test email change form submission
- [ ] Test password change form submission
- [ ] Test form validation
- [ ] Test error handling

### 13.2 Service Tests

**File:** `GCRegisterWeb-10-26/src/services/authService.test.ts` (CREATE NEW)

- [ ] Test signup stores tokens
- [ ] Test getCurrentUser() fetches user data
- [ ] Test getVerificationStatus() fetches status
- [ ] Test resendVerification() calls correct endpoint
- [ ] Test requestEmailChange() sends correct data
- [ ] Test changePassword() sends correct data

### 13.3 Integration Tests

- [ ] Test signup → dashboard flow in browser
- [ ] Test verification flow in browser
- [ ] Test email change flow in browser
- [ ] Test password change flow in browser

**Acceptance Criteria:**
- All component tests pass
- Service tests pass
- Integration tests pass
- UI behaves correctly

---

## Phase 14: Documentation (Day 14)

### 14.1 API Documentation

**File:** `GCRegisterAPI-10-26/docs/API.md` (UPDATE or CREATE)

- [ ] Document all new endpoints:
  - `/auth/verification/status`
  - `/auth/verification/resend`
  - `/auth/account/change-email`
  - `/auth/account/confirm-email-change`
  - `/auth/account/cancel-email-change`
  - `/auth/account/change-password`

- [ ] Update modified endpoints:
  - `/auth/signup` (now returns tokens)
  - `/auth/login` (now allows unverified)
  - `/auth/me` (now includes email_verified)

- [ ] Include for each endpoint:
  - Method and path
  - Authentication requirements
  - Rate limits
  - Request body schema
  - Response schema
  - Error responses
  - Example requests/responses

### 14.2 User Guide

**File:** `OCTOBER/10-26/USER_GUIDE.md` (CREATE NEW)

- [ ] Create user-facing documentation
- [ ] Explain signup flow (auto-login)
- [ ] Explain verification process
- [ ] Explain how to resend verification
- [ ] Explain how to change email
- [ ] Explain how to change password
- [ ] Add screenshots/diagrams if possible

### 14.3 Developer Setup Guide

**File:** `GCRegisterAPI-10-26/README.md` (UPDATE)

- [ ] Update setup instructions
- [ ] Document new environment variables (if any)
- [ ] Document database migration process
- [ ] Document email template configuration

### 14.4 Update PROGRESS.md

**File:** `OCTOBER/10-26/PROGRESS.md`

- [ ] Add entry at top of file
- [ ] Document implementation of verification architecture
- [ ] List all new features added
- [ ] Note any challenges encountered

### 14.5 Update DECISIONS.md

**File:** `OCTOBER/10-26/DECISIONS.md`

- [ ] Add entry at top of file
- [ ] Document decision to allow unverified logins
- [ ] Document decision to use dual-verification for email changes
- [ ] Document rate limiting choices (5 min resend, 3 per hour email change)
- [ ] Document choice to create separate services/routes

**Acceptance Criteria:**
- All documentation complete and accurate
- API docs match implementation
- User guide is clear and helpful
- Developer setup guide works for new developers

---

## Phase 15: Deployment (Day 14)

### 15.1 Backend Deployment Preparation

- [ ] Review all environment variables
- [ ] Ensure all secrets configured in Google Cloud
- [ ] Test migration on staging database
- [ ] Create deployment checklist

### 15.2 Database Migration - Production

- [ ] Backup production database
- [ ] Run migration on production
- [ ] Verify migration success
- [ ] Test database constraints
- [ ] Monitor for errors

### 15.3 Backend Deployment

- [ ] Deploy updated API to Cloud Run
- [ ] Verify deployment successful
- [ ] Test all new endpoints in production
- [ ] Monitor logs for errors
- [ ] Test email sending in production

### 15.4 Frontend Deployment

- [ ] Build production frontend: `npm run build`
- [ ] Deploy to Cloud Storage
- [ ] Test all pages in production
- [ ] Verify routing works
- [ ] Test verification flow end-to-end

### 15.5 Post-Deployment Monitoring

- [ ] Monitor API logs for 24 hours
- [ ] Monitor error rates
- [ ] Monitor email delivery rates
- [ ] Check database for any issues
- [ ] Verify rate limiting works
- [ ] Test with real users

**Acceptance Criteria:**
- Zero downtime deployment
- All features working in production
- No critical errors in logs
- Email delivery working
- Database migration successful

---

## Final Verification Checklist

### Functional Requirements

- [ ] Users can signup and login immediately (auto-login)
- [ ] Unverified users have full feature access
- [ ] Header shows verification status (yellow/green button)
- [ ] Users can resend verification email (rate limited)
- [ ] Users can verify email via email link
- [ ] Verified users can change email (dual verification)
- [ ] Verified users can change password
- [ ] Unverified users cannot change email/password
- [ ] All emails sent successfully
- [ ] All error cases handled gracefully

### Security Requirements

- [ ] Tokens properly signed and validated
- [ ] Rate limiting enforced on all endpoints
- [ ] Password confirmation required for sensitive ops
- [ ] Email verification required for account changes
- [ ] No user enumeration vulnerabilities
- [ ] XSS protection in place
- [ ] SQL injection protection in place
- [ ] Passwords properly hashed with bcrypt
- [ ] Audit logging complete

### Code Quality Requirements

- [ ] No file exceeds 1000 lines
- [ ] Services properly separated (Auth, Verification, Account, Email, Token)
- [ ] Routes properly separated (auth.py, account.py, verification.py if needed)
- [ ] Models clearly defined and validated
- [ ] Components modular and reusable
- [ ] No code duplication
- [ ] Clear comments and docstrings
- [ ] Consistent code style
- [ ] All TypeScript types defined
- [ ] No TypeScript 'any' types (where possible)

### Testing Requirements

- [ ] Unit test coverage >80%
- [ ] Integration tests pass
- [ ] E2E tests pass
- [ ] Security tests pass
- [ ] All edge cases covered
- [ ] Error cases tested

### Documentation Requirements

- [ ] API documentation complete
- [ ] User guide complete
- [ ] Developer setup guide updated
- [ ] PROGRESS.md updated
- [ ] DECISIONS.md updated
- [ ] Code comments clear

---

## Progress Tracking

**Start Date:** _____________
**Target End Date:** _____________
**Actual End Date:** _____________

### Phase Completion

- [ ] Phase 1: Database Changes (Day 1)
- [ ] Phase 2: Backend Services (Days 2-3)
- [ ] Phase 3: Backend Models (Day 3)
- [ ] Phase 4: Backend Routes - Modifications (Days 4-5)
- [ ] Phase 5: Backend Routes - Verification (Day 5)
- [ ] Phase 6: Backend Routes - Account (Days 6-7)
- [ ] Phase 7: Backend Audit Logging (Day 7)
- [ ] Phase 8: Frontend Services (Day 8)
- [ ] Phase 9: Frontend Components (Days 9-10)
- [ ] Phase 10: Frontend Routing (Day 10)
- [ ] Phase 11: Email Templates (Day 11)
- [ ] Phase 12: Backend Testing (Days 12-13)
- [ ] Phase 13: Frontend Testing (Day 13)
- [ ] Phase 14: Documentation (Day 14)
- [ ] Phase 15: Deployment (Day 14)

### Blockers / Issues

_Document any blockers or issues encountered during implementation:_

1.
2.
3.

---

## Notes for Implementation

### Modular Structure Guidelines

1. **Backend Services:**
   - Keep AuthService focused on authentication (signup, login, password hashing)
   - Move verification logic to VerificationService
   - Move account management to AccountService
   - Keep each service under 500 lines

2. **Backend Routes:**
   - Keep auth.py for authentication routes
   - Create account.py for account management routes
   - Consider verification.py if auth.py exceeds 800 lines
   - Each route file should handle one logical domain

3. **Frontend Components:**
   - One component per file
   - Keep components under 300 lines
   - Extract complex logic to custom hooks if needed
   - Separate CSS files for each component

4. **Reusable Components:**
   - Consider creating Button, Input, Alert components
   - Create FormGroup component for consistent form styling
   - Create LoadingSpinner component

5. **Error Handling:**
   - Create centralized error handler utility
   - Consistent error message formatting
   - Log errors appropriately (backend)
   - Show user-friendly messages (frontend)

### Performance Considerations

- [ ] Database queries optimized (use indexes)
- [ ] Email sending non-blocking (async if possible)
- [ ] Frontend lazy loading for routes
- [ ] API response caching where appropriate
- [ ] Rate limiting configured correctly

### Accessibility Considerations

- [ ] All buttons have proper ARIA labels
- [ ] Form inputs have associated labels
- [ ] Error messages announced to screen readers
- [ ] Keyboard navigation works
- [ ] Color contrast meets WCAG standards

---

**End of Checklist**

*Last Updated: 2025-11-09*
