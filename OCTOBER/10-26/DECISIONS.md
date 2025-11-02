# Architectural Decisions - TelegramFunnel OCTOBER/10-26

**Last Updated:** 2025-11-01 (Archived previous entries to DECISIONS_ARCH.md)

This document records all significant architectural decisions made during the development of the TelegramFunnel payment system.

---

## Table of Contents
1. [Service Architecture](#service-architecture)
2. [Cloud Infrastructure](#cloud-infrastructure)
3. [Data Flow & Orchestration](#data-flow--orchestration)
4. [Security & Authentication](#security--authentication)
5. [Database Design](#database-design)
6. [Error Handling & Resilience](#error-handling--resilience)
7. [User Interface](#user-interface)

---

## Recent Decisions

### 2025-11-02: Micro-Batch Processor Schedule Optimization

**Decision:** Reduced micro-batch-conversion-job scheduler interval from 15 minutes to 5 minutes

**Rationale:**
- Faster threshold detection for accumulated payments
- Improved payout latency for users (3x faster threshold checks)
- Aligns with batch-processor-job interval (also 5 minutes)
- No functional changes to service logic - only scheduling frequency

**Impact:**
- Threshold checks now occur every 5 minutes instead of 15 minutes
- Maximum wait time for threshold detection reduced from 15 min to 5 min
- Expected payout completion time reduced by up to 10 minutes
- Minimal increase in Cloud Scheduler API calls (cost negligible)

**Configuration:**
```
Schedule: */5 * * * * (Etc/UTC)
Target: https://gcmicrobatchprocessor-10-26-291176869049.us-central1.run.app/check-threshold
State: ENABLED
```

---

## Notes
- All previous architectural decisions have been archived to DECISIONS_ARCH.md
- This file tracks only the most recent architectural decisions
- Add new decisions at the TOP of the document
