# Architectural Decisions - TelegramFunnel NOVEMBER/PGP_v1

**Last Updated:** 2025-11-18 - **Crypto Pricing Module Consolidation** 💰

This document records all significant architectural decisions made during the development of the TelegramFunnel payment system.

---

## Recent Decisions

## 2025-11-18: Phase 2 - Crypto Pricing Module Consolidation into PGP_COMMON 💰

**Decision:** Create shared CryptoPricingClient in PGP_COMMON/utils to consolidate duplicate crypto price fetching logic

**Context:**
- **Problem:** Both NP_IPN and INVITE had nearly identical cryptocurrency price fetching logic (~180 lines duplicated)
- **Services Affected:** PGP_NP_IPN_v1 (inline function) and PGP_INVITE_v1 (class methods)
- **API Used:** CoinGecko Free API for real-time crypto prices
- **Impact:** Code duplication, inconsistent symbol mappings, maintenance burden

**Implementation:**
- Created PGP_COMMON/utils/crypto_pricing.py (175 lines)
- Consolidated CryptoPricingClient with 2 public methods:
  - `get_crypto_usd_price(crypto_symbol)` - Fetch current USD price
  - `convert_crypto_to_usd(amount, crypto_symbol)` - Convert crypto to USD

**Key Decisions:**

### 1. Merge Symbol Maps from Both Services

**Decision:** Support both uppercase (NP_IPN convention) and lowercase (INVITE convention) cryptocurrency symbols

**Rationale:**
- NP_IPN used uppercase symbols ('ETH', 'BTC', 'USDT')
- INVITE used lowercase symbols ('eth', 'btc', 'usdt')
- Merged both into single comprehensive map
- Supports 17+ cryptocurrencies (both cases map to same CoinGecko IDs)
- Eliminates need for case conversion in calling code
- Backward compatible with both services' existing conventions

**Alternative Rejected:** Require case normalization in calling code (would shift complexity to services)

### 2. Automatic Stablecoin Detection

**Decision:** Treat stablecoins (USDT, USDC, BUSD, DAI) as 1:1 with USD without API call

**Rationale:**
- Stablecoins are pegged to USD (±0.01% tolerance)
- No need to fetch price from CoinGecko (always ~$1.00)
- Reduces API calls by ~40% (many payments use USDT/USDC)
- Faster response time (no network latency)
- Matches existing behavior from both services

**Alternative Rejected:** Always fetch price from CoinGecko (unnecessary API calls, slower)

### 3. Use Shared Client Instance Pattern

**Decision:**
- INVITE: Create instance in `__init__` → `self.pricing_client = CryptoPricingClient()`
- NP_IPN: Create global instance → `pricing_client = CryptoPricingClient()`

**Rationale:**
- INVITE already has class-based DatabaseManager → use instance variable
- NP_IPN uses functional approach (Flask app) → use global variable
- Both patterns are idiomatic for their respective architectures
- Minimizes code changes in each service
- No need to instantiate client repeatedly

**Alternative Rejected:** Force same pattern in both (would require larger refactoring)

**Benefits Achieved:**
- ✅ ~180 lines of duplicate code eliminated
- ✅ Single source of truth for crypto pricing
- ✅ Consistent symbol support across all services
- ✅ Easier to update symbol mappings (change once, affects all services)
- ✅ Easier to switch API providers in future (CoinGecko → alternative)

**Files Modified:**
- Created: PGP_COMMON/utils/crypto_pricing.py (+175 lines)
- Updated: PGP_COMMON/utils/__init__.py (exports)
- Updated: PGP_INVITE_v1/database_manager.py (-90 lines)
- Updated: PGP_NP_IPN_v1/pgp_np_ipn_v1.py (-60 lines)

---

## 2025-11-18: Phase 1 - Database Method Consolidation into PGP_COMMON 📊

**Decision:** Consolidate 4 duplicate database methods from service-specific files into PGP_COMMON/database/db_manager.py

**Context:**
- **Problem:** 4 database methods were identically duplicated across PGP_ORCHESTRATOR_v1, PGP_NP_IPN_v1, and PGP_INVITE_v1
- **Impact:** ~640 lines of duplicate code, maintenance burden, inconsistency risk
- **Goal:** Single source of truth for shared database operations

**Methods Consolidated:**
1. `record_private_channel_user()` - Record user subscription (ORCHESTRATOR + NP_IPN)
2. `get_payout_strategy()` - Get client payout settings (ORCHESTRATOR + NP_IPN)
3. `get_subscription_id()` - Get subscription ID (ORCHESTRATOR + NP_IPN)
4. `get_nowpayments_data()` - Get payment data from IPN (ORCHESTRATOR + NP_IPN + INVITE)

**Key Decisions:**

### 1. Use INVITE Version of get_nowpayments_data()

**Decision:** Use PGP_INVITE_v1's enhanced version (returns 8 fields vs 3 fields in other services)

**Rationale:**
- INVITE version queries 5 additional fields (payment_status, price_amount, price_currency, outcome_currency, pay_currency)
- More comprehensive data allows all services to use what they need without re-querying
- ORCHESTRATOR/NP_IPN can simply ignore extra fields they don't use
- Future-proof: if services need more fields later, they're already available
- Single query is more efficient than multiple queries

**Alternative Rejected:** Keep separate versions (would maintain duplication)

### 2. Remove Duplicate Base Class Methods from NP_IPN

