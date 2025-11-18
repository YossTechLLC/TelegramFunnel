# Token Manager Centralization Checklist

**Objective**: Minimize code bloat by centralizing redundant token_manager.py code into PGP_COMMON while preserving service-specific token encryption/decryption logic.

**Scope**: 11 services with token_manager.py files
**Approach**: Systematic review → Identify redundancies → Centralize common code → Verify functionality preserved

---

## Executive Summary

### Current State
- **11 token_manager.py files** deployed across PGP_X_v1 services
- **BaseTokenManager** already exists in `PGP_COMMON/tokens/base_token.py`
- All service TokenManagers inherit from BaseTokenManager
- Significant code duplication in imports, helper methods, and patterns

### Redundancies Identified
1. ✅ **Already Centralized in BaseTokenManager**:
   - HMAC signature generation/verification
   - Base64 encoding/decoding (URL-safe)
   - String packing/unpacking with 1-byte length prefix
   - Timestamp handling (minutes conversion, reconstruction)
   - 48-bit ID packing/unpacking for Telegram IDs

2. ❌ **Duplicated Across Services** (needs cleanup):
   - Redundant `_pack_string()` and `_unpack_string()` methods in PGP_SPLIT3_v1 and PGP_MICROBATCHPROCESSOR_v1
   - Inconsistent use of inherited vs. local methods
   - Similar import patterns across all files

3. ✅ **Service-Specific** (must remain in each service):
   - Token format definitions for specific communication flows
   - Encryption methods (e.g., `encrypt_pgp_split1_to_pgp_split2_token`)
   - Decryption methods (e.g., `decrypt_pgp_split2_to_pgp_split1_token`)
   - Service-specific token field packing order

### Security Verification Required
- ✅ Use Google MCP to verify HMAC-SHA256 implementation meets financial app standards
- ✅ Use Context7 MCP to verify token exchange patterns follow best practices
- ✅ Ensure backward compatibility for token validation during migration

---

## Part 1: Architecture Analysis

### 1.1 Token Flow Mapping

**Token Communication Flows:**

```
NOWPayments → PGP_ORCHESTRATOR_v1 → PGP_INVITE_v1
                    ↓
              PGP_SPLIT1_v1 ↔ PGP_SPLIT2_v1 ↔ PGP_SPLIT3_v1
                    ↓
              PGP_BATCHPROCESSOR_v1 → PGP_MICROBATCHPROCESSOR_v1 → PGP_HOSTPAY1_v1
                    ↓
              PGP_ACCUMULATOR_v1 → PGP_SPLIT3_v1
                    ↓
              PGP_HOSTPAY1_v1 ↔ PGP_HOSTPAY2_v1 ↔ PGP_HOSTPAY3_v1
```

**Token Signing Keys Used:**
- `SUCCESS_URL_SIGNING_KEY`: NOWPayments → Orchestrator → Invite/Split flows
- `TPS_HOSTPAY_SIGNING_KEY`: Batch → MicroBatch → HostPay flows
- `PGP_INTERNAL_SIGNING_KEY`: HostPay1/2/3 internal communications

### 1.2 Service-by-Service Token Usage

