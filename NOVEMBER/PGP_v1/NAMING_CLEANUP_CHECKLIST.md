# Naming Cleanup Checklist - Phase 2.6
## Update All Comments, Print Statements, and Documentation

**Objective:** Replace ALL old naming conventions (GC*, 10-26 suffixes) with new PGP_v1 naming in comments, print statements, error messages, docstrings, and documentation.

**Scope:** 3626+ occurrences across all Python files, Dockerfiles, and Markdown files

---

## Naming Transformation Map

### Service-Level Naming
| Old Service Name | New Service Name | Old Main File | New Main File |
|------------------|------------------|---------------|---------------|
| PGP_ACCUMULATOR_v1 | PGP_ACCUMULATOR_v1 | pgp_accumulator_v1.py | pgp_accumulator_v1.py |
| PGP_BATCHPROCESSOR_v1 | PGP_BATCHPROCESSOR_v1 | pgp_batchprocessor_v1.py | pgp_batchprocessor_v1.py |
| PGP_WEB_v1 | PGP_WEB_v1 | (static) | (static) |
| PGP_WEBAPI_v1 | PGP_WEBAPI_v1 | app.py | pgp_webapi_v1.py |
| PGP_NP_IPN_v1 | PGP_NP_IPN_v1 | app.py | pgp_np_ipn_v1.py |
| PGP_NOTIFICATIONS_v1 | PGP_NOTIFICATIONS_v1 | pgp_notifications_v1.py | pgp_notifications_v1.py |
| PGP_MICROBATCHPROCESSOR_v1 | PGP_MICROBATCHPROCESSOR_v1 | micropgp_batchprocessor_v1.py | pgp_microbatchprocessor_v1.py |
| PGP_INVITE_v1 | PGP_INVITE_v1 | pgp_invite_v1.py | pgp_invite_v1.py |
| PGP_ORCHESTRATOR_v1 | PGP_ORCHESTRATOR_v1 | pgp_orchestrator_v1.py | pgp_orchestrator_v1.py |
| PGP_BROADCAST_v1 | PGP_BROADCAST_v1 | pgp_broadcast_v1.py | pgp_broadcast_v1.py |
| PGP_SPLIT3_v1 | PGP_SPLIT3_v1 | pgp_split3_v1.py | pgp_split3_v1.py |
| PGP_SPLIT2_v1 | PGP_SPLIT2_v1 | pgp_split2_v1.py | pgp_split2_v1.py |
| PGP_SPLIT1_v1 | PGP_SPLIT1_v1 | pgp_split1_v1.py | pgp_split1_v1.py |
| PGP_HOSTPAY3_v1 | PGP_HOSTPAY3_v1 | pgp_hostpay3_v1.py | pgp_hostpay3_v1.py |
| PGP_HOSTPAY2_v1 | PGP_HOSTPAY2_v1 | pgp_hostpay2_v1.py | pgp_hostpay2_v1.py |
| PGP_HOSTPAY1_v1 | PGP_HOSTPAY1_v1 | pgp_hostpay1_v1.py | pgp_hostpay1_v1.py |
| PGP_SERVER_v1 | PGP_SERVER_v1 | pgp_server_v1.py | pgp_server_v1.py |

### Shortened Naming Variants
| Old Short Name | New Short Name | Context |
|----------------|----------------|---------|
| pgp_accumulator | pgp_accumulator | Logs, comments |
| pgp_batch | pgp_batch | Logs, comments |
| pgp_notification | pgp_notification | Logs, comments |
| pgp_microbatch | pgp_microbatch | Logs, comments |
| gcwebhook1 | pgp_orchestrator | Logs, queue names |
| gcwebhook2 | pgp_invite | Logs, queue names |
| gcsplit1 | pgp_split1 | Logs, queue names |
| gcsplit2 | pgp_split2 | Logs, queue names |
| gcsplit3 | pgp_split3 | Logs, queue names |
| gchostpay1 | pgp_hostpay1 | Logs, queue names |
| gchostpay2 | pgp_hostpay2 | Logs, queue names |
| gchostpay3 | pgp_hostpay3 | Logs, queue names |
| pgp_server | pgp_server | Logs, comments |