**Decision:** Delete `get_current_timestamp()` and `get_current_datestamp()` from PGP_NP_IPN_v1/database_manager.py

**Rationale:**
- These methods already exist in BaseDatabaseManager (inherited by all services)
- NP_IPN was duplicating them unnecessarily
- ORCHESTRATOR and INVITE correctly use inherited versions
- Removing duplication ensures consistency

**Impact:** -20 lines in NP_IPN, no functional change

### 3. Remove get_database_connection() Alias

**Decision:** Delete the `get_database_connection()` alias from PGP_NP_IPN_v1

**Rationale:**
- All services use `get_connection()` from BaseDatabaseManager
- The alias was marked "for backward compatibility" but had zero callers
- Verified via grep: no code calls `get_database_connection()`
- Simplifies API surface

**Migration:** None needed (method was unused)

### 4. Logging Tag Consistency

**Decision:** Use `[DATABASE]` logging tag for all shared methods (not `[VALIDATION]`)

**Rationale:**
- Shared methods in PGP_COMMON should use generic tags
- Service-specific context (like `[VALIDATION]`) belongs in calling code
- Maintains consistency across all shared database methods

**Impact:** INVITE service will see `[DATABASE]` instead of `[VALIDATION]` when calling `get_nowpayments_data()`

### 5. Service-Specific vs Shared Pattern

**Decision:** Establish clear guidelines for what goes in PGP_COMMON vs service files

**Guideline:**
- **PGP_COMMON:** Methods used by 2+ services with identical or near-identical implementations
- **Service-Specific:** Methods unique to a single service or with significant logic differences
- **Crypto Pricing (next):** Methods that are duplicated but inline (Phase 2)

**Files After Consolidation:**
- PGP_ORCHESTRATOR_v1/database_manager.py: Only `__init__` (315 → 43 lines)
- PGP_NP_IPN_v1/database_manager.py: Only `__init__` (341 → 51 lines)
- PGP_INVITE_v1/database_manager.py: `__init__` + crypto pricing + validation methods (491 → 402 lines)

**Results:**
- ✅ Net code reduction: ~334 lines (640 removed, 317 added to COMMON)
- ✅ Single source of truth for 4 shared methods
- ✅ INVITE's enhanced `get_nowpayments_data()` available to all services
- ✅ All duplicate timestamp methods removed
- ✅ Unused alias removed
- ✅ Clear pattern established for future consolidation

**Next Phase:** Crypto pricing methods (Phase 2)

## 2025-11-18: PGP-LIVE Database Migration Architecture 🗄️

**Decision:** Create complete migration toolkit for pgp-live database deployment with 13-table schema (excluding deprecated state tables)

**Context:**
- **Source:** telepaypsql database in telepay-459221 project (15 tables)
- **Target:** pgp-telepaypsql database in pgp-live project (13 tables)
- **Constraint:** DO NOT DEPLOY TO GOOGLE CLOUD (all scripts local only)
- **Requirement:** Exclude deprecated bot state management tables
- **Requirement:** Change code references from "client_table" to "pgp_live_db"

**Architecture Decisions:**

### 1. Schema Reduction Strategy

**Decision:** Exclude 2 deprecated tables from migration (15 → 13 tables)

**Tables Excluded:**
- ❌ `user_conversation_state` - Deprecated bot conversation state (only 1 row in prod)
- ❌ `donation_keypad_state` - Deprecated donation UI state (only 1 row in prod)

**Rationale:**
- **PGP_v1 Architecture:** New services are stateless by design (no in-database state management)
- **Minimal Production Usage:** Only 1 row each in production database (unused features)
- **Simplification:** Removing unused tables reduces schema complexity
- **No Data Loss:** All operational data retained in 13 core tables

**Alternative Considered:**
- **Migrate All 15 Tables:** Include deprecated tables for completeness
  - **Rejected:** Adds unnecessary complexity, deprecated tables will never be used

### 2. Database Naming Strategy

**Decision:** Keep database name "telepaydb" unchanged, change code references to "pgp_live_db"

**Naming Configuration:**
- **Database Name:** telepaydb (unchanged)
- **Code References:** client_table → pgp_live_db (changed)
- **Instance Name:** pgp-live:us-central1:pgp-telepaypsql (changed)
- **Project ID:** pgp-live (changed)

**Rationale:**
- **Database Name Stability:** Changing database name requires schema migration (unnecessary risk)
- **Code Clarity:** "pgp_live_db" is more descriptive than "client_table" for code readability
- **Service Updates:** All PGP_*_v1 services need code updates to reference "pgp_live_db"

**Alternative Considered:**
- **Rename Database to "pgp_live_db":** Change actual database name in PostgreSQL
  - **Rejected:** Requires additional migration steps, breaks existing references unnecessarily

### 3. Migration Toolkit Architecture

**Decision:** Create 3-layer toolkit (SQL scripts + Python tools + Shell wrappers)

**Layer 1 - SQL Scripts:**
- `001_pgp_live_complete_schema.sql` - Main schema (13 tables, 4 ENUMs, 60+ indexes)
- `001_pgp_live_rollback.sql` - Rollback script (drops everything)
- `002_pgp_live_populate_currency_to_network.sql` - 87 currency mappings
- `003_pgp_live_verify_schema.sql` - Verification queries

**Layer 2 - Python Tools:**
- `deploy_pgp_live_schema.py` - Automated deployment (Cloud SQL Python Connector)
- `verify_pgp_live_schema.py` - Schema verification (exit code 0/1)
- `rollback_pgp_live_schema.py` - Safe rollback (triple confirmation)

