# Architectural Decisions Log

## 2025-11-16: PGP_SERVER_v1 Security Architecture Assessment

### Decision: Document Current Security Architecture and Identify Critical Gaps

**Context:**
- Post-Phase 4B redundancy elimination (1,471 lines removed)
- Need to understand overlap between root files and modular directories
- Security architecture needs validation against industry best practices
- User requested thorough analysis of overlap, security benefits, and weaknesses

**Analysis Performed:**
- Comprehensive review of all 20 critical root files
- Mapping of relationships with /api, /bot, /models, /security, /services
- Security architecture assessment using Context7 MCP (Flask-Security, python-telegram-bot)
- Vulnerability identification using OWASP Top 10 framework
- Compliance scoring against best practices

**Findings:**

**Overlap Rationale (Intentional Architecture):**
1. **Bot Instance Creation (9 files)**: Background services need independent Bot instances for concurrent operations - NOT REDUNDANT
2. **Secret Management (19 files)**: Dependency injection pattern - ConfigManager is single source of truth - NOT REDUNDANT
3. **Database Access**: Shared ConnectionPool instance across all managers - NOT REDUNDANT
4. **Handler Registration**: Hybrid OLD/NEW pattern during phased migration (Phase 4C planned) - TEMPORARY OVERLAP

**Security Strengths:**
- ✅ Defense-in-depth: 3-layer middleware stack (IP whitelist, HMAC, rate limiter)
- ✅ Secret Manager integration for all credentials
- ✅ Connection pooling prevents DoS attacks
- ✅ SQLAlchemy prevents SQL injection

**Critical Security Gaps:**
- 🔴 No IPN signature verification (NowPayments webhook)
- 🔴 No CSRF protection on webhook endpoints
- 🟠 Missing security headers (CSP, X-Frame-Options, HSTS)
- 🟠 No bot token rotation policy
- 🟡 In-memory rate limiting (doesn't scale horizontally)
- 🟡 No replay attack prevention

**Compliance Scores:**
- Flask-Security: 62.5% (5/8 features)
- python-telegram-bot: 42.9% (3/7 features)
- OWASP Top 10: 60% (6/10 risks mitigated)

**Decision:**
Maintain current hybrid architecture with the following security improvements:

**Immediate (Week 1):**
1. Implement NowPayments IPN signature verification (CRITICAL)
2. Add Telegram webhook secret token verification (HIGH)

**Short-Term (Sprint 1):**
1. Add CSRF protection with flask-wtf
2. Implement security headers with flask-talisman
3. Audit for SQL injection vulnerabilities

**Medium-Term (Sprint 2-3):**
1. Add replay attack prevention (timestamp + nonce validation)
2. Deploy Redis for distributed rate limiting
3. Add input validation framework

**Long-Term (Q1 2025):**
1. Implement bot token rotation mechanism
2. Complete Phase 4C migration (optional)
3. Security penetration testing

**Rationale:**
- Current architecture is sound (intentional overlap, not redundant)
- Security gaps are implementation details, not architectural flaws
- Phased approach reduces risk of breaking changes
- Critical gaps must be addressed before production scaling

**Alternatives Considered:**
- Full architectural rewrite → Rejected: Current architecture is solid, only security gaps need fixing
- Immediate Phase 4C migration → Rejected: Security fixes are higher priority
- Merge all Bot instances → Rejected: Would couple independent services

**Consequences:**
- **Positive**: Clear security roadmap with prioritized actions
- **Positive**: Architectural decisions validated (overlap is intentional)
- **Positive**: Compliance gaps identified with concrete mitigation steps
- **Negative**: Requires additional development effort (estimated 40+ hours)
- **Negative**: Need Redis deployment for distributed rate limiting

**Documentation:**
- Created SECURITY_AND_OVERLAP_ANALYSIS.md (730+ lines)
- Provides complete vulnerability list, recommendations, and implementation examples
- Includes best practices compliance matrix and security checklist

---

## 2025-11-15: PGP_v1 Naming Architecture

### Decision: Complete Service Renaming to PGP_v1 Pattern

**Context:**
- Existing services used inconsistent naming: GC*-10-26, TelePay10-26, np-webhook-10-26
- Date-based naming (10-26) became confusing over time
- Mixed naming conventions (GC prefix, TelePay prefix, np prefix)

**Decision:**
Implemented unified naming scheme:
- **Cloud Run Services**: `pgp-<component>-v1` (lowercase with hyphens)
- **Python Files**: `pgp_<component>_v1.py` (lowercase with underscores)
- **Cloud Tasks Queues**: `pgp-<component>-queue-v1`
- **Directories**: `PGP_<COMPONENT>_v1` (uppercase with underscores)

**Rationale:**
1. **Clarity**: PGP (PayGatePrime) is self-documenting
2. **Versioning**: v1 suffix allows future iterations
3. **Consistency**: Same pattern across all 17 services
4. **Professional**: Industry-standard naming convention
5. **Searchability**: Easy to grep/find all related services

**Alternatives Considered:**
- Keep date-based naming → Rejected: Not sustainable long-term
- Use mixed prefixes → Rejected: Causes confusion
- No versioning → Rejected: Limits future flexibility

**Consequences:**
- **Positive**: Clear, professional, maintainable naming
- **Positive**: Easy rollback (old services untouched)
- **Positive**: Better service discovery and documentation
- **Negative**: Requires update to all references (managed systematically)
- **Negative**: Temporary dual-service running during transition

**Implementation:**
- Phase 1: Dockerfiles and deployment scripts ✅ COMPLETE
- Phase 2: Python code cross-references (pending)
- Phase 3: Master deployment and testing (pending)

---

## 2025-11-15: Portable Path Resolution in Deployment Scripts

**Decision:**
Use `$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../../PGP_*_v1` pattern for all SOURCE_DIR paths in deployment scripts.

**Rationale:**
- Works on both development environment (/home/user) and production VM (/home/kingslavxxx)
- Eliminates hardcoded absolute paths
- Makes scripts portable across different machines
- Relative paths ensure scripts work from any invocation location

**Alternatives Considered:**
- Hardcoded paths → Rejected: Not portable
- Environment variables → Rejected: Extra configuration burden
- Git root detection → Rejected: Unnecessary complexity

**Consequences:**
- Scripts can be run from any location
- No manual path updates needed when moving between environments
- Cleaner, more maintainable code
