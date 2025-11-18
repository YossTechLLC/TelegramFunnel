# Phase 2: Python Code Update Plan

## Overview
Update all Python config_manager.py files to reference new PGP_v1 secret names.

## Files Requiring Updates

### 1. PGP_ORCHESTRATOR_v1/config_manager.py
**Lines to Update:**
- Line 73-76: `GCWEBHOOK2_QUEUE` → `PGP_INVITE_QUEUE`
- Line 78-81: `GCWEBHOOK2_URL` → `PGP_INVITE_URL`
- Line 83-86: `GCSPLIT1_QUEUE` → `PGP_SPLIT1_QUEUE`
- Line 88-91: `GCSPLIT1_URL` → `PGP_SPLIT1_URL`
- Line 94-97: `GCACCUMULATOR_QUEUE` → `PGP_ACCUMULATOR_QUEUE`
- Line 99-102: `GCACCUMULATOR_URL` → `PGP_ACCUMULATOR_URL`
- Update all variable names in config dict (lines 138-143)
- Update all log messages (lines 157-162)

### 2. PGP_SPLIT1_v1/config_manager.py
**Lines to Update:**
- Line 111-114: `GCSPLIT2_QUEUE` → `PGP_SPLIT2_ESTIMATE_QUEUE`
- Line 116-119: `GCSPLIT2_URL` → `PGP_SPLIT2_URL`
- Line 121-124: `GCSPLIT3_QUEUE` → `PGP_SPLIT3_SWAP_QUEUE`
- Line 126-129: `GCSPLIT3_URL` → `PGP_SPLIT3_URL`
- Line 131-134: `HOSTPAY_QUEUE` → `PGP_HOSTPAY_TRIGGER_QUEUE`
- Update config dict (lines 175-179)
- Update log messages (lines 196-200)

### 3. PGP_HOSTPAY1_v1/config_manager.py
**Lines to Update:**
- Line 79-82: `GCHOSTPAY2_QUEUE` → `PGP_HOSTPAY2_STATUS_QUEUE`
- Line 84-87: `GCHOSTPAY2_URL` → `PGP_HOSTPAY2_URL`
- Line 90-93: `GCHOSTPAY3_QUEUE` → `PGP_HOSTPAY3_PAYMENT_QUEUE`
- Line 95-98: `GCHOSTPAY3_URL` → `PGP_HOSTPAY3_URL`
- Line 101-104: `GCHOSTPAY1_URL` → `PGP_HOSTPAY1_URL`
- Line 106-109: `GCHOSTPAY1_RESPONSE_QUEUE` → `PGP_HOSTPAY1_RESPONSE_QUEUE`
- Line 118-121: `MICROBATCH_RESPONSE_QUEUE` → `PGP_MICROBATCH_RESPONSE_QUEUE`
- Line 123-126: `MICROBATCH_URL` → `PGP_MICROBATCH_URL`
- Update config dict (lines 166-173)
- Update log messages (lines 189-196)

### 4. PGP_HOSTPAY2_v1/config_manager.py
**Similar pattern - update:**
- `GCHOSTPAY1_URL` → `PGP_HOSTPAY1_URL`
- `GCHOSTPAY1_RESPONSE_QUEUE` → `PGP_HOSTPAY1_RESPONSE_QUEUE`

### 5. PGP_HOSTPAY3_v1/config_manager.py
**Similar pattern - update:**
- `GCHOSTPAY1_URL` → `PGP_HOSTPAY1_URL`
- `GCHOSTPAY1_RESPONSE_QUEUE` → `PGP_HOSTPAY1_RESPONSE_QUEUE`

### 6. PGP_SPLIT2_v1/config_manager.py
**Update:**
- Response queue/URL references
- Split3 references

### 7. PGP_SPLIT3_v1/config_manager.py
**Update:**
- HostPay references

### 8. PGP_ACCUMULATOR_v1/config_manager.py
**Update:**
- `GCSPLIT1_BATCH_QUEUE` → `PGP_BATCHPROCESSOR_QUEUE`

### 9. PGP_BATCHPROCESSOR_v1/config_manager.py
**Update:**
- `GCSPLIT1_BATCH_QUEUE` → `PGP_BATCHPROCESSOR_QUEUE`

### 10. PGP_MICROBATCHPROCESSOR_v1/config_manager.py
**Update:**
- HostPay references

### 11. PGP_NP_IPN_v1/pgp_np_ipn_v1.py
**Update:**
- `GCWEBHOOK1_QUEUE` → `PGP_ORCHESTRATOR_QUEUE`
- `GCWEBHOOK1_URL` → `PGP_ORCHESTRATOR_URL`
- `GCWEBHOOK2_QUEUE` → `PGP_INVITE_QUEUE`
- `GCWEBHOOK2_URL` → `PGP_INVITE_URL`
- `TELEPAY_BOT_URL` → `PGP_SERVER_URL`

## Validation Steps

After each file update:
1. ✅ Check syntax (no Python errors)
2. ✅ Verify all secret names updated
3. ✅ Verify all variable names in config dict updated
4. ✅ Verify all log messages updated
5. ✅ Verify description strings updated

## Testing Strategy

1. Update files in dependency order (foundational → dependent)
2. Validate each file after update
3. Create test script to verify all secret names are consistent
4. Compare against SECRET_NAME_MAPPING.md

## Automation Script

A Python script can automate this using regex:
```python
import re

# Map old names to new names
SECRET_MAPPING = {
    'GCWEBHOOK1_QUEUE': 'PGP_ORCHESTRATOR_QUEUE',
    'GCWEBHOOK1_URL': 'PGP_ORCHESTRATOR_URL',
    'GCWEBHOOK2_QUEUE': 'PGP_INVITE_QUEUE',
    'GCWEBHOOK2_URL': 'PGP_INVITE_URL',
    'GCSPLIT1_QUEUE': 'PGP_SPLIT1_QUEUE',
    'GCSPLIT1_URL': 'PGP_SPLIT1_URL',
    # ... etc
}

# Update all fetch_secret() calls
# Update all config dict keys
# Update all log messages
```

## Status

- [x] PGP_ORCHESTRATOR_v1/config_manager.py ✅
- [x] PGP_INVITE_v1/config_manager.py ✅
- [x] PGP_SPLIT1_v1/config_manager.py ✅
- [x] PGP_SPLIT2_v1/config_manager.py ✅
- [x] PGP_SPLIT3_v1/config_manager.py ✅
- [x] PGP_HOSTPAY1_v1/config_manager.py ✅
- [x] PGP_HOSTPAY2_v1/config_manager.py ✅
- [x] PGP_HOSTPAY3_v1/config_manager.py ✅
- [x] PGP_ACCUMULATOR_v1/config_manager.py ✅
- [x] PGP_BATCHPROCESSOR_v1/config_manager.py ✅
- [x] PGP_MICROBATCHPROCESSOR_v1/config_manager.py ✅
- [x] PGP_NP_IPN_v1/pgp_np_ipn_v1.py ✅

**Phase 2 COMPLETE** - All 13 files updated (12 config_manager.py + 1 main service file)

## Next: Create Automated Update Script

Due to the large number of files and repetitive nature, an automated script is recommended.
