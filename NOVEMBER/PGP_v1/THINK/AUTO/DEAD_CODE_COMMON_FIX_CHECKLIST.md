# Code Consolidation Checklist: PGP_COMMON Centralization

**Generated:** 2025-11-18
**Purpose:** Systematically consolidate duplicate functions across PGP_X_v1 services into PGP_COMMON
**Scope:** Code bloat reduction through centralization (NOT dead code removal)
**Status:** 🔴 NOT STARTED

---

## Executive Summary

### Duplication Statistics

| Category | Duplicate Lines | Services Affected | Priority |
|----------|----------------|-------------------|----------|
| Database Methods | ~640 lines | 3 services (ORCHESTRATOR, NP_IPN, INVITE) | 🔴 CRITICAL |
| Crypto Pricing | ~180 lines | 2 services (NP_IPN, INVITE) | 🟡 HIGH |
| Inline DB Operations | ~300 lines | 1 service (NP_IPN) | 🟡 MEDIUM |
| ChangeNow Client | ~120 lines | 2 services (SPLIT2, SPLIT3) | 🟢 LOW |
| Signature Verification | ~30 lines | 1 service (SPLIT1) | 🟢 LOW |
| **TOTAL** | **~1,270 lines** | **9 services** | - |

### What This Checklist Does:
✅ Identifies duplicate functions across services
✅ Plans consolidation into PGP_COMMON
✅ Maintains service functionality (no structural changes)
✅ Reduces code bloat and improves maintainability

### What This Checklist Does NOT Do:
❌ Remove dead code (see separate DEAD_CODE_CLEANUP_CHECKLIST.md)
❌ Change service architecture
❌ Refactor service-specific logic

---

## Phase 1: Database Method Consolidation 🔴 CRITICAL

**Priority:** HIGHEST
**Estimated Impact:** ~640 lines reduced
**Services Affected:** PGP_ORCHESTRATOR_v1, PGP_NP_IPN_v1, PGP_INVITE_v1
**Status:** ⬜ NOT STARTED

### 1.1 Identify Duplicate Database Methods

#### Method 1: `record_private_channel_user()`
- **Status:** ⬜ NOT ANALYZED
- **Location 1:** `PGP_ORCHESTRATOR_v1/database_manager.py`
- **Location 2:** `PGP_NP_IPN_v1/database_manager.py`
- **Lines:** ~100 lines each (200 total)
- **Purpose:** Records user subscription to database
- **Verification Command:**
  ```bash
  grep -rn "def record_private_channel_user" PGP_ORCHESTRATOR_v1/ PGP_NP_IPN_v1/ --include="*.py"
  ```

#### Method 2: `get_payout_strategy()`
- **Status:** ⬜ NOT ANALYZED
- **Location 1:** `PGP_ORCHESTRATOR_v1/database_manager.py`
- **Location 2:** `PGP_NP_IPN_v1/database_manager.py`
- **Lines:** ~50 lines each (100 total)
- **Purpose:** Fetches client payout strategy (instant vs threshold)
- **Verification Command:**
  ```bash
  grep -rn "def get_payout_strategy" PGP_ORCHESTRATOR_v1/ PGP_NP_IPN_v1/ --include="*.py"
  ```

#### Method 3: `get_subscription_id()`
- **Status:** ⬜ NOT ANALYZED
- **Location 1:** `PGP_ORCHESTRATOR_v1/database_manager.py`
- **Location 2:** `PGP_NP_IPN_v1/database_manager.py`
- **Lines:** ~50 lines each (100 total)
- **Purpose:** Gets subscription ID for user/channel combo
- **Verification Command:**
  ```bash
  grep -rn "def get_subscription_id" PGP_ORCHESTRATOR_v1/ PGP_NP_IPN_v1/ --include="*.py"
  ```