| Service | Token Manager Init | Encrypt Methods | Decrypt Methods | Notes |
|---------|-------------------|-----------------|-----------------|-------|
| **PGP_ORCHESTRATOR_v1** | `TokenManager(signing_key)` | `decode_and_verify_token` (NOWPayments)<br>`encrypt_token_for_pgp_invite` | None | Entry point from NOWPayments |
| **PGP_INVITE_v1** | `TokenManager(signing_key)` | None | `decode_and_verify_token` | Terminal endpoint (sends Telegram invite) |
| **PGP_SPLIT1_v1** | `TokenManager(signing_key, batch_signing_key)` | `encrypt_pgp_split1_to_pgp_split2_token`<br>`encrypt_pgp_split1_to_pgp_split3_token` | `decrypt_pgp_split2_to_pgp_split1_token`<br>`decrypt_pgp_split3_to_pgp_split1_token`<br>`decrypt_batch_token` | Dual-key setup |
| **PGP_SPLIT2_v1** | `TokenManager(signing_key)` | `encrypt_pgp_split1_to_pgp_split2_token`<br>`encrypt_pgp_split2_to_pgp_split1_token` | `decrypt_pgp_split1_to_pgp_split2_token`<br>`decrypt_pgp_split2_to_pgp_split1_token` | Bidirectional with SPLIT1 |
| **PGP_SPLIT3_v1** | `TokenManager(signing_key)` | `encrypt_pgp_split1_to_pgp_split3_token`<br>`encrypt_pgp_split3_to_pgp_split1_token`<br>`encrypt_pgp_split3_to_accumulator_token` | `decrypt_pgp_split1_to_pgp_split3_token`<br>`decrypt_pgp_split3_to_pgp_split1_token`<br>`decrypt_accumulator_to_pgp_split3_token` | Has redundant `_pack/unpack_string` |
| **PGP_ACCUMULATOR_v1** | `TokenManager(signing_key)` | `encrypt_accumulator_to_pgp_split3_token` | `decrypt_pgp_split3_to_accumulator_token` | Uses inherited methods correctly |
| **PGP_BATCHPROCESSOR_v1** | `TokenManager(signing_key)` | `encrypt_batch_to_pgp_split1_token` | None | Sends to SPLIT1 |
| **PGP_MICROBATCHPROCESSOR_v1** | `TokenManager(signing_key)` | `encrypt_microbatch_to_pgp_hostpay1_token` | `decrypt_pgp_hostpay1_to_microbatch_token` | Has redundant `_pack/unpack_string` |
| **PGP_HOSTPAY1_v1** | `TokenManager(tps_hostpay_key, internal_key)` | `encrypt_pgp_hostpay1_to_pgp_hostpay2_token`<br>`encrypt_pgp_hostpay1_to_microbatch_token` | `decrypt_microbatch_to_pgp_hostpay1_token`<br>`decrypt_pgp_hostpay2_to_pgp_hostpay1_token` | Dual-key setup |
| **PGP_HOSTPAY2_v1** | `TokenManager(tps_hostpay_key, internal_key)` | `encrypt_pgp_hostpay1_to_pgp_hostpay2_token`<br>`encrypt_pgp_hostpay2_to_pgp_hostpay3_token` | `decrypt_pgp_hostpay1_to_pgp_hostpay2_token`<br>`decrypt_pgp_hostpay3_to_pgp_hostpay2_token` | Dual-key setup |
| **PGP_HOSTPAY3_v1** | `TokenManager(tps_hostpay_key, internal_key)` | `encrypt_pgp_hostpay2_to_pgp_hostpay3_token`<br>`encrypt_pgp_hostpay3_to_pgp_hostpay2_token` | `decrypt_pgp_hostpay2_to_pgp_hostpay3_token`<br>`decrypt_pgp_hostpay3_to_pgp_hostpay2_token` | Dual-key setup |

---

## Part 2: Redundancy Cleanup Tasks

### 2.1 PGP_SPLIT3_v1 - Remove Redundant Methods

**File**: `PGP_SPLIT3_v1/token_manager.py`

**Issue**: Lines 24-54 define `_pack_string()` and `_unpack_string()` methods that are already in BaseTokenManager

**Action Required**:
- [ ] Delete `_pack_string()` method (lines 24-37)
- [ ] Delete `_unpack_string()` method (lines 39-54)
- [ ] Verify all calls use `self.pack_string()` and `self.unpack_string()` (inherited from BaseTokenManager)
- [ ] Test token encryption/decryption still works

**Files to Check After Change**:
- `PGP_SPLIT3_v1/pgp_split3_v1.py` - ensure no import errors
- `PGP_SPLIT3_v1/token_manager.py` - verify calls use inherited methods