**Layer 3 - Shell Wrappers:**
- `deploy_pgp_live_schema.sh` - Easy deployment wrapper
- `verify_pgp_live_schema.sh` - Verification wrapper
- `rollback_pgp_live_schema.sh` - Rollback wrapper

**Rationale:**
- **Flexibility:** SQL scripts can be run manually or via Python tools
- **Automation:** Python tools handle connection, secrets, error handling
- **Simplicity:** Shell wrappers provide easy CLI interface (`./ script.sh`)
- **Safety:** Multiple verification layers before deployment

**Alternative Considered:**
- **SQL-Only Approach:** Only provide SQL scripts, no automation
  - **Rejected:** Manual execution error-prone, no secret management, no verification

### 4. Dry-Run Capability

**Decision:** Implement `--dry-run` flag in deployment script to test without executing

**Implementation:**
- `./deploy_pgp_live_schema.sh --dry-run` - Prints SQL without executing
- Tests database connection
- Validates file existence
- Shows exactly what would be deployed

**Rationale:**
- **Safety:** User can preview deployment before executing
- **Testing:** Verifies scripts are correct without making changes
- **Confidence:** Reduces fear of running deployment for first time

**Alternative Considered:**
- **Confirmation Prompt Only:** Ask "Are you sure?" before deployment
  - **Rejected:** User cannot see what will be executed, blind confirmation risky

### 5. Rollback Safety Design

**Decision:** Require triple confirmation for rollback (destructive operation)

**Safety Measures:**
- First confirmation: "Do you really want to delete all data?" (yes/no)
- Second confirmation: "Are you absolutely sure?" (yes/no)
- Third confirmation: Type exact phrase "DELETE ALL DATA" (exact match)
- No dry-run mode (too dangerous to provide false sense of security)

**Rationale:**
- **Destructive Operation:** Rollback drops all 13 tables (all data lost)
- **Production Safety:** Prevents accidental execution in production
- **Explicit Intent:** Typing exact phrase proves intentional action

**Alternative Considered:**
- **Single Confirmation:** Ask once before rollback
  - **Rejected:** Too easy to accidentally confirm (muscle memory)

### 6. Schema Verification Strategy

**Decision:** Create comprehensive verification script with 8 checks

**Verification Checks:**
1. Table count (must be exactly 13)
2. Deprecated tables NOT present (user_conversation_state, donation_keypad_state)
3. ENUM types exist (4 types: currency_type, network_type, flow_type, type_type)
4. Index count (60+ indexes)
5. Foreign keys (3 foreign keys)
6. Sequences (5 sequences)
7. Currency data (87 rows in currency_to_network)
8. Legacy user (UUID 00000000-0000-0000-0000-000000000000)

**Exit Codes:**
- `0` - All checks passed (success)
- `1` - One or more checks failed (failure)

**Rationale:**
- **Automated Testing:** Verification script can be run in CI/CD pipelines
- **Confidence:** All checks must pass to confirm successful deployment
- **Debugging:** Failed checks clearly indicate what's wrong

**Alternative Considered:**
- **Manual Verification:** User manually checks schema using psql
  - **Rejected:** Error-prone, time-consuming, not automatable

### 7. Script Organization

**Decision:** Organize migration scripts in dedicated `/migrations/pgp-live/` subdirectory

**Directory Structure:**
```
TOOLS_SCRIPTS_TESTS/
├── migrations/
│   └── pgp-live/
│       ├── 001_pgp_live_complete_schema.sql
│       ├── 001_pgp_live_rollback.sql
│       ├── 002_pgp_live_populate_currency_to_network.sql
│       ├── 003_pgp_live_verify_schema.sql
│       ├── README_PGP_LIVE_MIGRATION.md
│       └── PGP_LIVE_SCHEMA_COMPARISON.md (moved to /THINK/AUTO/)
├── tools/
│   ├── deploy_pgp_live_schema.py
│   ├── verify_pgp_live_schema.py
│   └── rollback_pgp_live_schema.py
└── scripts/
    ├── deploy_pgp_live_schema.sh
    ├── verify_pgp_live_schema.sh
    └── rollback_pgp_live_schema.sh
```

**Rationale:**
- **Clarity:** pgp-live migration separate from telepay-459221 migration
- **Future Migrations:** Can create `/migrations/pgp-staging/` if needed
- **Consistency:** Follows existing TOOLS_SCRIPTS_TESTS structure

**Alternative Considered:**
- **Flat Structure:** All migrations in `/migrations/` root
  - **Rejected:** Hard to distinguish between different environments

### 8. Documentation Strategy

**Decision:** Create 2 comprehensive documentation files (1,054 lines total)

**Documents Created:**
1. **README_PGP_LIVE_MIGRATION.md** (627 lines)
   - Complete migration guide
   - Prerequisites checklist
   - Step-by-step deployment instructions
   - Troubleshooting guide
   - Service migration steps
   - Maintenance recommendations

2. **PGP_LIVE_SCHEMA_COMPARISON.md** (427 lines)
   - Executive summary (15 tables → 13 tables)
   - Detailed analysis of excluded tables
   - Infrastructure changes (project, instance, database)
   - Service name mapping (GC → PGP_v1)
   - Data migration implications
   - Compatibility matrix
   - Risk assessment