#### Method 4: `get_nowpayments_data()`
- **Status:** ⬜ NOT ANALYZED
- **Location 1:** `PGP_ORCHESTRATOR_v1/database_manager.py`
- **Location 2:** `PGP_NP_IPN_v1/database_manager.py`
- **Location 3:** `PGP_INVITE_v1/database_manager.py`
- **Lines:** ~80 lines each (240 total)
- **Purpose:** Fetches NowPayments payment data
- **Verification Command:**
  ```bash
  grep -rn "def get_nowpayments_data" PGP_ORCHESTRATOR_v1/ PGP_NP_IPN_v1/ PGP_INVITE_v1/ --include="*.py"
  ```

### 1.2 Move Methods to PGP_COMMON/database/db_manager.py

#### Task 1.2.1: Read and Compare Implementations
- [ ] Read `PGP_ORCHESTRATOR_v1/database_manager.py` - `record_private_channel_user()`
- [ ] Read `PGP_NP_IPN_v1/database_manager.py` - `record_private_channel_user()`
- [ ] Compare implementations for differences (print statements, error handling)
- [ ] Document any differences in a comparison file

#### Task 1.2.2: Add Methods to BaseDatabaseManager
- [ ] Open `PGP_COMMON/database/db_manager.py`
- [ ] Add `record_private_channel_user()` method
- [ ] Add `get_payout_strategy()` method
- [ ] Add `get_subscription_id()` method
- [ ] Add `get_nowpayments_data()` method
- [ ] Ensure proper error handling and logging
- [ ] Add docstrings explaining the methods are shared

**Expected Addition to PGP_COMMON/database/db_manager.py:**
```python
def record_private_channel_user(self, user_id: int, closed_channel_id: int, ...) -> bool:
    """
    Record user subscription to private channel (SHARED METHOD).

    Used by: PGP_ORCHESTRATOR_v1, PGP_NP_IPN_v1

    Args:
        user_id: Telegram user ID
        closed_channel_id: Closed channel ID
        ...

    Returns:
        True if successful, False otherwise
    """
    # Implementation...

def get_payout_strategy(self, closed_channel_id: int) -> tuple:
    """
    Get payout strategy for client (SHARED METHOD).

    Used by: PGP_ORCHESTRATOR_v1, PGP_NP_IPN_v1

    Returns:
        Tuple of (payout_mode, threshold_usdt) or (None, None) if not found
    """
    # Implementation...

def get_subscription_id(self, user_id: int, closed_channel_id: int) -> int:
    """
    Get subscription ID for user/channel combo (SHARED METHOD).

    Used by: PGP_ORCHESTRATOR_v1, PGP_NP_IPN_v1

    Returns:
        Subscription ID or None if not found
    """
    # Implementation...

def get_nowpayments_data(self, user_id: int, closed_channel_id: int) -> Optional[dict]:
    """
    Get NowPayments payment data (SHARED METHOD).

    Used by: PGP_ORCHESTRATOR_v1, PGP_NP_IPN_v1, PGP_INVITE_v1

    Returns:
        Dictionary with payment data or None if not found
    """
    # Implementation...
```

### 1.3 Update Services to Use Inherited Methods

#### Task 1.3.1: Update PGP_ORCHESTRATOR_v1
- [ ] Open `PGP_ORCHESTRATOR_v1/database_manager.py`
- [ ] Remove `record_private_channel_user()` method (~100 lines)
- [ ] Remove `get_payout_strategy()` method (~50 lines)
- [ ] Remove `get_subscription_id()` method (~50 lines)
- [ ] Remove `get_nowpayments_data()` method (~80 lines)
- [ ] Verify class still inherits from `BaseDatabaseManager`
- [ ] Test that service still works (run locally)

#### Task 1.3.2: Update PGP_NP_IPN_v1
- [ ] Open `PGP_NP_IPN_v1/database_manager.py`
- [ ] Remove `record_private_channel_user()` method (~100 lines)
- [ ] Remove `get_payout_strategy()` method (~50 lines)
- [ ] Remove `get_subscription_id()` method (~50 lines)
- [ ] Remove `get_nowpayments_data()` method (~80 lines)
- [ ] Verify class still inherits from `BaseDatabaseManager`
- [ ] Test that service still works (run locally)

