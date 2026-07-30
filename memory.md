# Project Memory / Decision Log

Running log of notable changes and decisions made during development, for context that isn't obvious from the code alone. See also `BUSINESS_RULE_ASSUMPTIONS.md` for business-rule assumptions specifically.

## 2026-07-30 — Compact UI layout

Tightened spacing across the whole frontend (header, hero section, sidebar form, and result cards) because the page required too much scrolling — 5 recommendation cards plus the full brief form didn't fit on a normal screen.

**What changed:**
- `frontend/src/components/Field.jsx` — reduced label/field margins (`mb-5`→`mb-3`, etc.)
- `frontend/src/App.jsx` — smaller header bar, hero heading, section titles, and grid gaps throughout
- `frontend/src/components/RecommendationCard.jsx` — smaller card padding, product row height, and text sizes
- `frontend/src/index.css` — reduced `.input` and `.pill` padding

**Result:** measured via a real headless-browser render (Playwright) — page height dropped from 1855px to 1254px (~32% shorter) at the same viewport (1400×1000), with no visual regressions. 5 options now mostly fit without scrolling on a normal screen.

**Why this approach:** rather than removing content or collapsing cards, every spacing/font-size value was proportionally reduced so the existing design language (colors, card structure, badges) stayed intact — just denser.