**Testing**:
```bash
# Run after changes
python3 PGP_SPLIT3_v1/token_manager.py  # Should not error on import
# Integration test with actual token flow
```

---

### 2.2 PGP_MICROBATCHPROCESSOR_v1 - Remove Redundant Methods

**File**: `PGP_MICROBATCHPROCESSOR_v1/token_manager.py`

**Issue**: Lines 31-44 define `_pack_string()` and `_unpack_string()` methods that are already in BaseTokenManager

**Action Required**:
- [ ] Delete `_pack_string()` method (lines 31-36)
- [ ] Delete `_unpack_string()` method (lines 38-44)
- [ ] Verify all calls use `self.pack_string()` and `self.unpack_string()` (inherited from BaseTokenManager)
- [ ] Update line 66: `self.pack_string('batch')` (already correct)
- [ ] Test token encryption/decryption still works

**Files to Check After Change**:
- `PGP_MICROBATCHPROCESSOR_v1/pgp_microbatchprocessor_v1.py`
- `PGP_MICROBATCHPROCESSOR_v1/token_manager.py`

---

### 2.3 Standardize Import Pattern

**Current Issue**: Some services have missing imports (e.g., PGP_SPLIT3_v1 missing `import struct`, `import time`, etc.)

**Action Required for Each Service**:
- [ ] **PGP_SPLIT3_v1**: Add missing imports at top of file
  ```python
  import base64
  import hmac
  import hashlib
  import struct
  import time
  ```

**Verify Import Consistency Across All Services**:
- [ ] PGP_ACCUMULATOR_v1 ✅ (already correct)
- [ ] PGP_BATCHPROCESSOR_v1 ✅ (already correct)
- [ ] PGP_HOSTPAY1_v1 ✅ (already correct)
- [ ] PGP_HOSTPAY2_v1 ✅ (already correct)
- [ ] PGP_HOSTPAY3_v1 ✅ (already correct)
- [ ] PGP_INVITE_v1 ✅ (already correct)
- [ ] PGP_MICROBATCHPROCESSOR_v1 ✅ (already correct)
- [ ] PGP_ORCHESTRATOR_v1 ✅ (uses minimal imports - correct)
- [ ] PGP_SPLIT1_v1 ✅ (already correct)
- [ ] PGP_SPLIT2_v1 ✅ (already correct)
- [ ] PGP_SPLIT3_v1 ❌ (missing imports - needs fix)

---

## Part 3: Enhanced BaseTokenManager (Optional Improvements)

### 3.1 Add Multi-Key Support to BaseTokenManager

**Current Issue**: Services with dual-key setup (SPLIT1, HOSTPAY1/2/3) handle this in their __init__, but pattern is duplicated

**Proposed Enhancement** (OPTIONAL):
```python
# PGP_COMMON/tokens/base_token.py

class BaseTokenManager:
    def __init__(self, signing_key: str, service_name: str, secondary_key: Optional[str] = None):
        """
        Initialize the BaseTokenManager.

        Args:
            signing_key: Primary signing key (SUCCESS_URL_SIGNING_KEY)
            service_name: Name of the service (for logging)
            secondary_key: Optional secondary key for dual-key services
        """
        self.signing_key = signing_key
        self.secondary_key = secondary_key if secondary_key else signing_key
        self.service_name = service_name
        print(f"🔐 [TOKEN] TokenManager initialized for {service_name}")
        if secondary_key:
            print(f"🔐 [TOKEN] Secondary signing key configured")

    def generate_hmac_signature_secondary(self, data: bytes, truncate_to: int = 16) -> bytes:
        """Generate HMAC using secondary key."""
        full_signature = hmac.new(
            self.secondary_key.encode(),
            data,
            hashlib.sha256
        ).digest()

        if truncate_to > 0:
            return full_signature[:truncate_to]
        return full_signature
```

