# Roadmap: Investment Agent

## Milestones

- ✅ **v1.0 Competitive Parity** — Phases 1-4 (shipped 2026-04-22)
- ✅ **v1.1 Live Validation** — Phases 5-7 (shipped 2026-04-25)
- 📋 **v1.2 (TBD)** — not yet scoped (run `/gsd-new-milestone` to define)

## Phases

<details>
<summary>✅ v1.0 Competitive Parity (Phases 1-4) — SHIPPED 2026-04-22</summary>

- [x] Phase 1: Foundation Hardening (3/3 plans) — completed 2026-04-22
- [x] Phase 2: Signal Quality Upgrade (3/3 plans) — completed 2026-04-22
- [x] Phase 3: Data Coverage Expansion (4/4 plans) — completed 2026-04-22
- [x] Phase 4: Portfolio UI + Analytics Uplift (4/4 plans) — completed 2026-04-22

Full snapshot: `.planning/milestones/v1.0-ROADMAP.md` · Requirements: `.planning/milestones/v1.0-REQUIREMENTS.md`

</details>

<details>
<summary>✅ v1.1 Live Validation (Phases 5-7) — SHIPPED 2026-04-25</summary>

- [x] Phase 5: Corpus Population + Live Data Closeout (2/2 plans) — completed 2026-04-23
- [x] Phase 6: Calibration & Weights UI (3/3 plans) — completed 2026-04-24
- [x] Phase 7: Digest + Analytics Completeness (3/3 plans) — completed 2026-04-25

Full snapshot: `.planning/milestones/v1.1-ROADMAP.md` · Requirements: `.planning/milestones/v1.1-REQUIREMENTS.md`

</details>

### 📋 v1.2 (Planned)

To be scoped via `/gsd-new-milestone`. Candidate themes carried forward from v1.1 retrospective and v2 placeholder list:

- **Deployment story:** Docker + docker-compose (DEPLOY-v2-01), OpenTelemetry/Prometheus (DEPLOY-v2-02), `pandas-ta-classic` migration (DEPLOY-v2-03)
- **UX depth:** Allocation donuts (UI-v2-01), CSV import wizard (UI-v2-02), alert-threshold UI (UI-v2-03), Riskfolio-Lib position sizing (UI-v2-04), QuantStats tearsheet (UI-v2-05)
- **Signal Quality v2:** Calibration reliability plots (SIG-v2-01), regime-conditioned adaptive RSI (SIG-v2-02), trade-shuffle Monte Carlo (SIG-v2-03)
- **Data Coverage v2:** MarketAux news + sentiment (DATA-v2-01), SimFin point-in-time fundamentals (DATA-v2-02), CoinGecko on-chain (DATA-v2-03)
- **v1.1 research flag:** Validate drift-detector thresholds (`>20%` IC-IR drop / `<0.5` floor) against the populated live corpus before promoting them out of "preliminary" status.

## Progress

| Phase | Milestone | Plans Complete | Status   | Completed  |
|-------|-----------|----------------|----------|------------|
| 1. Foundation Hardening                   | v1.0 | 3/3 | Complete | 2026-04-22 |
| 2. Signal Quality Upgrade                 | v1.0 | 3/3 | Complete | 2026-04-22 |
| 3. Data Coverage Expansion                | v1.0 | 4/4 | Complete | 2026-04-22 |
| 4. Portfolio UI + Analytics Uplift        | v1.0 | 4/4 | Complete | 2026-04-22 |
| 5. Corpus Population + Live Data Closeout | v1.1 | 2/2 | Complete | 2026-04-23 |
| 6. Calibration & Weights UI               | v1.1 | 3/3 | Complete | 2026-04-24 |
| 7. Digest + Analytics Completeness        | v1.1 | 3/3 | Complete | 2026-04-25 |