#### Task 1.3.3: Update PGP_INVITE_v1
- [ ] Open `PGP_INVITE_v1/database_manager.py`
- [ ] Remove `get_nowpayments_data()` method (~80 lines)
- [ ] Verify class still inherits from `BaseDatabaseManager`
- [ ] Test that service still works (run locally)

### 1.4 Verification & Testing

#### Unit Testing
- [ ] Test `record_private_channel_user()` with mock data
- [ ] Test `get_payout_strategy()` with different client IDs
- [ ] Test `get_subscription_id()` with valid/invalid combinations
- [ ] Test `get_nowpayments_data()` with existing/missing data

#### Integration Testing
- [ ] Test PGP_ORCHESTRATOR_v1 payment flow (uses all 4 methods)
- [ ] Test PGP_NP_IPN_v1 IPN callback flow (uses all 4 methods)
- [ ] Test PGP_INVITE_v1 payment validation (uses get_nowpayments_data)

#### Syntax Verification
```bash
# Verify Python syntax
python3 -m py_compile PGP_COMMON/database/db_manager.py
python3 -m py_compile PGP_ORCHESTRATOR_v1/database_manager.py
python3 -m py_compile PGP_NP_IPN_v1/database_manager.py
python3 -m py_compile PGP_INVITE_v1/database_manager.py

# Verify imports work
python3 -c "from PGP_ORCHESTRATOR_v1.database_manager import DatabaseManager"
python3 -c "from PGP_NP_IPN_v1.database_manager import DatabaseManager"
python3 -c "from PGP_INVITE_v1.database_manager import DatabaseManager"
```

---

## Phase 2: Crypto Pricing Module Creation 🟡 HIGH

**Priority:** HIGH
**Estimated Impact:** ~180 lines reduced
**Services Affected:** PGP_NP_IPN_v1, PGP_INVITE_v1
**Status:** ⬜ NOT STARTED

### 2.1 Identify Duplicate Crypto Pricing Methods

#### Method 1: `get_crypto_usd_price()`
- **Status:** ⬜ NOT ANALYZED
- **Location 1:** `PGP_NP_IPN_v1/pgp_np_ipn_v1.py` (inline, lines 156-216)
- **Location 2:** `PGP_INVITE_v1/database_manager.py` (method, lines 142-201)
- **Lines:** ~60 lines each (120 total)
- **Purpose:** Fetches crypto price from CoinGecko API
- **Verification Command:**
  ```bash
  grep -rn "def get_crypto_usd_price\|coingecko" PGP_NP_IPN_v1/ PGP_INVITE_v1/ --include="*.py"
  ```

#### Method 2: `convert_crypto_to_usd()`
- **Status:** ⬜ NOT ANALYZED
- **Location 1:** `PGP_NP_IPN_v1/pgp_np_ipn_v1.py` (inline)
- **Location 2:** `PGP_INVITE_v1/database_manager.py` (method, lines 203-235)
- **Lines:** ~30 lines each (60 total)
- **Purpose:** Converts crypto amount to USD
- **Verification Command:**
  ```bash
  grep -rn "def convert_crypto_to_usd" PGP_NP_IPN_v1/ PGP_INVITE_v1/ --include="*.py"
  ```

### 2.2 Create PGP_COMMON/utils/crypto_pricing.py

#### Task 2.2.1: Create Crypto Pricing Module
- [ ] Create file `PGP_COMMON/utils/crypto_pricing.py`
- [ ] Add `CryptoPricingClient` class
- [ ] Add `__init__()` with symbol mapping
- [ ] Add `get_crypto_usd_price()` method
- [ ] Add `convert_crypto_to_usd()` method
- [ ] Add proper error handling and logging
- [ ] Add docstrings

