# Bug Tracker - TelegramFunnel OCTOBER/10-26

**Last Updated:** 2025-11-11 Session 105g

---

## Active Bugs

### 🐛 Documentation: Invalid Example EVM Address (Low Priority)

**Date Discovered:** 2025-11-08 Session 83
**File:** WALLET_ADDRESS_VALIDATION_ANALYSIS.md
**Severity:** LOW - Documentation only, no production impact
**Status:** 🔍 **DOCUMENTED - NOT URGENT**

**Issue:**
Example EVM address used throughout documentation has only 39 hex characters instead of required 40.

**Invalid Address:**
```
0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb  ← Only 39 hex chars (should be 40)
```

**Locations:**
- Line 43: Input placeholder example
- Line 56: Address format explanation
- Line 788: Test addresses object
- Line 847: User scenario example

**Expected Format:**
- EVM addresses: `0x` + exactly 40 hexadecimal characters
- Total length: 42 characters
- Example of valid address: `0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb0` (added one char)

**Impact:**
- ✅ Production code unaffected - validation working correctly
- ✅ Rejects invalid addresses as expected
- ⚠️ Documentation examples misleading (shows invalid address as example)
- ⚠️ Could confuse developers reading the docs

**Fix Required:**
Replace all instances with valid 40-hex-char EVM address like:
`0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb0`

**Priority:** Low - Can be fixed during next documentation update

---

## Recently Resolved

### ✅ [FIXED] Database Query Error - sub_value Column in Donation Workflow

**Date Discovered:** 2025-11-11 Session 105g
**Date Resolved:** 2025-11-11 Session 105g
**File:** `database.py`
**Severity:** HIGH - Blocked all donation attempts
**Resolution Time:** Immediate

**Issue:**
Donation workflow crashed when users tried to make donations due to database column error.

**Error Message:**
```
❌ Error fetching channel details: column "sub_value" does not exist
LINE 5:                     sub_value
```

**Root Cause:**
- `get_channel_details_by_open_id()` method queried `sub_value` column
- This method was created in Session 105e for donation message formatting
- `sub_value` is subscription pricing data, not relevant for donations
- Donations use user-entered amounts from numeric keypad
- Mixing donation and subscription logic caused database query failure

**Impact:**
- ❌ ALL donation attempts failed
- ❌ Users couldn't complete donation flow
- ✅ Subscription workflow unaffected (uses different methods)

**Fix Applied:**
**Location:** `database.py::get_channel_details_by_open_id()` lines 314-367

**Changes:**
1. Removed `sub_value` from SELECT query
2. Updated method to only fetch:
   - `closed_channel_title`
   - `closed_channel_description`
3. Updated docstring to clarify "exclusively for donation workflow"
4. Verified only title/description are used in `donation_input_handler.py`

**Before:**
```sql
SELECT
    closed_channel_title,
    closed_channel_description,
    sub_value  -- ❌ Doesn't exist / not needed
FROM main_clients_database
WHERE open_channel_id = %s
```

**After:**
```sql
SELECT
    closed_channel_title,
    closed_channel_description  -- ✅ Only what's needed
FROM main_clients_database
WHERE open_channel_id = %s
```

**Verification:**
- ✅ Method only used by donation workflow
- ✅ Donation flow only needs title/description for display
- ✅ Donation amount comes from user keypad input (not database)
- ✅ Subscription workflow uses separate methods (unaffected)

**Lessons Learned:**
1. Separate donation and subscription logic - they're different business flows
2. Don't assume column existence - verify schema before querying
3. Document method scope clearly - added "donation-specific" to docstring
4. Test all user-facing flows after database changes

**Related:**
- Session 105e: Created `get_channel_details_by_open_id()` method (introduced bug)
- Session 105g: Fixed by removing subscription-specific column query

---

### ✅ RESOLVED: Signup Validation Error Causes 500 Internal Server Error (CRITICAL)

**Date Discovered:** 2025-11-09 Session 101
**Date Resolved:** 2025-11-09 Session 101 (same session)
**Service:** GCRegisterAPI-10-26
**Severity:** CRITICAL - Production signup completely broken for users with weak passwords
**Status:** ✅ **RESOLVED**

**User Report:**
User attempted to create account with credentials:
- Username: `slickjunt`
- Email: `slickjunt@gmail.com`
- Password: `herpderp123`

Result: "Internal server error" displayed on signup page