**Action**:
- [ ] Decision: Implement multi-key support in BaseTokenManager? (Review with user first)
- [ ] If yes: Update BaseTokenManager
- [ ] If yes: Migrate SPLIT1, HOSTPAY1/2/3 to use new pattern
- [ ] If no: Keep current service-specific dual-key pattern

---

### 3.2 Add Token Format Documentation to BaseTokenManager

**Proposed Enhancement**:
Create a centralized token format registry for documentation purposes

```python
# PGP_COMMON/tokens/token_formats.py (NEW FILE)

"""
Token Format Registry for PGP_v1 Services.

This module documents all token formats used across the PGP_v1 architecture.
Each token format is defined by its communication flow and field structure.
"""

TOKEN_FORMATS = {
    "nowpayments_to_orchestrator": {
        "description": "NOWPayments success_url token format",
        "fields": [
            ("user_id", "6 bytes", "48-bit unsigned, converted to signed"),
            ("closed_channel_id", "6 bytes", "48-bit unsigned, converted to signed"),
            ("timestamp_minutes", "2 bytes", "uint16 (wrap-around at 65536)"),
            ("subscription_time_days", "2 bytes", "uint16"),
            ("subscription_price", "variable", "1-byte length + UTF-8 string"),
            ("wallet_address", "variable", "1-byte length + UTF-8 string"),
            ("payout_currency", "variable", "1-byte length + UTF-8 string"),
            ("payout_network", "variable", "1-byte length + UTF-8 string"),
            ("signature", "16 bytes", "HMAC-SHA256 truncated to 16 bytes"),
        ],
        "signing_key": "SUCCESS_URL_SIGNING_KEY",
        "expiration": "2 hours",
    },
    "split1_to_split2_estimate_request": {
        "description": "Token for PGP_SPLIT1_v1 → PGP_SPLIT2_v1 swap estimate request",
        "fields": [
            ("user_id", "8 bytes", "uint64"),
            ("closed_channel_id", "16 bytes", "fixed-length padded string"),
            ("wallet_address", "variable", "1-byte length + UTF-8 string"),
            ("payout_currency", "variable", "1-byte length + UTF-8 string"),
            ("payout_network", "variable", "1-byte length + UTF-8 string"),
            ("adjusted_amount", "8 bytes", "double (ETH or USDT)"),
            ("swap_currency", "variable", "1-byte length + UTF-8 ('eth' or 'usdt')"),
            ("payout_mode", "variable", "1-byte length + UTF-8 ('instant' or 'threshold')"),
            ("actual_eth_amount", "8 bytes", "double"),
            ("timestamp", "4 bytes", "uint32"),
            ("signature", "16 bytes", "HMAC-SHA256 truncated"),
        ],
        "signing_key": "SUCCESS_URL_SIGNING_KEY",
        "expiration": "24 hours",
    },
    # ... add all other token formats
}
```

**Action**:
- [ ] Decision: Create token format registry? (Review with user first)
- [ ] If yes: Create `PGP_COMMON/tokens/token_formats.py`
- [ ] If yes: Document all token formats
- [ ] If yes: Update `PGP_COMMON/tokens/__init__.py` to export registry

---

## Part 4: Testing & Validation

### 4.1 Unit Tests for BaseTokenManager

**File to Create**: `PGP_COMMON/tests/test_base_token_manager.py`

**Tests Required**:
- [ ] Test `generate_hmac_signature()` with known inputs
- [ ] Test `verify_hmac_signature()` with valid/invalid signatures
- [ ] Test `pack_string()` with various string lengths (1 byte, 255 bytes, 256 bytes - should fail)
- [ ] Test `unpack_string()` with valid/invalid data
- [ ] Test `encode_base64_urlsafe()` and `decode_base64_urlsafe()` round-trip
- [ ] Test `get_timestamp_minutes()` returns valid 16-bit value
- [ ] Test `reconstruct_timestamp_from_minutes()` with wrap-around scenarios
- [ ] Test `pack_48bit_id()` and `unpack_48bit_id()` with positive/negative Telegram IDs

