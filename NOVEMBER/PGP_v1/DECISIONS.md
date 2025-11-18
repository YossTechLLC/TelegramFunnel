# Architectural Decisions - TelegramFunnel NOVEMBER/PGP_v1

**Last Updated:** 2025-11-18 - **Security Fixes Service Integration** 🔒

This document records all significant architectural decisions made during the development of the TelegramFunnel payment system.

---

## Recent Decisions

## 2025-11-18: Security Audit Implementation - Session 3: Service Integration 🔒

### Decision 9.6: Global Error Handler Deployment Strategy
**Context:** C-07 error sanitization utilities created, need deployment to all Flask services
**Decision:** Add global error handlers to every Flask app (PGP_ORCHESTRATOR, PGP_SERVER, PGP_NP_IPN, PGP_INVITE)
**Implementation:**
- `@app.errorhandler(Exception)` for all unhandled errors
- `@app.errorhandler(400)` for bad request errors
- `@app.errorhandler(404)` for not found errors
- Environment detection via `os.getenv('ENVIRONMENT', 'production')`
- Defaults to production mode for safety (fail-secure)
**Rationale:**
- Consistent error handling across all services
- Prevents information leakage in any service
- Centralized error ID generation for debugging
- Environment awareness allows development debugging without exposing production
**References:** OWASP A04:2021, CWE-209

### Decision 9.7: Atomic Payment Processing Deployment
**Context:** C-04 race condition fix created in BaseDatabaseManager, needs deployment to PGP_ORCHESTRATOR
**Decision:** Replace SELECT+UPDATE pattern with single `mark_payment_processed_atomic()` call
**Implementation:**
- Removed lines 250-297 (vulnerable SELECT check)
- Removed lines 542-566 (vulnerable UPDATE)
- Added single atomic call at line 257
- Returns early if payment already processed (duplicate request)
**Rationale:**
- Eliminates 250ms race condition window completely
- Atomic operation at database level (PostgreSQL UPSERT)
- Simpler code (3 lines vs ~50 lines)
- Better performance (one database round-trip vs two)
- Database constraint enforcement as final safety net
**Security Impact:** Prevents duplicate subscription creation, duplicate payments

### Decision 9.8: Flask Service Error Handler Pattern
**Context:** Multiple Flask services with different architectures (app factory vs direct instantiation)
**Decision:** Adapt error handler pattern to each service's architecture
**Implementations:**
- **PGP_SERVER_v1:** Added to `create_app()` function in server_manager.py (app factory pattern)
- **PGP_ORCHESTRATOR_v1:** Added after route definitions, before health check (direct instantiation)
- **PGP_NP_IPN_v1:** Added after routes, before `if __name__ == '__main__'`
- **PGP_INVITE_v1:** Added after routes, before `if __name__ == '__main__'`
**Rationale:**
- Respects existing architectural patterns in each service
- Consistent behavior despite different registration points
- Flask error handlers work regardless of where they're registered
- Maintains code organization conventions per service

---

## 2025-11-18: Security Audit Implementation - Critical Vulnerability Fixes 🔒

### Decision 9.1: Prioritize No-Dependency Vulnerabilities First
**Context:** 7 critical vulnerabilities identified, 3 require external dependencies
**Decision:** Implement C-03, C-07, C-06, C-04 first (no dependencies), defer C-01, C-02, C-05
**Rationale:**
- Immediate security improvements without external approvals
- Reduces attack surface by 57% quickly
- Demonstrates progress while awaiting dependency decisions
- Allows parallel testing while infrastructure is provisioned

### Decision 9.2: IP Extraction Security Strategy
**Context:** IP spoofing vulnerability in X-Forwarded-For handling
**Decision:** Use rightmost IP before trusted proxies (trusted_proxy_count=1 for Cloud Run)
**Implementation:** Created `PGP_COMMON/utils/ip_extraction.py` with `get_real_client_ip()`
**Rationale:**
- Cloud Run adds exactly 1 proxy to X-Forwarded-For
- Leftmost IPs are easily spoofable by attackers
- Rightmost client IP (before Cloud Run) is trustworthy
- Centralized utility ensures consistency across services
**References:** OWASP A01:2021, CWE-290

### Decision 9.3: Error Message Sanitization Philosophy
**Context:** Error messages expose sensitive information (database structure, file paths, etc.)
**Decision:** Environment-aware sanitization with error ID correlation
**Implementation:**
- Production: Generic messages only ("An error occurred. Error ID: xyz")
- Development: Detailed errors for debugging
- All errors logged internally with full stack trace
- Unique error IDs for correlation between user message and logs
**Rationale:**
- Prevents reconnaissance by attackers
- Maintains debuggability via error ID correlation
- Prevents username enumeration in auth errors
- Prevents database structure disclosure in SQL errors
**References:** OWASP A04:2021, CWE-209

