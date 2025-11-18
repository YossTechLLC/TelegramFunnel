# Phase 2.5: Function Name Renaming Plan

## Overview
Update all function names in `cloudtasks_client.py` and `token_manager.py` files to use new PGP_v1 naming scheme.

## Problem
Function names still use old naming conventions:
- `enqueue_gcwebhook1_*` → should be `enqueue_pgp_orchestrator_*`
- `enqueue_gcwebhook2_*` → should be `enqueue_pgp_invite_*`
- `enqueue_gcsplit1_*` → should be `enqueue_pgp_split1_*`
- `enqueue_gcsplit2_*` → should be `enqueue_pgp_split2_*`
- `enqueue_gcsplit3_*` → should be `enqueue_pgp_split3_*`
- `enqueue_gchostpay1_*` → should be `enqueue_pgp_hostpay1_*`
- `enqueue_gchostpay2_*` → should be `enqueue_pgp_hostpay2_*`
- `enqueue_gchostpay3_*` → should be `enqueue_pgp_hostpay3_*`

## Function Name Mapping

### PGP_ORCHESTRATOR_v1
- `enqueue_gcwebhook2_telegram_invite` → `enqueue_pgp_invite_telegram_invite`
- `enqueue_gcsplit1_payment_split` → `enqueue_pgp_split1_payment_split`

### PGP_INVITE_v1
(No cloudtasks_client.py - uses direct HTTP/bot API)

### PGP_SPLIT1_v1
- `enqueue_gcsplit2_estimate_request` → `enqueue_pgp_split2_estimate_request`
- `enqueue_gcsplit1_estimate_response` → `enqueue_pgp_split1_estimate_response`
- `enqueue_gcsplit3_swap_request` → `enqueue_pgp_split3_swap_request`
- `enqueue_gcsplit1_swap_response` → `enqueue_pgp_split1_swap_response`
- `enqueue_hostpay_trigger` → `enqueue_pgp_hostpay_trigger`

### PGP_SPLIT2_v1
- `enqueue_gcsplit1_estimate_response` → `enqueue_pgp_split1_estimate_response`

### PGP_SPLIT3_v1
- `enqueue_gcsplit2_estimate_request` → `enqueue_pgp_split2_estimate_request`
- `enqueue_gcsplit1_estimate_response` → `enqueue_pgp_split1_estimate_response`
- `enqueue_gcsplit3_swap_request` → `enqueue_pgp_split3_swap_request`
- `enqueue_gcsplit1_swap_response` → `enqueue_pgp_split1_swap_response`
- `enqueue_hostpay_trigger` → `enqueue_pgp_hostpay_trigger`

### PGP_HOSTPAY1_v1
- `enqueue_gchostpay2_status_check` → `enqueue_pgp_hostpay2_status_check`
- `enqueue_gchostpay3_payment_execution` → `enqueue_pgp_hostpay3_payment_execution`
- `enqueue_gchostpay1_status_response` → `enqueue_pgp_hostpay1_status_response`
- `enqueue_gchostpay1_payment_response` → `enqueue_pgp_hostpay1_payment_response`
- `enqueue_gchostpay1_retry_callback` → `enqueue_pgp_hostpay1_retry_callback`

### PGP_HOSTPAY2_v1
- `enqueue_gchostpay2_status_check` → `enqueue_pgp_hostpay2_status_check`
- `enqueue_gchostpay3_payment_execution` → `enqueue_pgp_hostpay3_payment_execution`
- `enqueue_gchostpay1_status_response` → `enqueue_pgp_hostpay1_status_response`
- `enqueue_gchostpay1_payment_response` → `enqueue_pgp_hostpay1_payment_response`