**Root Causes Identified:**

**1. Password Validation Failure (Expected Behavior):**
- Password `herpderp123` failed validation requirements
- Missing required uppercase letter (all lowercase)
- Pydantic validator in `SignupRequest` model correctly raised `ValueError`
- File: `api/models/auth.py` lines 27-39

**2. JSON Serialization Bug in Error Handler (Actual Bug):**
- ValidationError handler attempted to return `e.errors()` directly in JSON response
- Pydantic's `ValidationError.errors()` contains non-serializable Python exception objects
- Flask's `jsonify()` crashed with: `TypeError: Object of type ValueError is not JSON serializable`
- This converted a proper 400 validation error into a 500 server error
- File: `api/routes/auth.py` lines 108-125

**Error Flow:**
1. User submits password without uppercase letter
2. Line 55: `SignupRequest(**request.json)` raises `ValidationError`
3. Line 108: Caught by `except ValidationError as e:` handler
4. Line 121-125: Handler tries to jsonify `e.errors()` containing ValueError objects
5. Flask JSON encoder crashes → Returns 500 instead of 400

**Cloud Logging Evidence:**
```
Traceback (most recent call last):
  File "/usr/local/lib/python3.11/site-packages/flask/json/provider.py", line 120, in _default
    raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")
TypeError: Object of type ValueError is not JSON serializable
```

**Resolution:**

**File Modified:** `api/routes/auth.py` lines 108-134

**Before (Broken):**
```python
except ValidationError as e:
    print(f"❌ Signup validation error: {e.errors()}")
    # ... audit logging ...
    return jsonify({
        'success': False,
        'error': 'Validation failed',
        'details': e.errors()  # ← CRASHES: Contains ValueError objects
    }), 400
```

**After (Fixed):**
```python
except ValidationError as e:
    print(f"❌ Signup validation error: {e.errors()}")
    # ... audit logging ...

    # Convert validation errors to JSON-safe format
    error_details = []
    for error in e.errors():
        error_details.append({
            'field': '.'.join(str(loc) for loc in error['loc']),
            'message': error['msg'],
            'type': error['type']
        })

    return jsonify({
        'success': False,
        'error': 'Validation failed',
        'details': error_details  # ← SAFE: Pure dict/str/int types
    }), 400
```

**Deployment:**
- Build ID: Auto-generated by Cloud Build
- Revision: `gcregisterapi-10-26-00022-d2n`
- Deployed: 2025-11-09 Session 101
- Service URL: https://gcregisterapi-10-26-pjxwjsdktq-uc.a.run.app

**Testing Performed:**

**Test 1: Invalid Password (No Uppercase)**
```bash
# Input: username=slickjunt, email=slickjunt@gmail.com, password=herpderp123
# Expected: 400 Bad Request with validation error message
# Result: ✅ Returns 400 with "Validation failed" message
# Frontend displays: "Validation failed" (not "Internal server error")
```

**Test 2: Valid Password (With Uppercase)**
```bash
# Input: username=slickjunt2, email=slickjunt2@gmail.com, password=Herpderp123
# Expected: 201 Created, account created, auto-login
# Result: ✅ Account created successfully
# Redirected to dashboard with "Please Verify E-Mail" button
```

**Impact:**
- ✅ Signup errors now return proper 400 status codes (not 500)
- ✅ Users receive clear validation error messages
- ✅ Frontend can display specific field errors
- ✅ Server no longer crashes on validation failures
- ✅ Audit logging still works correctly
- ✅ Password validation requirements enforced properly

**Password Requirements:**
- Minimum 8 characters
- At least one uppercase letter (A-Z)
- At least one lowercase letter (a-z)
- At least one digit (0-9)

**Files Changed:**
1. `GCRegisterAPI-10-26/api/routes/auth.py` (lines 121-128 added)

**Lessons Learned:**
- Always serialize exception objects to strings before JSON encoding
- Test error handlers with actual failing inputs
- Pydantic validation errors need special handling for JSON responses
- 500 errors mask underlying validation issues - always return appropriate status codes

---

### 🔒 Database: Missing UNIQUE Constraints + Duplicate User Accounts (CRITICAL)

**Date Discovered:** 2025-11-09 Session 91
**Date Resolved:** 2025-11-09 Session 91
**Severity:** CRITICAL - Login completely broken for affected users
**Status:** ✅ **RESOLVED**