**Expected Implementation:**
```python
#!/usr/bin/env python
"""
Crypto Pricing Client for PGP_v1 Services.
Fetches cryptocurrency prices from CoinGecko API.
"""
import requests
from typing import Optional


class CryptoPricingClient:
    """
    Shared crypto price fetching and conversion logic.

    Used by: PGP_NP_IPN_v1, PGP_INVITE_v1

    Features:
    - Fetches real-time prices from CoinGecko API
    - Converts crypto amounts to USD
    - Handles stablecoins (USDT, USDC) as $1.00
    - Error handling for API failures
    """

    def __init__(self):
        """Initialize CryptoPricingClient with symbol mapping."""
        self.symbol_map = {
            'eth': 'ethereum',
            'btc': 'bitcoin',
            'ltc': 'litecoin',
            'usdt': 'tether',
            'usdc': 'usd-coin',
            # Add more as needed
        }
        self.coingecko_api = "https://api.coingecko.com/api/v3/simple/price"

    def get_crypto_usd_price(self, crypto_symbol: str) -> Optional[float]:
        """
        Fetch current USD price from CoinGecko API.

        Args:
            crypto_symbol: Crypto symbol (e.g., 'eth', 'btc')

        Returns:
            USD price or None if failed
        """
        # Implementation...

    def convert_crypto_to_usd(self, amount: float, crypto_symbol: str) -> Optional[float]:
        """
        Convert crypto amount to USD using current market rate.

        Args:
            amount: Crypto amount
            crypto_symbol: Crypto symbol (e.g., 'eth', 'btc')

        Returns:
            USD value or None if failed
        """
        # Implementation...
```

#### Task 2.2.2: Update PGP_COMMON/utils/__init__.py
- [ ] Open `PGP_COMMON/utils/__init__.py`
- [ ] Add import: `from .crypto_pricing import CryptoPricingClient`
- [ ] Make it available at package level

### 2.3 Update Services to Use Shared Crypto Pricing

#### Task 2.3.1: Update PGP_NP_IPN_v1
- [ ] Open `PGP_NP_IPN_v1/pgp_np_ipn_v1.py`
- [ ] Add import: `from PGP_COMMON.utils import CryptoPricingClient`
- [ ] Initialize `pricing_client = CryptoPricingClient()` in global scope
- [ ] Replace inline `get_crypto_usd_price()` calls (lines ~156-216)
- [ ] Replace inline `convert_crypto_to_usd()` calls
- [ ] Test payment validation flow

#### Task 2.3.2: Update PGP_INVITE_v1
- [ ] Open `PGP_INVITE_v1/database_manager.py`
- [ ] Add import: `from PGP_COMMON.utils import CryptoPricingClient`
- [ ] Initialize `self.pricing_client = CryptoPricingClient()` in `__init__`
- [ ] Remove `get_crypto_usd_price()` method (lines 142-201)
- [ ] Remove `convert_crypto_to_usd()` method (lines 203-235)
- [ ] Update `validate_payment_complete()` to use `self.pricing_client`
- [ ] Test payment validation flow

### 2.4 Verification & Testing

#### Unit Testing
- [ ] Test CoinGecko API calls for ETH, BTC, LTC
- [ ] Test conversion with stablecoins (USDT, USDC)
- [ ] Test conversion with volatile coins (ETH, BTC)
- [ ] Test error handling (API timeout, unknown symbol)

#### Integration Testing
- [ ] Test PGP_NP_IPN_v1 payment validation with real prices
- [ ] Test PGP_INVITE_v1 payment validation with real prices

---

## Phase 3: Inline Database Operations Refactoring 🟡 MEDIUM

**Priority:** MEDIUM
**Estimated Impact:** ~300 lines reduced
**Services Affected:** PGP_NP_IPN_v1
**Status:** ⬜ NOT STARTED

### 3.1 Identify Inline Database Operations