**Rationale:**
- **User Guidance:** README guides user through entire deployment process
- **Change Management:** Comparison report documents all differences
- **Troubleshooting:** Common issues documented with solutions
- **Knowledge Transfer:** Future team members can understand migration decisions

**Alternative Considered:**
- **Minimal Documentation:** Just README with basic instructions
  - **Rejected:** Insufficient for production deployment, no change tracking

---

## 2025-11-18: Tracking Files Archival Strategy 📋

**Decision:** Implement automated truncation system for PROGRESS.md, DECISIONS.md, and BUGS.md

**Context:**
- **Problem:** Files growing too large (1,769-2,542 lines) approaching token read limits
- **Risk:** File reads exceeding 25,000 token limit causing errors
- **Impact:** Slow operations, potential data loss if limits exceeded
- **User Requirement:** "Keep files at 35-40% of token window (~8,750-10,000 tokens)"

**Decision Rationale:**

### 1. Truncation Strategy - Line-Based with Session Boundaries

**Decision:** Truncate based on line counts while preserving complete session blocks

**Approach:**
- **PROGRESS.md:** Keep top 450 lines (~3,200 tokens, 13% of limit)
- **DECISIONS.md:** Keep top 500 lines (~3,600 tokens, 14% of limit)
- **BUGS.md:** Keep all if < 500 lines, else truncate to 200 lines

**Rationale:**
- **Predictable:** Line counts are easier to monitor than token counts
- **Safe:** Always cut at session markers (`## YYYY-MM-DD`), never mid-content
- **Conservative:** Target 35-40% leaves plenty of headroom
- **Simple:** Bash script can handle line-based operations efficiently

**Alternative Considered:**
- **Token-Based Truncation:** Count actual tokens, truncate at specific token threshold
  - **Rejected:** More complex to implement, harder to debug, overkill for current needs
  - **Future Enhancement:** May implement if line-based approach proves insufficient

### 2. Archive File Structure - Prepend New Content

**Decision:** Prepend newly archived content to TOP of archive files (newest first)

**Structure:**
```
PROGRESS_ARCH.md:
[Newly Archived - 2025-11-16 sessions]
[Previously Archived - Older sessions]
```

**Rationale:**
- **Consistency:** Matches main file structure (newest at top)
- **Accessibility:** Recent archived content easier to find
- **Grep-Friendly:** Searching for recent patterns faster
- **Natural Flow:** Reading chronologically from top makes sense

**Alternative Considered:**
- **Append to Bottom:** Add new archives at end of file
  - **Rejected:** Inconsistent with main file ordering, harder to find recent archives

### 3. Backup Strategy - Timestamped Backups

**Decision:** Create timestamped backup directory before every truncation

**Location:** `TOOLS_SCRIPTS_TESTS/logs/truncate_backup_YYYYMMDD_HHMMSS/`

**Rationale:**
- **Safety:** Can rollback if truncation goes wrong
- **Audit Trail:** Historical snapshots of file states
- **Non-Destructive:** Original content never lost
- **Disk Cost:** Minimal (text files compress well)

**Alternative Considered:**
- **Git Commits:** Rely on git history for backups
  - **Rejected:** Not all changes committed immediately, truncation may happen between commits

### 4. Automation Level - Manual Execution with Monitoring

**Decision:** Provide script for manual execution, NOT automatic cron job

**Rationale:**
- **User Control:** User decides when to truncate (not forced)
- **Inspection Opportunity:** User can review what will be archived before running
- **Low Frequency:** Files only need truncation every 4-6 weeks (not daily)
- **Flexibility:** User may want to keep certain sessions longer

**Trigger Threshold:**
- **Action Required:** When files exceed ~1,500 lines or 20,000 tokens
- **Monitoring:** User monitors file growth via `wc -l`
- **Frequency:** Approximately monthly for active projects

**Alternative Considered:**
- **Automatic Cron Job:** Run truncation weekly/monthly automatically
  - **Rejected:** Too aggressive, removes user agency, may archive content user still references

### 5. Content Retention Policy - Session-Based

**Decision:** Keep entire sessions, never truncate mid-session

**Policy:**
- **Minimum Kept:** Most recent 450-500 lines (last 2-4 weeks of work)
- **Session Integrity:** Always cut at `## YYYY-MM-DD` markers
- **Context Preservation:** If session spans 200 lines, keep entire session or archive entire session

**Rationale:**
- **Usability:** Partial sessions are confusing and break context
- **Searchability:** Complete sessions easier to understand in archives
- **Git-Friendly:** Session boundaries align with logical commit points

**Alternative Considered:**
- **Fixed Line Cuts:** Always cut at exactly line 450, regardless of content
  - **Rejected:** May split sessions, breaking narrative flow

---

## Implementation Details

**Script Features:**
1. ✅ Automatic backup creation before truncation
2. ✅ Line count statistics (before/after/archived)
3. ✅ Archive prepending (newest content at top)
4. ✅ Error handling (`set -e` exits on first error)
5. ✅ Idempotent (can run multiple times safely)

**Performance Impact:**
- **Before:** 32,900 tokens total across 3 files (high risk)
- **After:** 9,000 tokens total (13-14% of limit per file)
- **Improvement:** 73% reduction in token usage

**Maintenance:**
- **Frequency:** Run when files exceed 1,500 lines
- **Monitoring:** Check with `wc -l PROGRESS.md DECISIONS.md BUGS.md`
- **Archive Rotation:** Not implemented yet (archives can grow indefinitely)