---

## Systematic Replacement Strategy

### Phase 1: Automated Text Replacement Script
**Script:** `phase_2_6_naming_cleanup.py`

**Replacement Rules (order matters - longest patterns first):**

1. **Service Names (with hyphen and version)**
   - `PGP_ACCUMULATOR_v1` → `PGP_ACCUMULATOR_v1`
   - `PGP_BATCHPROCESSOR_v1` → `PGP_BATCHPROCESSOR_v1`
   - `PGP_WEB_v1` → `PGP_WEB_v1`
   - `PGP_WEBAPI_v1` → `PGP_WEBAPI_v1`
   - `PGP_NP_IPN_v1` → `PGP_NP_IPN_v1`
   - `PGP_NOTIFICATIONS_v1` → `PGP_NOTIFICATIONS_v1`
   - `PGP_MICROBATCHPROCESSOR_v1` → `PGP_MICROBATCHPROCESSOR_v1`
   - `PGP_INVITE_v1` → `PGP_INVITE_v1`
   - `PGP_ORCHESTRATOR_v1` → `PGP_ORCHESTRATOR_v1`
   - `PGP_BROADCAST_v1` → `PGP_BROADCAST_v1`
   - `PGP_SPLIT3_v1` → `PGP_SPLIT3_v1`
   - `PGP_SPLIT2_v1` → `PGP_SPLIT2_v1`
   - `PGP_SPLIT1_v1` → `PGP_SPLIT1_v1`
   - `PGP_HOSTPAY3_v1` → `PGP_HOSTPAY3_v1`
   - `PGP_HOSTPAY2_v1` → `PGP_HOSTPAY2_v1`
   - `PGP_HOSTPAY1_v1` → `PGP_HOSTPAY1_v1`
   - `PGP_SERVER_v1` → `PGP_SERVER_v1`

2. **File Names (old main files)**
   - `pgp_accumulator_v1.py` → `pgp_accumulator_v1.py`
   - `pgp_batchprocessor_v1.py` → `pgp_batchprocessor_v1.py`
   - `micropgp_batchprocessor_v1.py` → `pgp_microbatchprocessor_v1.py`
   - `pgp_invite_v1.py` → `pgp_invite_v1.py`
   - `pgp_orchestrator_v1.py` → `pgp_orchestrator_v1.py`
   - `pgp_split3_v1.py` → `pgp_split3_v1.py`
   - `pgp_split2_v1.py` → `pgp_split2_v1.py`
   - `pgp_split1_v1.py` → `pgp_split1_v1.py`
   - `pgp_hostpay3_v1.py` → `pgp_hostpay3_v1.py`
   - `pgp_hostpay2_v1.py` → `pgp_hostpay2_v1.py`
   - `pgp_hostpay1_v1.py` → `pgp_hostpay1_v1.py`
   - `pgp_server_v1.py` → `pgp_server_v1.py`

3. **Shortened Service Names (lowercase, in comments/logs)**
   - `pgp_accumulator` → `pgp_accumulator`
   - `pgp_batch` → `pgp_batch`
   - `pgp_notification` → `pgp_notification`
   - `pgp_microbatch` → `pgp_microbatch`
   - `gcwebhook1` → `pgp_orchestrator`
   - `gcwebhook2` → `pgp_invite`
   - `gcsplit1` → `pgp_split1`
   - `gcsplit2` → `pgp_split2`
   - `gcsplit3` → `pgp_split3`
   - `gchostpay1` → `pgp_hostpay1`
   - `gchostpay2` → `pgp_hostpay2`
   - `gchostpay3` → `pgp_hostpay3`
   - `pgp_server` → `pgp_server`