**User Report:**
- Cannot login with user1 (user1TEST$) or user2 (user2TEST$)
- Verification link clicked successfully showing "Email already verified"
- Login fails with error: "Invalid username or password"

**Root Cause:**
1. **Missing UNIQUE Constraints**: Database table `registered_users` had no UNIQUE constraints on username or email columns
2. **Duplicate Accounts Created**: user2 was registered TWICE:
   - First: 2025-11-09 13:55:15 (revision 00015-hrc) with password hash A
   - Second: 2025-11-09 14:09:16 (revision 00016-kds) with password hash B
3. **Password Mismatch**: User tried to login with password from first registration, but database had second registration with different hash
4. **Application-Level Only**: Duplicate checks existed in `auth_service.py` but no database-level enforcement

**Investigation Timeline:**
1. Used Playwright to test login → Captured 401 Unauthorized errors
2. Analyzed Cloud Logging → Found "Invalid username or password" in audit logs
3. Tested API directly with curl → Confirmed backend returning 401
4. Reviewed auth_service.py → Authentication logic correct (lines 135-198)
5. Checked database records → Discovered multiple user2 entries with different created_at timestamps

**Technical Analysis:**
```sql
-- BEFORE FIX: This query would return multiple rows
SELECT username, COUNT(*) as count, array_agg(user_id ORDER BY created_at)
FROM registered_users
GROUP BY username
HAVING COUNT(*) > 1;

-- user2 appeared twice with different user_ids and password_hashes
```

**Resolution:**

**1. Created Migration Script:**
- File: `database/migrations/fix_duplicate_users_add_unique_constraints.sql`
- Deleted duplicate username records (kept most recent by created_at DESC)
- Deleted duplicate email records (kept most recent by created_at DESC)
- Added UNIQUE constraint on username column
- Added UNIQUE constraint on email column

**2. Created Migration Executor:**
- File: `run_migration.py`
- Uses application's DatabaseManager for connection
- Executes migration with transaction safety
- Reports deleted records and constraint additions
- Verifies constraints after migration

**3. Migration Execution:**
```bash
python3 run_migration.py
```

**Migration Results:**
- Deleted: 0 duplicate username records (already cleaned up)
- Deleted: 0 duplicate email records (already cleaned up)
- Added: UNIQUE constraint "unique_username" on username column
- Added: UNIQUE constraint "unique_email" on email column
- Database now has 4 total UNIQUE constraints

**Files Changed:**
1. `database/migrations/fix_duplicate_users_add_unique_constraints.sql` - NEW FILE (comprehensive migration)
2. `run_migration.py` - NEW FILE (migration executor script)

**Current State:**
- ✅ Database has UNIQUE constraints on username and email
- ✅ Duplicate registration now IMPOSSIBLE at database level
- ✅ Application-level checks backed by DB constraints
- ✅ user2 account verified and exists (created 14:09:16)
- ⚠️ user2 password hash is from SECOND registration (not first)

**User Impact:**
- **user2**: Account exists and verified, but password is from second registration (may need reset)
- **user1**: Should work with original password (if remembered)
- **Future users**: Protected from duplicate account issues

**Testing Performed:**
```bash
# Test duplicate username - BLOCKED
curl -X POST /api/auth/signup \
  -d '{"username":"user2","email":"new@test.com","password":"Test1234$"}'
# Response: {"error":"Username already exists","success":false}

# Test duplicate email - BLOCKED
curl -X POST /api/auth/signup \
  -d '{"username":"newuser","email":"user4test@test.com","password":"Test1234$"}'
# Response: {"error":"Email already exists","success":false}

# Test new registration - WORKS
curl -X POST /api/auth/signup \
  -d '{"username":"user4","email":"user4test@test.com","password":"user4TEST$"}'
# Response: {"success":true,"verification_required":true,...}
```

**Prevention Measures:**
1. ✅ UNIQUE constraints enforce uniqueness at database level
2. ✅ PostgreSQL will reject INSERT/UPDATE that violates constraints
3. ✅ Application code already handles constraint violations gracefully
4. ✅ Constraint violations return proper error messages to users

**Lessons Learned:**
- Always add UNIQUE constraints for fields that must be unique
- Database constraints provide critical safety net beyond application-level checks
- Test duplicate scenarios thoroughly before production
- Monitor for duplicate data patterns in logs