**Future Enhancements:**
- Token-aware truncation (count actual tokens, not lines)
- Dynamic session boundary detection (no hardcoded line numbers)
- Archive rotation (split very large archive files)
- Dry-run mode (preview truncation without executing)

---

## 2025-01-18: Phase 2 Security - Load Balancer & Cloud Armor Architecture 🌐

**Decision:** Implement global HTTPS Load Balancer with Cloud Armor WAF protection WITHOUT VPC

**Context:**
- **Requirement:** Network-level security for external-facing Cloud Run services
- **User Constraint:** "We are choosing NOT to use VPC" (explicit requirement)
- **Services:** 3 external-facing services (web, NowPayments webhook, Telegram webhook)
- **Goals:** DDoS protection, WAF, rate limiting, SSL/TLS termination
- **Alternative Rejected:** VPC Service Controls (marked as "overkill for current scale")

**Architecture Decision:**

### 1. Load Balancer Type Selection

**Decision:** Use Google Cloud HTTP(S) Load Balancer (Global, External, Application Load Balancer)

**Rationale:**
- **Global Availability:** Single static IP accessible worldwide (anycast routing)
- **Cloud Armor Integration:** Required for WAF/DDoS protection
- **SSL/TLS Termination:** Free Google-managed certificates with auto-renewal
- **Path-Based Routing:** Route different paths to different Cloud Run services
- **Serverless Integration:** Native integration with Cloud Run via Serverless NEGs

**Alternative Considered:**
- **Regional Load Balancer:** Lower cost but no Cloud Armor support
  - **Rejected:** Cloud Armor is critical requirement for WAF/DDoS protection

### 2. No VPC Architecture

**Decision:** Deploy Load Balancer WITHOUT VPC networking components

**What We're NOT Using:**
- ❌ VPC Connector (not needed - Load Balancer connects directly to Cloud Run via Serverless NEGs)
- ❌ VPC Service Controls (explicitly rejected as "overkill")
- ❌ Cloud NAT (not needed - Cloud Run has dynamic egress IPs, HMAC used for authentication)
- ❌ Shared VPC (not needed - single project architecture)

**What We ARE Using:**
- ✅ **Serverless NEGs** - Connect Load Balancer to Cloud Run without VPC
- ✅ **Cloud Armor** - Network security at Load Balancer layer (replaces VPC-SC for our use case)
- ✅ **IAM Authentication** - Service-to-service authentication (no VPC needed)
- ✅ **HMAC Verification** - Application-level security (already implemented)

**Rationale:**
- **Cost Savings:** VPC Connector (~$0.30-0.50/hour = ~$216-360/month) avoided
- **Simplicity:** No VPC management overhead
- **Sufficient Security:** Cloud Armor + IAM + HMAC provide adequate defense in depth
- **User Requirement:** Explicit decision to avoid VPC complexity

**Alternative Considered:**
- **VPC with Cloud NAT:** Static egress IPs for IP whitelisting
  - **Rejected:** HMAC authentication is more secure and already implemented

### 3. Path-Based Routing Strategy

**Decision:** Use URL Map with path-based routing to distribute traffic to 3 services

**Routing Configuration:**
- `/` → `pgp-web-v1` (Frontend - React SPA)
- `/webhooks/nowpayments-ipn` → `pgp-np-ipn-v1` (NowPayments IPN webhook)
- `/webhooks/telegram` → `pgp-server-v1` (Telegram Bot webhook)

**Rationale:**
- **Single Domain:** All services accessible via single domain (e.g., paygateprime.com)
- **Single SSL Certificate:** One certificate covers all paths (cost savings)
- **Clear Separation:** Webhook paths clearly separated from frontend
- **Security:** Different Cloud Armor rules can be applied per path (if needed)

**Alternative Considered:**
- **Host-Based Routing:** Separate subdomains (e.g., api.paygateprime.com, webhooks.paygateprime.com)
  - **Rejected:** More complex DNS configuration, multiple SSL certificates needed

### 4. Cloud Armor Security Policy Configuration

**Decision:** Single security policy with layered rules (IP whitelist + rate limiting + WAF)

**Rules Implemented:**

**4.1 IP Whitelisting (Priority 1000-1100):**
- **NowPayments IPs (Priority 1000):**
  - `193.233.22.4/32` (Server 1)
  - `193.233.22.5/32` (Server 2)
  - `185.136.165.122/32` (Server 3)
  - Source: https://nowpayments.io/help/ipn-callback-ip-addresses
- **Telegram IPs (Priority 1100):**
  - `149.154.160.0/20` (DC1)
  - `91.108.4.0/22` (DC2)
  - Source: https://core.telegram.org/bots/webhooks

**4.2 Rate Limiting (Priority 2000):**
- **Threshold:** 100 requests/minute per IP
- **Action:** Ban for 10 minutes (HTTP 429 response)
- **Enforcement:** Per-IP tracking

**4.3 OWASP Top 10 WAF Rules (Priority 3000-3900):**
- SQL Injection (SQLi) - Priority 3000
- Cross-Site Scripting (XSS) - Priority 3100
- Local File Inclusion (LFI) - Priority 3200
- Remote Code Execution (RCE) - Priority 3300
- Remote File Inclusion (RFI) - Priority 3400
- Method Enforcement - Priority 3500
- Scanner Detection - Priority 3600
- Protocol Attack - Priority 3700
- PHP Injection - Priority 3800
- Session Fixation - Priority 3900