### PGP_HOSTPAY3_v1
- `enqueue_gchostpay2_status_check` → `enqueue_pgp_hostpay2_status_check`
- `enqueue_gchostpay3_payment_execution` → `enqueue_pgp_hostpay3_payment_execution`
- `enqueue_gchostpay1_status_response` → `enqueue_pgp_hostpay1_status_response`
- `enqueue_gchostpay1_payment_response` → `enqueue_pgp_hostpay1_payment_response`
- `enqueue_gchostpay3_retry` → `enqueue_pgp_hostpay3_retry`

### PGP_ACCUMULATOR_v1
- `enqueue_gcsplit2_conversion` → `enqueue_pgp_split2_conversion`
- `enqueue_gcsplit3_eth_to_usdt_swap` → `enqueue_pgp_split3_eth_to_usdt_swap`
- `enqueue_gchostpay1_execution` → `enqueue_pgp_hostpay1_execution`

### PGP_MICROBATCHPROCESSOR_v1
- `enqueue_gchostpay1_batch_execution` → `enqueue_pgp_hostpay1_batch_execution`

### PGP_NP_IPN_v1
- `enqueue_gcwebhook1_validated_payment` → `enqueue_pgp_orchestrator_validated_payment`

## Implementation Strategy

### Step 1: Update cloudtasks_client.py function definitions
For each service's cloudtasks_client.py:
1. Update function names (def statements)
2. Update docstrings that reference function names
3. Update any internal references

### Step 2: Update function calls across all services
Search for and update all function calls in:
- Main service files (*.py)
- Helper files
- Any other Python modules that call these functions

### Step 3: Update token_manager.py if needed
Check for similar naming issues in token generation functions

## Files Requiring Updates

### cloudtasks_client.py (11 files)
- [ ] PGP_ORCHESTRATOR_v1/cloudtasks_client.py
- [ ] PGP_SPLIT1_v1/cloudtasks_client.py
- [ ] PGP_SPLIT2_v1/cloudtasks_client.py
- [ ] PGP_SPLIT3_v1/cloudtasks_client.py
- [ ] PGP_HOSTPAY1_v1/cloudtasks_client.py
- [ ] PGP_HOSTPAY2_v1/cloudtasks_client.py
- [ ] PGP_HOSTPAY3_v1/cloudtasks_client.py
- [ ] PGP_ACCUMULATOR_v1/cloudtasks_client.py
- [ ] PGP_BATCHPROCESSOR_v1/cloudtasks_client.py (if exists)
- [ ] PGP_MICROBATCHPROCESSOR_v1/cloudtasks_client.py
- [ ] PGP_NP_IPN_v1/cloudtasks_client.py

### Main service files (need to find all function calls)
- [ ] PGP_ORCHESTRATOR_v1/*.py
- [ ] PGP_SPLIT1_v1/*.py
- [ ] PGP_SPLIT2_v1/*.py
- [ ] PGP_SPLIT3_v1/*.py
- [ ] PGP_HOSTPAY1_v1/*.py
- [ ] PGP_HOSTPAY2_v1/*.py
- [ ] PGP_HOSTPAY3_v1/*.py
- [ ] PGP_ACCUMULATOR_v1/*.py
- [ ] PGP_BATCHPROCESSOR_v1/*.py
- [ ] PGP_MICROBATCHPROCESSOR_v1/*.py
- [ ] PGP_NP_IPN_v1/*.py

## Search Pattern for Function Calls

```bash
# Find all calls to old function names
grep -r "enqueue_gcwebhook[12]_" --include="*.py"
grep -r "enqueue_gcsplit[123]_" --include="*.py"
grep -r "enqueue_gchostpay[123]_" --include="*.py"
```

## Validation

After updates:
1. ✅ No references to `gcwebhook1`, `gcwebhook2` in function names
2. ✅ No references to `gcsplit1/2/3` in function names
3. ✅ No references to `gchostpay1/2/3` in function names
4. ✅ All function definitions match their calling locations
5. ✅ All docstrings updated

## Status

**NOT STARTED** - Waiting for user approval to proceed with Phase 2.5