#### Operation 1: `get_db_connection()`
- **Status:** ⬜ NOT ANALYZED
- **Location:** `PGP_NP_IPN_v1/pgp_np_ipn_v1.py` (lines 273-291)
- **Lines:** ~20 lines
- **Issue:** Should use `DatabaseManager.get_connection()`
- **Verification Command:**
  ```bash
  grep -rn "def get_db_connection" PGP_NP_IPN_v1/ --include="*.py"
  ```

#### Operation 2: `parse_order_id()`
- **Status:** ⬜ NOT ANALYZED
- **Location:** `PGP_NP_IPN_v1/pgp_np_ipn_v1.py` (lines 222-271)
- **Lines:** ~50 lines
- **Issue:** Should be in `database_manager.py` or `token_manager.py`
- **Verification Command:**
  ```bash
  grep -rn "def parse_order_id" PGP_NP_IPN_v1/ --include="*.py"
  ```

#### Operation 3: `update_payment_data()`
- **Status:** ⬜ NOT ANALYZED
- **Location:** `PGP_NP_IPN_v1/pgp_np_ipn_v1.py` (lines 294-540)
- **Lines:** ~246 lines (MASSIVE!)
- **Issue:** Should be in `database_manager.py`
- **Verification Command:**
  ```bash
  grep -rn "def update_payment_data" PGP_NP_IPN_v1/ --include="*.py"
  ```

### 3.2 Move Operations to DatabaseManager

#### Task 3.2.1: Move parse_order_id()
- [ ] Read `PGP_NP_IPN_v1/pgp_np_ipn_v1.py` lines 222-271
- [ ] Open `PGP_NP_IPN_v1/database_manager.py`
- [ ] Add `parse_order_id()` method
- [ ] Remove from main service file
- [ ] Update calls to use `db_manager.parse_order_id()`
- [ ] Test IPN callback flow

#### Task 3.2.2: Move update_payment_data()
- [ ] Read `PGP_NP_IPN_v1/pgp_np_ipn_v1.py` lines 294-540
- [ ] Open `PGP_NP_IPN_v1/database_manager.py`
- [ ] Add `update_payment_data()` method
- [ ] Remove from main service file (246 lines!)
- [ ] Update calls to use `db_manager.update_payment_data()`
- [ ] Test IPN callback flow

#### Task 3.2.3: Remove get_db_connection()
- [ ] Verify all calls use `self.db_manager.get_connection()` instead
- [ ] Remove `get_db_connection()` from main service file
- [ ] Test service startup

### 3.3 Verification & Testing

#### Code Quality Check
- [ ] Main service file reduced from 1304 → ~1000 lines
- [ ] Better separation of concerns
- [ ] Database logic centralized in database_manager.py

#### Functional Testing
- [ ] Test IPN callback processing
- [ ] Test order_id parsing
- [ ] Test payment data updates
- [ ] Test UPSERT logic for duplicate callbacks

---

## Phase 4: ChangeNow Client Consolidation 🟢 LOW

**Priority:** LOW (Architecture Decision Required)
**Estimated Impact:** ~120 lines reduced
**Services Affected:** PGP_SPLIT2_v1, PGP_SPLIT3_v1
**Status:** ⬜ NOT STARTED

### 4.1 Analyze ChangeNow Client Duplication

#### Task 4.1.1: Compare Implementations
- [ ] Read `PGP_SPLIT2_v1/changenow_client.py` (179 lines)
- [ ] Read `PGP_SPLIT3_v1/changenow_client.py` (180 lines)
- [ ] Identify differences:
  - SPLIT2: `get_estimated_amount_v2_with_retry()`
  - SPLIT3: `create_fixed_rate_transaction_with_retry()`
  - SPLIT2: Has hot-reload via `config_manager` ✅
  - SPLIT3: NO hot-reload (stores `api_key` in `__init__`) ❌