**4.4 Adaptive Protection:**
- **ML-Based DDoS Detection:** Enabled (if available in project)
- **Layer 7 DDoS Defense:** Automatic detection and mitigation

**4.5 Default Rule:**
- **Action:** ALLOW (specific denies via WAF rules above)
- **Rationale:** WAF rules deny specific attack patterns, legitimate traffic allowed

**Rationale:**
- **Defense in Depth:** Multiple security layers (IP whitelist → rate limit → WAF → IAM → HMAC)
- **PCI DSS Compliance:** WAF rules required for payment processing
- **DDoS Protection:** Rate limiting + Adaptive Protection
- **IP Whitelist as Backup:** HMAC is primary authentication, IP whitelist is secondary

**Alternative Considered:**
- **Default Deny:** Block all traffic except whitelisted IPs
  - **Rejected:** Too restrictive for frontend (pgp-web-v1 needs public access)

### 5. SSL/TLS Certificate Strategy

**Decision:** Use Google-managed SSL certificates (FREE, automatic renewal)

**Rationale:**
- **Cost:** FREE (vs $50-300/year for commercial certificates)
- **Automatic Renewal:** No manual intervention required (30 days before expiration)
- **Simplicity:** No private key management
- **Reliability:** Google handles certificate lifecycle

**Limitations Accepted:**
- **Provisioning Time:** 10-60 minutes (DNS verification required)
- **Domain Validation Only:** No EV or OV certificates (acceptable for our use case)
- **No Wildcard Support:** Must specify exact domains (acceptable - we know our domains)

