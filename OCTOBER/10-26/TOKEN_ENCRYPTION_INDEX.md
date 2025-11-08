# Token Encryption Architecture - Documentation Index

**Created:** 2025-11-08  
**Status:** Complete and Ready for Review  
**Total Documentation:** 1,403 lines across 3 files  

---

## Documentation Files

### 1. TOKEN_ENCRYPTION_MAP.md (762 lines, 28KB)
**Comprehensive detailed analysis** - Start here for deep understanding

**Contents:**
- Service-by-service breakdown (13 services analyzed)
  - Main file identification
  - Endpoint specifications
  - Token usage per endpoint
  - Complete token flow diagrams
  - Signing key requirements
- Token data payloads (4 formats documented)
  - Binary structure specifications
  - Encoding/decoding details
  - Field-by-field breakdown
- Service dependency graph with all connections
- Two-key security boundary architecture
- Critical security notes and token handling
- Maintenance checklist and testing examples

**Best for:** Complete understanding, implementation details, security review

### 2. TOKEN_ENCRYPTION_QUICK_REFERENCE.md (216 lines, 8.2KB)
**Quick lookup guide** - Use for quick answers

**Contents:**
- Service encryption status matrix (all 13 services at a glance)
- Summary statistics and counts
- Decrypt endpoints listing (8 services)
- Encrypt endpoints listing (9 services)
- No-token services explanation (3 services)
- Signing key distribution by service
- Token format comparison table
- Token expiration windows
- Service request/response patterns

**Best for:** Quick lookup, reference during meetings, status checks

### 3. TOKEN_ENCRYPTION_SUMMARY.txt (425 lines, 17KB)
**Executive overview** - Start here for high-level understanding

**Contents:**
- Quick statistics (total counts and breakdowns)
- Service descriptions (name, file, endpoints, keys)
- Services with tokens (9 detailed descriptions)
- Services without tokens (4 detailed descriptions)
- Token formats (4 types with specifications)
- Expiration windows (all types listed)
- Complete token flow paths (4 main scenarios)
- Critical security notes (7 key areas)
- Recommendations (immediate, short, medium, long term)

**Best for:** Management summary, architectural overview, onboarding

---

## Quick Navigation

### If you want to...

**Understand the overall architecture**
→ Read: TOKEN_ENCRYPTION_SUMMARY.txt (start here)

**Look up a specific service**
→ Use: TOKEN_ENCRYPTION_QUICK_REFERENCE.md (service matrix)
→ Then: TOKEN_ENCRYPTION_MAP.md (detailed section for that service)

**Understand token formats**
→ Read: TOKEN_ENCRYPTION_SUMMARY.txt (Token Formats section)
→ Or: TOKEN_ENCRYPTION_MAP.md (Token Data Payloads section)

**Trace a complete payment flow**
→ Read: TOKEN_ENCRYPTION_MAP.md (Service Dependency Graph)
→ Or: TOKEN_ENCRYPTION_SUMMARY.txt (Token Flow Paths)

**Check encryption/decryption status**
→ Use: TOKEN_ENCRYPTION_QUICK_REFERENCE.md (Service Matrix)

**Find signing key usage**
→ Use: TOKEN_ENCRYPTION_QUICK_REFERENCE.md (Key Distribution)
→ Or: TOKEN_ENCRYPTION_SUMMARY.txt (SIGNING KEYS section)

**Review security aspects**
→ Read: TOKEN_ENCRYPTION_MAP.md (Critical Security Notes)
→ Or: TOKEN_ENCRYPTION_SUMMARY.txt (Security Notes)

**Find recommendations**
→ Read: TOKEN_ENCRYPTION_SUMMARY.txt (Recommendations)

---

## Service Coverage

All 13 services analyzed:

### With Encryption/Decryption (9)
- ✅ GCWebhook1-10-26 (decrypt + encrypt)
- ✅ GCWebhook2-10-26 (decrypt only)
- ✅ GCSplit1-10-26 (encrypt only, dual-key)
- ✅ GCSplit2-10-26 (decrypt + encrypt)
- ✅ GCSplit3-10-26 (decrypt + encrypt)
- ✅ GCHostPay1-10-26 (decrypt + encrypt, dual-key)
- ✅ GCHostPay2-10-26 (decrypt + encrypt)
- ✅ GCHostPay3-10-26 (decrypt + encrypt)
- ✅ GCBatchProcessor-10-26 (encrypt only)

### With Token Manager but Not Used (1)
- ⚠️ GCAccumulator-10-26 (has token_manager.py but uses plain JSON)