#### Task 4.1.2: Document Retry Logic Duplication
- [ ] Both have IDENTICAL infinite retry logic (60-second backoff)
- [ ] Same error handling (429, 5xx, timeout, connection)
- [ ] Same logging patterns
- [ ] Total duplicate: ~60 lines of retry logic

### 4.2 Architecture Decision: Consolidate or Keep Separate?

#### Option A: Create PGP_COMMON/utils/changenow_client.py ✅
**Pros:**
- Eliminates ~120 lines of duplication
- Single source of truth for retry logic
- Consistent hot-reload across all services
- Easier to add caching or rate limiting

**Cons:**
- Couples services together (shared dependency)
- Requires all services to upgrade together

**Implementation:**
```python
# PGP_COMMON/utils/changenow_client.py

class ChangeNowClient:
    """
    Shared ChangeNow API client with retry logic.

    Used by: PGP_SPLIT2_v1, PGP_SPLIT3_v1, PGP_MICROBATCHPROCESSOR_v1
    """

    def __init__(self, config_manager):
        """Initialize with config_manager for hot-reload."""
        self.config_manager = config_manager

    def get_estimated_amount_v2_with_retry(...):
        """Get estimate with infinite retry (SPLIT2)."""
        # Implementation with hot-reload api_key

    def create_fixed_rate_transaction_with_retry(...):
        """Create swap with infinite retry (SPLIT3)."""
        # Implementation with hot-reload api_key
```

#### Option B: Keep Separate (Accept Duplication) ❌
**Pros:**
- Services remain independent (microservice isolation)
- Each service owns its client logic

**Cons:**
- ~120 lines of duplicate code
- SPLIT3 lacks hot-reload (needs fix)
- Changes to retry logic require updating 2-3 files

### 4.3 Recommended Action

- [ ] **DECISION REQUIRED:** Choose Option A or Option B
- [ ] If Option A: Create `PGP_COMMON/utils/changenow_client.py`
- [ ] If Option A: Update SPLIT2, SPLIT3, MICROBATCH to use shared client
- [ ] If Option B: At minimum, add hot-reload to SPLIT3 for consistency

---

## Phase 5: Signature Verification Consolidation 🟢 LOW

**Priority:** LOW
**Estimated Impact:** ~30 lines reduced
**Services Affected:** PGP_SPLIT1_v1
**Status:** ⬜ NOT STARTED

### 5.1 Analyze Signature Verification Duplication

#### Current State
- **Location:** `PGP_SPLIT1_v1/pgp_split1_v1.py` lines 66-92
- **Purpose:** Verify webhook signature for security
- **Similar to:** `PGP_COMMON/auth/service_auth.py` (different pattern)

#### Task 5.1.1: Compare Implementations
- [ ] Read `PGP_SPLIT1_v1/pgp_split1_v1.py` lines 66-92
- [ ] Read `PGP_COMMON/auth/service_auth.py`
- [ ] Identify if patterns are compatible
- [ ] Document differences

### 5.2 Decision: Consolidate or Keep?

#### Option A: Use PGP_COMMON/auth Pattern
- [ ] Replace `verify_webhook_signature()` with PGP_COMMON/auth methods
- [ ] Update imports in PGP_SPLIT1_v1
- [ ] Test webhook signature verification

#### Option B: Keep Separate
- [ ] Accept that signature patterns may differ by service
- [ ] Document why (e.g., different security requirements)

---

## Phase 6: Final Verification & Documentation

### 6.1 Code Quality Verification

#### Syntax Checks
```bash
# Verify all modified files compile
find PGP_COMMON -name "*.py" -exec python3 -m py_compile {} \;
find PGP_ORCHESTRATOR_v1 -name "*.py" -exec python3 -m py_compile {} \;
find PGP_NP_IPN_v1 -name "*.py" -exec python3 -m py_compile {} \;
find PGP_INVITE_v1 -name "*.py" -exec python3 -m py_compile {} \;
```

