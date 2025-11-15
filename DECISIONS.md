# Architectural Decisions Log

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