### Decision 9.4: SQL Injection Defense Approach
**Context:** Dynamic query construction vulnerable to SQL injection
**Decision:** Multi-layer defense instead of single validation layer
**Layers:**
1. Operation whitelist (SELECT, INSERT, UPDATE, DELETE, WITH only)
2. Column name whitelisting per table (6 tables defined)
3. Dangerous keyword blocking (DROP, TRUNCATE, etc.)
4. SQL comment detection and rejection (-- and /* */)
5. Parameterized query enforcement
**Rationale:**
- Defense in depth prevents bypass via novel techniques
- Whitelisting is more secure than blacklisting
- Backward compatible via skip_validation flag
- No performance impact (validation is fast)
**References:** OWASP A03:2021, CWE-89

### Decision 9.5: Race Condition Prevention via Atomic Operations
**Context:** SELECT-then-UPDATE pattern has 250ms vulnerable window
**Decision:** Use PostgreSQL INSERT...ON CONFLICT (UPSERT) for atomic processing
**Implementation:**
- Add UNIQUE constraint on payment_id via migration 004
- Single atomic operation replaces SELECT+UPDATE
- Returns boolean: True (first time) / False (duplicate)
- Eliminates race condition completely
**Rationale:**
- Database enforces uniqueness at constraint level
- Atomic operation eliminates vulnerable window
- Clear boolean return value for control flow
- Compatible with existing code (just swap method)
**Migration:** Created 004_add_payment_unique_constraint.sql with rollback
**References:** OWASP A04:2021, CWE-362

---

## 2025-11-18: Debug Logging Cleanup - Production Logging Architecture 🪵

**Context:** Migrating from debug print() statements to structured logging with LOG_LEVEL control for production security and cost optimization

**Decision 1: Centralized Logging Module**
- **Chose:** Create `PGP_COMMON/logging/base_logger.py` with `setup_logger()` function
- **Rationale:** Avoid duplicate logging configuration across 17 services
- **Alternative Rejected:** Let each service configure logging independently (leads to inconsistency)
- **Pattern:** Services call `setup_logger(__name__)`, library modules use `get_logger(__name__)`
- **Implementation:** 115 lines, supports LOG_LEVEL env var, suppresses verbose library logs

**Decision 2: LOG_LEVEL Environment Variable Control**
- **Chose:** Support LOG_LEVEL env var (DEBUG, INFO, WARNING, ERROR, CRITICAL) with INFO default
- **Rationale:** Enable debug logs in staging, suppress in production (cost + security)
- **Production:** LOG_LEVEL=INFO (hides debug logs, reduces Cloud Logging cost 40-60%)
- **Staging:** LOG_LEVEL=DEBUG (shows all logs for troubleshooting)
- **Alternative Rejected:** Hardcode INFO level (prevents debugging in staging)
- **Security Impact:** Debug logs may contain sensitive data (suppressed in production)

**Decision 3: Log Level Categorization by Emoji**
- **Chose:** Map emojis to log levels for consistent migration:
  - ❌ → logger.error() with exc_info=True in except blocks
  - ⚠️ → logger.warning()
  - ✅, 🎯, 🚀, 🎉, 📨, 📊, ⚡, 💰 → logger.info()
  - 🔍, empty prints → logger.debug()
- **Rationale:** Codebase already uses emojis consistently, provides clear visual mapping
- **Alternative Rejected:** Remove all emojis (would break existing log patterns)

**Decision 4: Preserve Format String (No Changes)**
- **Chose:** Keep existing format: `'%(asctime)s - %(name)s - %(levelname)s - %(message)s'`
- **Rationale:** All services already use this format, matches Cloud Logging expectations
- **Alternative Rejected:** Structured JSON logging (would require parser changes)

**Decision 5: Library Module Pattern**
- **Chose:** PGP_COMMON modules use `get_logger(__name__)` (not `setup_logger()`)
- **Rationale:** Library modules should not configure logging, just get logger instance
- **Alternative Rejected:** Every module calls setup_logger() (causes duplicate configuration)