**Action**:
- [ ] Create comprehensive unit tests
- [ ] Run tests: `pytest PGP_COMMON/tests/test_base_token_manager.py -v`
- [ ] Ensure 100% coverage of BaseTokenManager methods

---

### 4.2 Integration Tests for Token Flows

**Test Scenarios**:

1. **NOWPayments → Orchestrator → Invite Flow**:
   - [ ] Generate token in PGP_ORCHESTRATOR_v1
   - [ ] Decrypt token in PGP_INVITE_v1
   - [ ] Verify all fields match

2. **SPLIT1 ↔ SPLIT2 ↔ SPLIT3 Flow**:
   - [ ] SPLIT1 encrypts estimate request → SPLIT2 decrypts
   - [ ] SPLIT2 encrypts estimate response → SPLIT1 decrypts
   - [ ] SPLIT1 encrypts swap request → SPLIT3 decrypts
   - [ ] SPLIT3 encrypts swap response → SPLIT1 decrypts

3. **Batch → MicroBatch → HostPay1 Flow**:
   - [ ] Batch encrypts token → SPLIT1 decrypts (dual-key scenario)
   - [ ] MicroBatch encrypts token → HostPay1 decrypts

4. **HostPay1 ↔ HostPay2 ↔ HostPay3 Flow**:
   - [ ] Dual-key encryption/decryption across all three services

**Action**:
- [ ] Create `TOOLS_SCRIPTS_TESTS/tests/test_token_integration.py`
- [ ] Run integration tests: `pytest TOOLS_SCRIPTS_TESTS/tests/test_token_integration.py -v`

---

### 4.3 Security Verification (MCP Tools)

**Use Google MCP & Context7 MCP to verify best practices**:

**Security Checklist**:
- [ ] **HMAC-SHA256 Implementation**: Verify signature generation follows NIST standards
- [ ] **Truncated Signatures**: Confirm 16-byte truncation is acceptable for financial apps
- [ ] **Timestamp Validation**: Ensure expiration windows are appropriate (2hr, 24hr, 30min)
- [ ] **Token Replay Prevention**: Verify timestamp + signature prevents replay attacks
- [ ] **Key Rotation Support**: Check if architecture supports key rotation without downtime
- [ ] **Constant-Time Comparison**: Ensure `hmac.compare_digest()` is used (prevents timing attacks)
- [ ] **Base64 Padding**: Verify URL-safe base64 handling is correct

**Action**:
- [ ] Use `@google` MCP to verify HMAC implementation
- [ ] Use `@context7` MCP to verify token exchange patterns
- [ ] Document security verification results in `THINK/AUTO/TOKEN_MANAGER_SECURITY_VERIFICATION.md`

---

## Part 5: Migration Execution Plan

### Phase 1: Cleanup Redundant Methods (LOW RISK)

**Tasks**:
1. [ ] Remove redundant `_pack_string` / `_unpack_string` from PGP_SPLIT3_v1
2. [ ] Remove redundant `_pack_string` / `_unpack_string` from PGP_MICROBATCHPROCESSOR_v1
3. [ ] Add missing imports to PGP_SPLIT3_v1
4. [ ] Run unit tests for affected services
5. [ ] Run integration tests for SPLIT flows

**Verification**:
- [ ] All services import successfully
- [ ] No runtime errors on token encryption/decryption
- [ ] Integration tests pass

**Rollback Plan**:
- If errors occur, revert changes to `token_manager.py` files
- Git commit before changes: `git commit -m "PRE-CLEANUP: token_manager redundancy removal"`

---

### Phase 2: Enhanced BaseTokenManager (OPTIONAL - MEDIUM RISK)

**Decision Point**: Discuss with user before proceeding