4. **Service Names Without Suffix (for flexibility)**
   - `PGP_ACCUMULATOR` → `PGP_ACCUMULATOR`
   - `PGP_BATCHPROCESSOR` → `PGP_BATCHPROCESSOR`
   - `PGP_WEB` → `PGP_WEB`
   - `PGP_WEBAPI` → `PGP_WEBAPI`
   - `PGP_NOTIFICATIONS` → `PGP_NOTIFICATIONS`
   - `PGP_MICROBATCHPROCESSOR` → `PGP_MICROBATCHPROCESSOR`
   - `PGP_INVITE_v1` → `PGP_INVITE`
   - `PGP_ORCHESTRATOR_v1` → `PGP_ORCHESTRATOR`
   - `PGP_BROADCAST` → `PGP_BROADCAST`
   - `PGP_SPLIT3_v1` → `PGP_SPLIT3`
   - `PGP_SPLIT2_v1` → `PGP_SPLIT2`
   - `PGP_SPLIT1_v1` → `PGP_SPLIT1`
   - `PGP_HOSTPAY3_v1` → `PGP_HOSTPAY3`
   - `PGP_HOSTPAY2_v1` → `PGP_HOSTPAY2`
   - `PGP_HOSTPAY1_v1` → `PGP_HOSTPAY1`
   - `TelePay` → `PGP_SERVER`

5. **Date Suffix Removal (standalone)**
   - `10-26` → `v1` (only in specific contexts like version references)

---

## File Types to Process

### 1. Python Files (*.py)
**Target Locations:**
- Comments (`#` lines)
- Docstrings (`"""` blocks)
- Print statements (`print(...)`)
- Logging statements (`logger.info(...)`, `logger.error(...)`, etc.)
- Exception messages (`raise Exception("...")`)
- String literals in error handling
- Module-level documentation

**Example Transformations:**
```python
# Before
# PGP_ACCUMULATOR_v1: Accumulates payments for batch processing
print("🚀 Starting PGP_ACCUMULATOR_v1 service...")
logger.info("[PGP_ACCUMULATOR] Processing batch...")

# After
# PGP_ACCUMULATOR_v1: Accumulates payments for batch processing
print("🚀 Starting PGP_ACCUMULATOR_v1 service...")
logger.info("[PGP_ACCUMULATOR] Processing batch...")
```

### 2. Dockerfiles
**Target Locations:**
- Comment lines
- File references in COPY/ADD commands
- CMD/ENTRYPOINT commands
- Labels and metadata

**Example Transformations:**
```dockerfile
# Before
# PGP_ACCUMULATOR_v1 Dockerfile
COPY pgp_accumulator_v1.py .
CMD ["python", "pgp_accumulator_v1.py"]

# After
# PGP_ACCUMULATOR_v1 Dockerfile
COPY pgp_accumulator_v1.py .
CMD ["python", "pgp_accumulator_v1.py"]
```

### 3. Markdown Files (*.md)
**Target Locations:**
- Documentation text
- Code examples
- Service references
- Table entries
- Headers and titles

**Example Transformations:**
```markdown
# Before
## PGP_ACCUMULATOR_v1 Service
Deploys the `pgp_accumulator_v1.py` accumulator service.

# After
## PGP_ACCUMULATOR_v1 Service
Deploys the `pgp_accumulator_v1.py` accumulator service.
```

### 4. Shell Scripts (*.sh)
**Target Locations:**
- Comments
- Echo statements
- Variable names (if relevant)
- Service name references

---

## Exclusions

**DO NOT MODIFY:**
1. PGP_COMMON directory (already uses correct naming)
2. Environment variable values in deployment scripts (unless they contain old names)
3. Secret Manager secret names (unless they need updating - check separately)
4. Git history or commit messages
5. URLs or external references that might break
6. Binary files or images

---

## Implementation Checklist

### Step 1: Create Automated Script
- [x] Define comprehensive replacement mapping
- [ ] Create `phase_2_6_naming_cleanup.py` script
- [ ] Include safety checks (dry-run mode)
- [ ] Add file-by-file processing with logging
- [ ] Include verification step

