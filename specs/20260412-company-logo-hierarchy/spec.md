# Company Logo and Service Hierarchy — Feature Specification

**Feature**: Company Logo Support and Enriched Company/ServiceType Hierarchy
**Date**: 2026-04-12
**Status**: Draft

---

## Overview

The system currently stores payment providers as flat `services` records with a `name` and `service_type` text field. This change request restructures the data model to introduce a formal **Company** entity (with a logo) and a **ServiceType** entity that sits between Company and the existing Accounts and CommissionTiers. Each Company may operate both Pay and Bank divisions; each division exposes named ServiceTypes (e.g. WST, Pay_To_Pay) that carry their own Accounts and CommissionTiers.

---

## Business Context

The shop handles transactions with these payment companies:

| Company | Division | Service Types |
|---|---|---|
| KBZ Pay | Pay | WST, Pay_To_Pay |
| Wave Money | Pay | WST, Pay_To_Pay |
| True Money | Pay | WST, Pay_To_Pay |
| KBZ Bank | Bank | Transfer, Exchange |
| AYA Bank | Bank | Transfer, Exchange |
| CB Bank | Bank | Transfer, Exchange |

Transfer/Exchange transactions may involve both a Pay company and a Bank company (cross-company flow): the customer pays in via KBZ Bank, AYA Bank, or Wave Money, and the shop pays out via K Pay, AYA Bank, or Wave Money.

---

## Functional Requirements

### FR-01 Company Entity
- A **Company** record has: `id`, `name`, `logo_path` (local file path or embedded blob), `category` (Pay | Bank | Both), `is_active`, `created_at`, `updated_at`.
- The five seeded companies are: KBZ Pay, Wave Money, True Money, KBZ Bank, AYA Bank, CB Bank.
- Each company must have exactly one logo image. Supported formats: PNG, JPG, SVG (displayed at 32×32 px in lists, 64×64 px in detail headers).

### FR-02 ServiceType Entity
- A **ServiceType** record has: `id`, `company_id` (FK → companies), `name` (e.g. "WST", "Pay_To_Pay", "Transfer", "Exchange"), `operation` (Deposit | Withdraw | Transfer | Exchange | All), `is_active`, `created_at`, `updated_at`.
- ServiceType replaces the current `service_type` text column used in `accounts` and `commission_tiers`.

### FR-03 Account Linkage
- `accounts.service_type_id` (INTEGER FK → service_types) replaces the existing `accounts.service_type` TEXT column.
- Existing accounts must be migrated to the new FK.

### FR-04 CommissionTier Linkage
- `commission_tiers.service_type_id` (INTEGER FK → service_types) replaces the existing `commission_tiers.service_type` TEXT column.
- Existing tier rows must be migrated.

### FR-05 Logo Management (Owner only)
- Owner can upload/replace a company logo via the Settings panel.
- Logo is stored in a local `assets/logos/` directory on the server host, referenced by relative path in the DB.
- The client fetches logo images via a new REST endpoint: `GET /companies/{id}/logo`.

### FR-06 Company & ServiceType CRUD (Owner only)
- Owner can create, edit, deactivate a Company.
- Owner can create, edit, deactivate a ServiceType under a Company.
- Deactivating a Company deactivates all its ServiceTypes and prevents new transactions on linked accounts.

### FR-07 Transfer/Exchange Cross-Company Flow
- A Transfer or Exchange transaction supports:
  - `from_company_id` + `from_account_id` (customer pays in via this company/account)
  - `to_company_id` + `to_account_id` (shop pays out via this company/account)
- The UI pre-filters account dropdowns based on selected company.

### FR-08 UI — Company Selector with Logo
- Anywhere a service/account is selected, the UI now shows the company logo alongside the company name.
- The transaction form shows two company selectors for Transfer/Exchange (payer company and payee company).

---

## Non-Functional Requirements

- **NFR-01 Backward Compatibility**: Migration script upgrades the existing SQLite DB in-place; no data loss.
- **NFR-02 Performance**: Logo images are cached client-side for the session; no repeated HTTP requests per transaction.
- **NFR-03 File Size**: Logo files must be ≤ 200 KB each.
- **NFR-04 Offline Fallback**: If logo cannot be loaded, show a colored initial-letter placeholder.
- **NFR-05 Packaging**: Logo assets must be bundled into the server PyInstaller package under `assets/logos/`.

---

## Success Criteria

1. Each Company record is displayed with its logo in the account selection dropdowns.
2. ServiceType records link correctly to CommissionTier lookups; tier fee calculation continues to work.
3. Transfer/Exchange form correctly selects source (customer's) company/account and destination (shop's) company/account.
4. All existing transactions remain readable and correctly associated after migration.
5. Owner can upload a new logo and it appears in the client UI within one session refresh (30 s auto-refresh cycle).

---

## Out of Scope

- Multi-currency logo variants.
- Logo CDN / remote hosting.
- Mobile client.