**Tasks** (if approved):
1. [ ] Add multi-key support to BaseTokenManager
2. [ ] Migrate SPLIT1 to use new multi-key pattern
3. [ ] Migrate HOSTPAY1/2/3 to use new multi-key pattern
4. [ ] Test all dual-key services
5. [ ] Create token format registry

**Verification**:
- [ ] All services initialize correctly with new pattern
- [ ] Token encryption/decryption works with both keys
- [ ] Backward compatibility maintained

**Rollback Plan**:
- Keep old `__init__` methods in service token_managers during migration
- Only remove after full verification

---

### Phase 3: Documentation & Security Audit (NO RISK)

**Tasks**:
1. [ ] Create token format registry documentation
2. [ ] Run security verification with MCP tools
3. [ ] Document all token flows in architecture diagram
4. [ ] Update PROGRESS.md with completed tasks
5. [ ] Update DECISIONS.md with architectural decisions

**Deliverables**:
- [ ] `TOKEN_MANAGER_SECURITY_VERIFICATION.md`
- [ ] `TOKEN_FORMATS_REGISTRY.md`
- [ ] Updated architecture documentation

---

## Part 6: File-by-File Change Checklist

### 6.1 PGP_SPLIT3_v1/token_manager.py

**Changes Required**:
```diff
#!/usr/bin/env python
"""
Token Manager for PGP_SPLIT3_v1
Handles encryption and decryption of tokens for secure inter-service communication via Cloud Tasks.
"""
+import base64
+import hmac
+import hashlib
+import struct
+import time
from typing import Dict, Any, Optional, Tuple
from PGP_COMMON.tokens import BaseTokenManager


class TokenManager(BaseTokenManager):
    """
    Manages token encryption and decryption for PGP_SPLIT3_v1.
    Inherits common methods from BaseTokenManager.
    """

    def __init__(self, signing_key: str):
        """
        Initialize TokenManager with signing key.

        Args:
            signing_key: SECRET key for HMAC signing (SUCCESS_URL_SIGNING_KEY)
        """
        super().__init__(signing_key, service_name="PGP_SPLIT3_v1")
-    def _pack_string(self, s: str) -> bytes:
-        """
-        Pack a string with 1-byte length prefix.
-
-        Args:
-            s: String to pack
-
-        Returns:
-            Packed bytes (1 byte length + UTF-8 encoded string)
-        """
-        s_bytes = s.encode('utf-8')
-        if len(s_bytes) > 255:
-            raise ValueError(f"String too long (max 255 bytes): {s}")
-        return bytes([len(s_bytes)]) + s_bytes
-
-    def _unpack_string(self, data: bytes, offset: int) -> Tuple[str, int]:
-        """
-        Unpack a string with 1-byte length prefix.
-
-        Args:
-            data: Byte array to unpack from
-            offset: Starting offset
-
-        Returns:
-            Tuple of (unpacked_string, new_offset)
-        """
-        length = data[offset]
-        offset += 1
-        s_bytes = data[offset:offset + length]
-        offset += length
-        return s_bytes.decode('utf-8'), offset
```

**Testing After Change**:
- [ ] Import test: `python3 -c "from PGP_SPLIT3_v1.token_manager import TokenManager"`
- [ ] Initialization test: Verify `TokenManager(signing_key)` works
- [ ] Encryption test: Test `encrypt_pgp_split3_to_pgp_split1_token()`
- [ ] Decryption test: Test `decrypt_pgp_split1_to_pgp_split3_token()`

---

### 6.2 PGP_MICROBATCHPROCESSOR_v1/token_manager.py