### With Tokens but No Token Manager (1)
- ✅ GCMicroBatchProcessor-10-26 (decrypt + encrypt, separate token manager)

### Without Tokens (2)
- ❌ np-webhook-10-26 (signature verification only)
- ❌ TelePay10-26 (telegram bot, no tokens)

---

## Key Statistics

| Metric | Value |
|--------|-------|
| Total services | 13 |
| Services with token_manager.py | 11 |
| Services using encryption | 9 |
| Services using tokens | 9 |
| Services with BOTH encrypt + decrypt | 6 |
| Services that decrypt only | 2 |
| Services that encrypt only | 2 |
| Services without tokens | 3 |
| Unused token managers | 1 |
| Signing keys | 3 |
| Token formats | 4 |
| Documentation lines | 1,403 |

---

## Signing Keys

1. **SUCCESS_URL_SIGNING_KEY**
   - Purpose: Internal service-to-service communication
   - Used by: 10 services
   - Boundary: Internal only

2. **TPS_HOSTPAY_SIGNING_KEY**
   - Purpose: External boundary security (GCSplit1 ↔ GCHostPay1)
   - Used by: 3 services (GCSplit1, GCHostPay1, GCBatchProcessor)
   - Boundary: External security perimeter

3. **NOWPAYMENTS_IPN_SECRET**
   - Purpose: HMAC-SHA256 signature verification (not encryption)
   - Used by: 1 service (np-webhook)
   - Type: Signature verification, not token encryption

---

## Flow Paths

### 4 Main Token Flow Scenarios

1. **Instant Payout Path** (7+ services, 37 steps)
   - Full payment processing with all verification steps
   - Detailed in: TOKEN_ENCRYPTION_MAP.md & TOKEN_ENCRYPTION_SUMMARY.txt

2. **Threshold Payout Path** (3 services)
   - Accumulation + async conversion
   - Detailed in: Both files

3. **Batch Payout Path** (2 services)
   - Scheduler-triggered batch processing
   - Detailed in: Both files

4. **Micro-Batch Path** (3 services)
   - Scheduler-triggered with callback
   - Detailed in: Both files

---

## Security Highlights

### Two-Key Boundary Architecture
- External: GCSplit1 ↔ GCHostPay1 (TPS_HOSTPAY_SIGNING_KEY)
- Internal: All other services (SUCCESS_URL_SIGNING_KEY)

### Token Security Features
- HMAC-SHA256 signature (truncated to 16 bytes)
- Base64 URL-safe encoding without padding
- Timestamp validation (prevents replay attacks)
- Variable expiration windows by use case
- Idempotency markers in database

### Validation Points
- Signature verification on all encrypted tokens
- Timestamp within expiration window
- ID handling for negative Telegram IDs (48-bit)
- Database idempotency checks

---

## Recommendations

### Immediate
- Review GCAccumulator unused token_manager
- Verify all signing keys properly rotated
- Check token expiration handling in logs

### Short Term
- Monitor token encryption/decryption failures
- Validate idempotency markers
- Test key rotation procedure

### Medium Term
- Consider consolidating token_manager implementations
- Add logging for all decrypt failures
- Implement token usage metrics

### Long Term
- Document any token format changes
- Plan key rotation strategy
- Archive historical signing keys

---

## Usage Guidelines

### For Developers
1. Read TOKEN_ENCRYPTION_SUMMARY.txt first (overview)
2. Find your service in TOKEN_ENCRYPTION_QUICK_REFERENCE.md
3. Go to TOKEN_ENCRYPTION_MAP.md for detailed analysis

### For Security Review
1. Read "Critical Security Notes" in TOKEN_ENCRYPTION_MAP.md
2. Check token formats and validation
3. Review Recommendations section

### For Operations
1. Use TOKEN_ENCRYPTION_QUICK_REFERENCE.md as reference
2. Monitor services listed by signing key
3. Implement recommendations checklist

### For Architecture Discussion
1. Start with TOKEN_ENCRYPTION_SUMMARY.txt
2. Reference Service Dependency Graph in TOKEN_ENCRYPTION_MAP.md
3. Use flow paths for scenario discussion

---

## Document Version

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-11-08 | Initial comprehensive analysis of all 13 services |

---

## Contact & Questions

This documentation was generated as part of comprehensive analysis of the TelegramFunnel payout architecture. All 13 services have been analyzed and documented.

For updates or clarifications, refer to:
- TOKEN_ENCRYPTION_MAP.md for complete technical details
- TOKEN_ENCRYPTION_QUICK_REFERENCE.md for quick lookup
- TOKEN_ENCRYPTION_SUMMARY.txt for high-level overview