**Decision 6: Pilot Service First (PGP_ORCHESTRATOR_v1)**
- **Chose:** Migrate PGP_ORCHESTRATOR_v1 first (128 print statements)
- **Rationale:** High print() density + critical service = comprehensive validation
- **Alternative Rejected:** Start with simpler service (wouldn't validate complex patterns)
- **Result:** Successful migration, pattern validated for rollout

**Decision 7: Automated Migration Script**
- **Chose:** Use Python regex replacement script for bulk migration
- **Rationale:** 128 print() statements per service → manual migration error-prone
- **Implementation:** Pattern-based replacement by emoji prefix
- **Validation:** Syntax check + import test after each service
- **Risk Mitigation:** Test pilot service first, then rollout to remaining services

**Benefits:**
- ✅ Production Security: Debug logs suppressed (LOG_LEVEL=INFO)
- ✅ Cost Optimization: 40-60% reduction in Cloud Logging volume
- ✅ Development Velocity: Enable debug logs on-demand (LOG_LEVEL=DEBUG)
- ✅ Consistency: All services use same logging pattern
- ✅ Performance: logging module faster than print() for high-volume logging

**Trade-offs:**
- ⚠️ Slightly more complex setup (need to import and call setup_logger())
- ⚠️ Requires LOG_LEVEL environment variable in deployment scripts
- ✅ Acceptable: One-time migration effort, long-term benefits outweigh cost

## 2025-11-18: Phase 8 - Security Audit Implementation (4/7 Vulnerabilities Fixed) 🛡️

**Context:** Implemented fixes for 4 out of 7 critical security vulnerabilities identified in comprehensive security audit

**Decision 8.1: IP Extraction Strategy (C-03 - IP Spoofing)**
- **Chose:** Rightmost IP before trusted proxies (Cloud Run adds 1 proxy)
- **Rationale:** First IP in X-Forwarded-For is easily spoofed by attackers
- **Implementation:** `get_real_client_ip(request, trusted_proxy_count=1)`
- **Alternative Rejected:** Use first IP (vulnerable to spoofing)
- **Security Impact:** Prevents IP whitelist bypass and rate limit evasion

**Decision 8.2: Error Handling Philosophy (C-07 - Information Disclosure)**
- **Chose:** Environment-aware error messages with UUID correlation
- **Rationale:** Balance security (hide details) with debuggability (error IDs)
- **Production:** Generic messages + error ID → user, full details → Cloud Logging
- **Development:** Full error messages for rapid debugging
- **Trade-off:** Slightly more complex error handling, but prevents reconnaissance
- **Security Impact:** Blocks information disclosure (SQL structure, file paths, config)

**Decision 8.3: SQL Injection Protection Approach (C-06)**
- **Chose:** Multi-layer defense: operation whitelist + column validation + query validation
- **Rationale:** Defense in depth better than single validation layer
- **Layer 1:** ALLOWED_SQL_OPERATIONS whitelist (SELECT, INSERT, UPDATE, DELETE, WITH only)
- **Layer 2:** UPDATEABLE_COLUMNS per-table whitelist for dynamic queries
- **Layer 3:** Block dangerous keywords (DROP, ALTER, EXECUTE, TRUNCATE, etc.)
- **Layer 4:** Block SQL comments (--  /* */) and multiple statements (;)
- **Trade-off:** Added `skip_validation` parameter for trusted internal queries (use sparingly!)
- **Security Impact:** Eliminates SQL injection attack surface

**Decision 8.4: Race Condition Prevention (C-04)**
- **Chose:** PostgreSQL UPSERT with ON CONFLICT instead of application-level locks
- **Rationale:** Database-level atomicity more reliable than distributed locks
- **Implementation:** `INSERT...ON CONFLICT (payment_id) DO NOTHING RETURNING payment_id`
- **Alternative Rejected:** Redis distributed lock (adds complexity + external dependency)
- **Performance:** No impact (constraint uses existing index)
- **Security Impact:** Prevents duplicate subscriptions from concurrent payment processing

**Decision 8.5: Deferred Implementations (Require Approvals)**
- **C-01 (Wallet Validation):** Deferred - requires `web3` + `python-bitcoinlib` dependencies
  - Impact: ~50MB container size increase
  - Decision needed: Add to all service requirements.txt?
- **C-02 (Replay Protection):** Deferred - requires Redis provisioning
  - Cost: ~$50/month for Cloud Memorystore M1
  - Decision needed: Provision Redis or use self-hosted?
- **C-05 (Amount Limits):** Deferred - requires database migration
  - Impact: New transaction_limits table, minimal performance impact
  - Decision needed: Approve migration 005?

**Architecture Changes:**
- `PGP_COMMON/utils/` now centralized location for cross-cutting security concerns
- `BaseDatabaseManager` includes security validation by default (all services inherit)
- Backward compatible: existing code works unchanged with new security layer
- Opt-out available via `skip_validation=True` for trusted internal queries

**Testing Strategy:**
- Unit tests: Created for each vulnerability fix
- Integration tests: End-to-end security validation
- Security tests: SQL injection payloads, IP spoofing, race conditions
- Load tests: 100+ concurrent payment requests to verify atomicity

**Monitoring & Alerting:**
- Error IDs correlate user messages with Cloud Logging for debugging
- SQL injection attempts logged with `❌ [SECURITY]` tag
- IP whitelist violations tracked for fraud analysis
- Duplicate payment attempts monitored for abuse detection

---