#### Import Checks
```bash
# Verify imports work
python3 -c "from PGP_COMMON.database import BaseDatabaseManager"
python3 -c "from PGP_COMMON.utils import CryptoPricingClient"
```

### 6.2 Integration Testing Checklist

#### Database Methods
- [ ] Test record_private_channel_user() in ORCHESTRATOR and NP_IPN
- [ ] Test get_payout_strategy() routing (instant vs threshold)
- [ ] Test get_subscription_id() retrieval
- [ ] Test get_nowpayments_data() in all 3 services

#### Crypto Pricing
- [ ] Test price fetching for all supported coins
- [ ] Test conversion accuracy
- [ ] Test error handling (API down, unknown symbol)

#### Inline Operations
- [ ] Test NP_IPN callback flow end-to-end
- [ ] Test order_id parsing
- [ ] Test payment data UPSERT logic

### 6.3 Documentation Updates

#### Update DECISIONS.md
- [ ] Document decision to consolidate database methods
- [ ] Document decision to create crypto pricing module
- [ ] Document decision on ChangeNow client (Option A or B)
- [ ] Document rationale for refactoring inline operations

#### Update PROGRESS.md
- [ ] Log Phase 1 completion (database methods)
- [ ] Log Phase 2 completion (crypto pricing)
- [ ] Log Phase 3 completion (inline operations)
- [ ] Log overall code reduction (~1,270 lines)

#### Create Architecture Documentation
- [ ] Document shared vs service-specific patterns
- [ ] Document PGP_COMMON usage guidelines
- [ ] Document when to add to PGP_COMMON vs keep in service

---

## Expected Results

### Code Reduction Summary

| Phase | Lines Reduced | Services Updated | Status |
|-------|--------------|------------------|--------|
| Phase 1: Database Methods | ~640 lines | 3 services | ⬜ |
| Phase 2: Crypto Pricing | ~180 lines | 2 services | ⬜ |
| Phase 3: Inline Operations | ~300 lines | 1 service | ⬜ |
| Phase 4: ChangeNow Client | ~120 lines | 2 services | ⬜ |
| Phase 5: Signature Verification | ~30 lines | 1 service | ⬜ |
| **TOTAL** | **~1,270 lines** | **9 services** | **⬜** |

### Maintainability Improvements

**Before:**
- Database queries duplicated across 3 services
- Crypto pricing logic duplicated across 2 services
- 1304-line monolithic service file (NP_IPN)
- Inconsistent patterns (hot-reload in SPLIT2 but not SPLIT3)

**After:**
- Single source of truth in PGP_COMMON
- ~1,270 lines of duplicate code removed
- Cleaner separation of concerns
- Consistent patterns across all services
- Easier to maintain and test

---

## Risk Assessment

### Low Risk ✅
- Moving methods to PGP_COMMON (already exists and tested)
- Refactoring inline operations (improves code quality)
- All changes are local (no deployment until tested)

### Medium Risk ⚠️
- Crypto pricing module (new utility, needs thorough testing)
- ChangeNow consolidation (if Option A chosen)

### Mitigation Strategies
1. **Backup:** Keep backups in `ARCHIVES_PGP_v1/REMOVED_CODE/`
2. **Incremental:** Complete one phase at a time
3. **Testing:** Comprehensive unit + integration tests before moving to next phase
4. **Rollback:** All changes tracked in git history

---

## Next Steps

1. ✅ Review this checklist with stakeholder
2. ⬜ Get approval to proceed with Phase 1 (database methods)
3. ⬜ Execute Phase 1 systematically
4. ⬜ Test Phase 1 thoroughly
5. ⬜ Move to Phase 2 only after Phase 1 is verified
6. ⬜ Document all changes in DECISIONS.md and PROGRESS.md

---

**Status:** 📋 CHECKLIST COMPLETE - READY FOR REVIEW AND EXECUTION
**Next Action:** User approval to begin Phase 1