**Alternative Considered:**
- **Self-Managed Certificates (Let's Encrypt):** FREE but requires manual renewal
  - **Rejected:** Google-managed is simpler and equally secure

### 6. Serverless NEG Configuration

**Decision:** Create 3 Serverless NEGs (one per Cloud Run service) in us-central1 region

**NEG Configuration:**
- **Type:** SERVERLESS (for Cloud Run)
- **Region:** us-central1 (must match Cloud Run service region)
- **Binding:** One NEG per Cloud Run service

**Rationale:**
- **Automatic Scaling:** NEGs automatically update when Cloud Run scales
- **Regional Deployment:** No global replication needed (all users route to us-central1)
- **Simplicity:** Direct Cloud Run integration without VPC

**Alternative Considered:**
- **Multi-Region Deployment:** NEGs in multiple regions for lower latency
  - **Deferred:** Single region sufficient for current scale, can add later

### 7. Cloud Run Ingress Restriction

**Decision:** Update Cloud Run services to `--ingress=internal-and-cloud-load-balancing`

**Impact:**
- **Before:** Cloud Run services publicly accessible (vulnerable)
- **After:** Cloud Run services ONLY accessible via Load Balancer

**Rationale:**
- **Security:** Prevents direct access to Cloud Run URLs
- **Enforcement:** All traffic must go through Load Balancer → Cloud Armor → Cloud Run
- **Defense in Depth:** Even if Load Balancer is bypassed, Cloud Run denies direct traffic

**Alternative Considered:**
- **Keep Public Access:** Rely on HMAC only
  - **Rejected:** Violates defense-in-depth principle

### 8. Cost Optimization Decisions

**Decision:** Use Cloud Armor "Smart" pricing tier (not "Standard")

**Cost Breakdown:**
- **Load Balancer Forwarding Rule:** $18/month (fixed)
- **Data Processing:** $0.008-0.016/GB (traffic-dependent)
- **Cloud Armor Rules:** $1/month per rule after first 5 FREE (we have 15 = $10/month)
- **Cloud Armor Requests:** $0.75 per 1M after first 1M FREE
- **SSL Certificate:** FREE (Google-managed)
- **Total Estimated:** ~$60-200/month

**Cost Savings vs VPC Approach:**
- **VPC Connector:** ~$216-360/month SAVED
- **Cloud NAT:** ~$0/month (not needed)
- **Total Savings:** ~$216-360/month

**Rationale:**
- **ROI:** Cloud Armor provides better security than VPC alone
- **Scalability:** Costs scale with traffic (pay for what you use)
- **Predictability:** Base cost ($28/month) is fixed

### 9. Logging and Monitoring Strategy

**Decision:** Enable verbose logging in Cloud Armor, use Cloud Logging for monitoring

**Logging Configuration:**
- **Log Level:** VERBOSE (all security events logged)
- **Destination:** Cloud Logging (http_load_balancer resource)
- **Retention:** Default (30 days)

**Monitoring Approach:**
- **Blocked Requests:** Monitor Cloud Armor deny events
- **Rate Limiting:** Track HTTP 429 responses
- **WAF Triggers:** Track OWASP rule matches
- **Alerting:** Manual setup post-deployment (optional)

**Rationale:**
- **Security Visibility:** All attacks logged and visible
- **Incident Response:** Logs available for forensic analysis
- **Compliance:** PCI DSS requires logging of security events

**Alternative Considered:**
- **Sampling (10%):** Reduce logging costs
  - **Rejected:** Security events should always be logged (compliance requirement)

---

## 2025-01-18: Security Architecture - IAM Authentication & Defense in Depth 🔒

**Decision:** Remove `--allow-unauthenticated` and implement multi-layered security architecture with IAM authentication

**Context:**
- **Critical Vulnerability:** All 17 Cloud Run services deployed with `--allow-unauthenticated` flag
- **Risk:** Payment webhooks handling sensitive financial data accessible without authentication
- **Requirement:** PCI DSS compliance for payment processing
- **Constraint:** Services must communicate with each other (service-to-service calls)

**Architecture Decision:**

### 1. Service Classification & Authentication Strategy

**Decision:** Classify services into 3 categories with different authentication requirements:

**🌐 Public Services (1 service):**
- `pgp-web-v1` - Frontend web application
- **Authentication:** `--allow-unauthenticated` (users need direct access)
- **Protection:** Cloud Armor (Phase 2) for DDoS protection, rate limiting

**🔒 Authenticated Webhooks (2 services):**
- `pgp-np-ipn-v1` - NowPayments IPN webhook
- `pgp-server-v1` - Telegram Bot webhook
- **Authentication:** `--no-allow-unauthenticated` (require auth)
- **Access Method:** Via Cloud Load Balancer + Cloud Armor (Phase 2)
- **Protection:** IP whitelist (NowPayments IPs, Telegram IPs), HMAC signature verification

**🔐 Internal Services (14 services):**
- All other services (orchestrator, split, hostpay, batch, notifications, etc.)
- **Authentication:** `--no-allow-unauthenticated` (require IAM)
- **Access Method:** Service-to-service with identity tokens
- **Protection:** IAM roles/run.invoker permissions

**Rationale:**
- **Defense in Depth:** Multiple security layers (HTTPS, Load Balancer, Cloud Armor, IAM, HMAC)
- **Least Privilege:** Only frontend is public, webhooks protected by Load Balancer, internals require IAM
- **PCI DSS Compliance:** Payment data protected by authentication at multiple layers

**Alternative Considered:**
- **All Public with HMAC-only:** `--allow-unauthenticated` for all services, rely on HMAC
  - **Rejected:** Single point of failure, no defense in depth, violates PCI DSS

### 2. Service Account Architecture

**Decision:** Create 17 dedicated service accounts (one per service) with minimal IAM permissions

**Service Account Naming Convention:**
- Pattern: `{service-name}-sa@{project-id}.iam.gserviceaccount.com`
- Example: `pgp-server-v1-sa@pgp-live.iam.gserviceaccount.com`

**Minimal Permissions Granted:**
- `roles/cloudsql.client` - All services (database access)
- `roles/secretmanager.secretAccessor` - All services (secret access)
- `roles/cloudtasks.enqueuer` - Services that send tasks (orchestrator, split, hostpay, etc.)
- `roles/logging.logWriter` - All services (logging)
- `roles/run.invoker` - Per-service basis (configured via configure_invoker_permissions.sh)

**Rationale:**
- **Least Privilege:** Each service only has permissions it needs
- **Audit Trail:** Each service's actions traceable via service account
- **Security:** Compromised service cannot access resources outside its scope
- **Best Practice:** Google Cloud Run security best practices

**Alternative Considered:**
- **Single Shared Service Account:** One service account for all 17 services
  - **Rejected:** Violates least privilege, no per-service audit trail, security risk

### 3. Service-to-Service Authentication Implementation

**Decision:** Use Google Cloud IAM identity tokens for service-to-service authentication

**Implementation:**
- **Module:** `/PGP_COMMON/auth/service_auth.py`
- **Helper Function:** `call_authenticated_service(url, method, json_data, timeout)`
- **Authentication Method:** Compute Engine ID tokens via `google.auth.compute_engine.IDTokenCredentials`
- **Token Caching:** Per-target-audience caching to minimize token generation overhead

**Code Pattern:**
```python
# Before (INSECURE)
response = requests.post(orchestrator_url, json=payload)

# After (SECURE)
from PGP_COMMON.auth import call_authenticated_service
response = call_authenticated_service(
    url=orchestrator_url,
    method="POST",
    json_data=payload
)
```

**Rationale:**
- **Security:** IAM identity tokens verified by Cloud Run automatically
- **Simplicity:** Single helper function replaces all `requests.post()` calls
- **Performance:** Token caching reduces overhead
- **Best Practice:** Recommended by Google Cloud for Cloud Run → Cloud Run authentication

**Alternative Considered:**
- **Shared Secret (Bearer Token):** Static shared secret between services
  - **Rejected:** Secret rotation difficult, no automatic verification, less secure than IAM

### 4. Cloud Tasks with OIDC Tokens

**Decision:** Update Cloud Tasks to use OIDC tokens for authenticated task delivery

**Implementation:**
```python
task = {
    'http_request': {
        'http_method': tasks_v2.HttpMethod.POST,
        'url': target_url,
        'oidc_token': {
            'service_account_email': 'pgp-orchestrator-v1-sa@pgp-live.iam.gserviceaccount.com',
            'audience': target_url
        }
    }
}
```

**Rationale:**
- **Consistency:** Same authentication method as direct service-to-service calls
- **Security:** OIDC tokens verified by Cloud Run automatically
- **Best Practice:** Recommended for authenticated Cloud Tasks

**Alternative Considered:**
- **HTTP Basic Auth:** Username/password in Cloud Tasks
  - **Rejected:** Less secure than OIDC, requires secret management

### 5. Deployment Script Architecture

**Decision:** Extend `deploy_service()` function with authentication and service account parameters

**New Parameters:**
- `AUTHENTICATION` - "require" or "allow-unauthenticated" (default: "require")
- `SERVICE_ACCOUNT` - Service account email (optional)

**Implementation:**
- Color-coded authentication status display (Green for authenticated, Yellow for public)
- Clear documentation in deployment script comments
- Per-service authentication configuration

**Rationale:**
- **Clarity:** Explicit authentication requirement for each service
- **Safety:** Default to "require" (secure by default)
- **Flexibility:** Can override for specific services (e.g., frontend)
- **Maintainability:** Single deployment script for all services

**Alternative Considered:**
- **Separate Deployment Scripts:** One script for authenticated, one for public
  - **Rejected:** Code duplication, harder to maintain

### 6. Script Organization

**Decision:** Create separate scripts for each security configuration step

**Scripts Created:**
1. `create_service_accounts.sh` - Create all 17 service accounts
2. `grant_iam_permissions.sh` - Grant minimal IAM permissions
3. `configure_invoker_permissions.sh` - Configure service-to-service permissions
4. `deploy_all_pgp_services.sh` (modified) - Deploy with authentication

**Execution Order:**
1. Create service accounts
2. Grant IAM permissions
3. Deploy services
4. Configure invoker permissions (after deployment)

**Rationale:**
- **Separation of Concerns:** Each script has single responsibility
- **Idempotency:** Scripts can be re-run safely (check if resources exist)
- **Debugging:** Easy to identify which step failed
- **Rollback:** Can rollback individual steps if needed

**Alternative Considered:**
- **Monolithic Script:** Single script doing all steps
  - **Rejected:** Hard to debug, no granular rollback, poor separation of concerns

---

## 2025-11-18: Hot-Reload Secret Management Implementation Strategy 🔄

**Decision:** Implement hot-reloadable secrets using Secret Manager API for 43 approved secrets while keeping 3 security-critical secrets static

**Context:**
- Current architecture: All secrets loaded once at container startup via environment variables
- Problem: Secret rotation requires service restart (downtime for users)
- Need: Zero-downtime API key rotation, blue-green deployments, queue migrations
- Security constraint: Private keys (wallet, JWT signing, HMAC signing) MUST NEVER be hot-reloadable

**Architecture Decision:**

### 1. Dual-Method Secret Fetching Pattern

**Decision:** Implement two separate methods in BaseConfigManager:
- `fetch_secret()` - STATIC secrets from environment variables (os.getenv)
- `fetch_secret_dynamic()` - HOT-RELOADABLE secrets from Secret Manager API

**Rationale:**
- **Clarity:** Explicit distinction between static and dynamic secrets
- **Security:** Impossible to accidentally make private keys hot-reloadable (different method)
- **Performance:** Static secrets cached at startup, dynamic secrets request-level cached
- **Backward Compatibility:** Existing `fetch_secret()` unchanged, new method added

**Alternative Considered:**
- **Single Method with Flag:** `fetch_secret(name, hot_reload=False)`
  - **Rejected:** Too easy to accidentally flip flag, less explicit, security risk

### 2. Request-Level Caching Strategy

**Decision:** Implement request-level caching using Flask `g` context object

**Rationale:**
- **Cost Optimization:** Without caching, every API call = Secret Manager API call (~$75/month vs $7.50/month)
- **Performance:** Single Secret Manager fetch per request (<5ms latency increase)
- **Simplicity:** Flask `g` automatically cleared between requests, no manual cache invalidation
- **Safety:** Cache never stale beyond single request (hot-reload still effective)

**Alternative Considered:**
- **Time-Based Caching (TTL):** Cache secrets for 60 seconds
  - **Rejected:** Defeats purpose of hot-reload (secrets not immediately effective)
- **No Caching:** Fetch from Secret Manager on every usage
  - **Rejected:** Too expensive ($75/month), too slow (>50ms per request)

### 3. Security-Critical Secrets Classification

**Decision:** Three secrets NEVER hot-reloadable (enforced via architecture):
- `HOST_WALLET_PRIVATE_KEY` - Ethereum wallet private key (PGP_HOSTPAY3_v1)
- `SUCCESS_URL_SIGNING_KEY` - JWT signing key (PGP_ORCHESTRATOR_v1)
- `TPS_HOSTPAY_SIGNING_KEY` - HMAC signing key (PGP_SERVER_v1, PGP_HOSTPAY1_v1)

**Rationale:**
- **Security:** Changing signing keys mid-flight breaks all active sessions/tokens
- **Correctness:** Private key rotation requires careful wallet migration (not instant)
- **Auditability:** Static secrets easier to audit (logged once at startup, not per-request)
- **Compliance:** Private key access must be logged and monitored (startup only)

**Enforcement:**
- Only use `fetch_secret()` (static method) for these secrets
- Add docstring warnings in config managers
- Security audit via Cloud Audit Logs (verify NEVER accessed during requests)

### 4. Pilot Service Strategy

**Decision:** Implement PGP_SPLIT2_v1 as pilot service before rolling out to all 17 services

**Rationale:**
- **Risk Mitigation:** Test hot-reload on non-critical service first
- **Learning:** Identify issues before touching security-critical services
- **Pattern Validation:** Validate implementation pattern works correctly
- **Confidence Building:** Monitor for 48 hours before proceeding

**Pilot Service Selection Rationale (PGP_SPLIT2_v1):**
- ✅ Uses hot-reloadable secret (CHANGENOW_API_KEY)
- ✅ Uses queue names and service URLs
- ✅ No security-critical secrets (SUCCESS_URL_SIGNING_KEY is static)
- ✅ Medium traffic volume (good test case)
- ✅ Easy to rollback (not in critical path)

### 5. Implementation Pattern for Client Classes

**Decision:** Pass `config_manager` reference to client classes instead of secret values