### Step 2: Run Script (Dry-Run Mode First)
- [ ] Run dry-run to see what would change
- [ ] Review sample changes for correctness
- [ ] Check for any unintended replacements
- [ ] Verify edge cases (e.g., "PGP_ORCHESTRATOR_v1" vs "PGP_INVITE_v1")

### Step 3: Execute Actual Replacements
- [ ] Run script on Python files (*.py)
- [ ] Run script on Dockerfiles
- [ ] Run script on Markdown files (*.md)
- [ ] Run script on Shell scripts (*.sh)

### Step 4: Service-Specific Verification
- [ ] PGP_ACCUMULATOR_v1 - Verify all references updated
- [ ] PGP_BATCHPROCESSOR_v1 - Verify all references updated
- [ ] PGP_WEB_v1 - Verify all references updated
- [ ] PGP_WEBAPI_v1 - Verify all references updated
- [ ] PGP_NP_IPN_v1 - Verify all references updated
- [ ] PGP_NOTIFICATIONS_v1 - Verify all references updated
- [ ] PGP_MICROBATCHPROCESSOR_v1 - Verify all references updated
- [ ] PGP_INVITE_v1 - Verify all references updated
- [ ] PGP_ORCHESTRATOR_v1 - Verify all references updated
- [ ] PGP_BROADCAST_v1 - Verify all references updated
- [ ] PGP_SPLIT3_v1 - Verify all references updated
- [ ] PGP_SPLIT2_v1 - Verify all references updated
- [ ] PGP_SPLIT1_v1 - Verify all references updated
- [ ] PGP_HOSTPAY3_v1 - Verify all references updated
- [ ] PGP_HOSTPAY2_v1 - Verify all references updated
- [ ] PGP_HOSTPAY1_v1 - Verify all references updated
- [ ] PGP_SERVER_v1 - Verify all references updated

### Step 5: Final Verification
- [ ] Search for remaining old patterns: `grep -r "PGP_ACCUMULATOR\|GCBatch" ...`
- [ ] Search for date suffixes: `grep -r "10-26" ...`
- [ ] Check Dockerfiles specifically
- [ ] Check all print/logging statements
- [ ] Check all comments and docstrings

### Step 6: Testing
- [ ] Verify syntax of all modified Python files (`python -m py_compile`)
- [ ] Check Dockerfile syntax
- [ ] Run quick sanity tests on modified services
- [ ] Check that no functionality was broken

### Step 7: Commit Changes
- [ ] Review all changes with `git diff`
- [ ] Commit with detailed message
- [ ] Push to remote branch

---

## Expected Changes Summary

**Estimated Files to Modify:**
- ~170 Python files
- ~17 Dockerfiles
- ~30 Markdown files
- ~15 Shell scripts

**Estimated Total Changes:** 3600+ text replacements

**Risk Level:** Low (text-only changes, no code logic modified)

**Verification Method:** Automated grep search for old patterns

---

## Safety Measures

1. **Backup:** All changes made on branch `claude/pgp_server-refactor-access-check-01VoFVjrTXfd97mAZWvaFTYm`
2. **Dry-Run:** Always run dry-run mode first
3. **Verification:** Automated verification after each phase
4. **Rollback:** Git reset available if issues found
5. **Testing:** Syntax checking before commit

---

## Success Criteria

✅ **Phase 2.6 Complete When:**
1. Zero occurrences of old service names (PGP_ACCUMULATOR_v1, etc.)
2. Zero occurrences of old file names (pgp_accumulator_v1.py, etc.)
3. All comments use new naming (PGP_ACCUMULATOR_v1, etc.)
4. All print/log statements use new naming
5. All Dockerfiles reference correct file names
6. All documentation updated
7. No syntax errors introduced
8. All changes committed and pushed

---

**Status:** Ready to begin
**Next Action:** Create and execute `phase_2_6_naming_cleanup.py` script