**Changes Required**:
```diff
class TokenManager(BaseTokenManager):
    """
    Manages token encryption for PGP_MICROBATCHPROCESSOR_v1.
    Inherits common methods from BaseTokenManager.
    """

    def __init__(self, signing_key: str):
        """
        Initialize the TokenManager.

        Args:
            signing_key: SUCCESS_URL_SIGNING_KEY for token encryption
        """
        super().__init__(signing_key=signing_key, service_name="PGP_MICROBATCHPROCESSOR_v1")

-
-    def _pack_string(self, s: str) -> bytes:
-        """Pack a string with 1-byte length prefix."""
-        s_bytes = s.encode('utf-8')
-        if len(s_bytes) > 255:
-            raise ValueError(f"String too long (max 255 bytes): {s}")
-        return bytes([len(s_bytes)]) + s_bytes
-
-    def _unpack_string(self, data: bytes, offset: int) -> Tuple[str, int]:
-        """Unpack a string with 1-byte length prefix."""
-        length = data[offset]
-        offset += 1
-        s_bytes = data[offset:offset + length]
-        offset += length
-        return s_bytes.decode('utf-8'), offset
```

**Testing After Change**:
- [ ] Import test: `python3 -c "from PGP_MICROBATCHPROCESSOR_v1.token_manager import TokenManager"`
- [ ] Initialization test: Verify `TokenManager(signing_key)` works
- [ ] Encryption test: Test `encrypt_microbatch_to_pgp_hostpay1_token()`
- [ ] Decryption test: Test `decrypt_pgp_hostpay1_to_microbatch_token()`

---

## Part 7: Success Criteria

### 7.1 Code Reduction Metrics

**Before Cleanup**:
- Total lines across all token_manager.py files: ~3,500 lines
- Duplicated helper methods: 2 services × 20 lines = 40 lines

**After Cleanup**:
- Expected reduction: ~40 lines (redundant methods removed)
- Import standardization: All files use consistent imports

**Measurement**:
- [ ] Run line count: `wc -l PGP_*/token_manager.py`
- [ ] Document before/after in PROGRESS.md

---

### 7.2 Functionality Verification

**All token flows must continue working**:
- [ ] NOWPayments → Orchestrator → Invite flow
- [ ] SPLIT1 ↔ SPLIT2 ↔ SPLIT3 flows
- [ ] Batch → MicroBatch → HostPay1 flow
- [ ] Accumulator → SPLIT3 flow
- [ ] HostPay1 ↔ HostPay2 ↔ HostPay3 flows

**No regressions**:
- [ ] All existing tests pass
- [ ] No new errors in logs
- [ ] Token validation success rate unchanged

---

### 7.3 Security Compliance

**Verified by MCP tools**:
- [ ] HMAC implementation meets financial app standards (Google MCP)
- [ ] Token exchange patterns follow best practices (Context7 MCP)
- [ ] No security vulnerabilities introduced

**Documentation**:
- [ ] Security verification report created
- [ ] All findings documented in DECISIONS.md

---

## Part 8: Rollback Plan

### 8.1 Git Workflow

**Before ANY changes**:
```bash
# Create backup branch
git checkout -b backup-token-manager-pre-cleanup

# Commit current state
git add .
git commit -m "BACKUP: Pre token_manager cleanup state"

# Create working branch
git checkout -b token-manager-cleanup

# Make changes incrementally with commits
git add PGP_SPLIT3_v1/token_manager.py
git commit -m "Remove redundant _pack_string/_unpack_string from PGP_SPLIT3_v1"

git add PGP_MICROBATCHPROCESSOR_v1/token_manager.py
git commit -m "Remove redundant _pack_string/_unpack_string from PGP_MICROBATCHPROCESSOR_v1"

# Test after each commit
# If tests fail, revert that specific commit
```

**Rollback Procedure**:
```bash
# If issues found after deployment
git checkout backup-token-manager-pre-cleanup

# Or revert specific commits
git revert <commit-hash>
```

---

### 8.2 Testing Before Merge

**Required passing tests**:
- [ ] All unit tests pass: `pytest PGP_COMMON/tests/ -v`
- [ ] All integration tests pass: `pytest TOOLS_SCRIPTS_TESTS/tests/ -v`
- [ ] No import errors in any service
- [ ] Manual verification of at least one token flow per service type

**Only merge if ALL tests pass**:
```bash
git checkout PGP_v1
git merge token-manager-cleanup
```

---

## Part 9: Next Steps & Dependencies

### 9.1 Immediate Next Steps (Low-Hanging Fruit)

**Can be done immediately without risk**:
1. [ ] Remove redundant methods from PGP_SPLIT3_v1 and PGP_MICROBATCHPROCESSOR_v1
2. [ ] Add missing imports to PGP_SPLIT3_v1
3. [ ] Create unit tests for BaseTokenManager
4. [ ] Run security verification with MCP tools

**Estimated Time**: 2-4 hours
**Risk Level**: LOW

---

### 9.2 Optional Enhancements (Requires Discussion)

**Discuss with user before proceeding**:
1. [ ] Multi-key support in BaseTokenManager
2. [ ] Token format registry creation
3. [ ] Additional helper methods in BaseTokenManager

**Estimated Time**: 4-8 hours
**Risk Level**: MEDIUM

---

### 9.3 Dependencies

**Before starting this work**:
- [ ] Ensure `.venv` environment is active
- [ ] Ensure all services are currently functional
- [ ] Ensure SECRET_SCHEME.md and NAMING_SCHEME.md are up to date
- [ ] Check that no other major refactoring is in progress

**After completing this work**:
- [ ] Update PROGRESS.md with changes made
- [ ] Update DECISIONS.md with architectural decisions
- [ ] Update BUGS.md if any issues found and fixed
- [ ] Consider archiving this checklist to ARCHIVES_PGP_v1/11-18_PGP_v1/

---

## Part 10: Security Best Practices Verification

### 10.1 HMAC Implementation Review

**Check against OWASP standards**:
- [ ] Using HMAC-SHA256 (recommended for financial apps) ✅
- [ ] Using `hmac.compare_digest()` (prevents timing attacks) ✅
- [ ] Truncating to 16 bytes (acceptable for 128-bit security level) ✅
- [ ] Using secrets from Google Secret Manager (not hardcoded) ✅

**Verify with Google MCP**:
```
Query: "Is HMAC-SHA256 with 16-byte truncation secure for financial application token signatures? What are the security implications?"
```
- [ ] MCP response documented
- [ ] Any concerns addressed

---

### 10.2 Token Expiration Windows

**Current expiration policies**:
- NOWPayments tokens: 2 hours
- SPLIT flow tokens: 24 hours
- MicroBatch tokens: 30 minutes
- Batch tokens: 24 hours

**Verify with Context7 MCP**:
```
Query: "What are best practices for token expiration windows in financial payment processing systems? Are 2-hour and 24-hour windows appropriate?"
```
- [ ] MCP response documented
- [ ] Expiration windows adjusted if needed

---

### 10.3 Key Management

**Current key usage**:
- `SUCCESS_URL_SIGNING_KEY`: NOWPayments integration
- `TPS_HOSTPAY_SIGNING_KEY`: Batch processing
- `PGP_INTERNAL_SIGNING_KEY`: Internal service communication

**Verify**:
- [ ] All keys stored in Google Secret Manager ✅
- [ ] Keys are different for different purposes ✅
- [ ] Key rotation procedure documented
- [ ] No keys hardcoded in source code ✅

---

## Summary

**Total Services with token_manager.py**: 11
**Services requiring changes**: 2 (PGP_SPLIT3_v1, PGP_MICROBATCHPROCESSOR_v1)
**Lines of code to remove**: ~40 lines
**Risk level**: LOW (only removing duplicated code that's already in BaseTokenManager)
**Estimated time**: 2-4 hours for Phase 1, additional 4-8 hours for Phase 2 (optional)

**Success means**:
- ✅ Reduced code duplication
- ✅ All services still function correctly
- ✅ No security regressions
- ✅ Improved maintainability
- ✅ Better code organization

**Next Action**: Review this checklist with user and get approval to proceed with Phase 1.
