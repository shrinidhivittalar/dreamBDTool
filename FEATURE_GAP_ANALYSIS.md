# Dream a Dozen — Feature Gap Analysis

A product-completeness audit: not "are there bugs," but "does this do what a
real user of a corporate-gifting/snack-box tool would expect, and where it
doesn't, how much does that actually cost us." Living document — grows as
we go deeper.

## 1. What currently works (the genuinely-wired core loop)

- **Catalog ingestion**: real daily HTTP pull from a Zoho WorkDrive sheet
  (`backend/data_provider.py`), with an atomic on-disk cache, graceful
  fallback to last-known-good data on failure, and manual "pull now" /
  "upload catalog" escape hatches. Failure/staleness is surfaced via
  `/api/products/status`, not hidden.
- **Recommendation engine**: real combinatorial search
  (`recommender.py` + `recommender_search/_constraints/_ranking/_diversity`),
  not mock data — mandatory/excluded/required-category constraints, budget
  scoring, diversity selection, and an item-count sweep when count is
  unspecified.
- **Export**: real CSV, real XLSX (openpyxl), and a hand-rolled real PDF
  writer, in two layouts (summary / itemized), wired to actual download
  buttons.
- **Business rules / validation / pricing**: packaging rules, a dedicated
  validator that checks every generated recommendation against the
  request before it's shown, and GST-free flat pricing — all real logic,
  not decorative.

This is a genuinely-functioning recommendation-and-export tool. The gap
list below is about what's missing *around* that core, not about the core
being fake.

## 2. The weakest / stub spots found in the codebase

| Area | Status | Evidence |
|---|---|---|
| Persistence | **Absent** | No DB anywhere. `ProductDataProvider._products` is in-process memory repopulated from file cache on restart. Frontend state (`recommendations`, `lastBrief`) lives only in React `useState` — a page refresh discards everything. No "saved boxes," no brief history, no user accounts. |
| Ordering / checkout / payment | **Absent** | No cart, checkout, order, or payment code anywhere (verified by full-repo grep). The app stops at "here are your recommendations" + an export download. |
| Auth / authorization | **Absent** | No login, session, JWT, or user model. Every endpoint — including catalog upload/refresh — is unauthenticated. No admin-vs-regular-user distinction. |
| Multi-user / team workflows | **Absent** | No sharing, approval flow, or commenting. The only way to hand a box to a colleague is manually emailing the exported file. |
| NL intent parser | **Partially wired** | `intent_parser.py` is pure regex/keyword matching, not an LLM call. Budget parsing recognizes only a few fixed phrasings and silently defaults to ₹1000 if no number is found at all; item count is clamped 1–10; category detection is a fixed 3-word-bucket list. It *looks* like a smart free-text box but is a thin deterministic parser underneath. |
| Frontend result interaction | **Absent** | No client-side sort/filter/search once recommendations are returned — just two export buttons. |
| Error/loading UX | **Partially wired** | Loading state is real (disabled buttons, relabeled text) but errors are a single plain-text banner with no retry action and no differentiation between "bad input," "network down," and "no results." |
| Product management | **Absent (all-or-nothing)** | No way to edit one product's price/category — only full catalog re-upload or re-pull. |
| Analytics / admin dashboard | **Absent** | No tracking, no usage reporting, no admin view of what's been generated/exported. |
| Accessibility | **Partially wired** | Responsive Tailwind breakpoints exist; no `aria-*`/`role` attributes or focus management found anywhere. |

## 3. Why the top gaps are the most damaging

**Persistence (or the lack of it) is the single most trust-corroding gap.**
Walk the causal chain: a user — likely someone building a gifting order for
a company event — spends several minutes tuning a brief (budget, item
count, mandatory items, exclusions), gets a set of boxes back, and then
either accidentally refreshes the tab, closes it to check something else,
or the browser session simply times out. Everything is gone. There is no
"my recent briefs," no "boxes I liked," nothing to come back to. For a
tool whose entire value proposition is "help me curate a good box without
re-doing the work," losing all state on a refresh directly contradicts
that value proposition. A user's mental model of *any* form-driven web app
in 2026 is "my work is safe unless I explicitly discard it" — this app
violates that silently, with no warning before the data disappears.

**No path from recommendation to order is the second most damaging gap,
because it caps what the product can ever be mistaken for.** Every
competitor researched (Sendoso, Snappy, PerkUp, Loop & Tie, Bond) treats
"pick a gift" as step one of a pipeline that continues through checkout,
fulfillment, shipping, and delivery tracking — that whole pipeline is the
product. Dream a Dozen currently ends at "here's a spreadsheet of what you
should buy." That's a legitimate internal tool, but it means a user who
expects a gifting *platform* (because that's the category this competes
in) will hit a dead end and have to go execute the actual purchase/dispatch
by hand, outside the tool, with no record loop back in. This isn't a
missing feature so much as a missing half of the product category.

**No auth is the gap most likely to cause a concrete incident, not just
disappointment.** Every endpoint, including the ones that overwrite the
entire product catalog (`/api/products/upload`, `/api/products/refresh`),
is open to anyone who can reach the API — there's no way to know who
changed the catalog, restrict who's allowed to, or even attribute
recommendations to a requester for later audit. In a real deployment
(anyone other than the developer poking at localhost) this is the gap
most likely to produce a "wait, who changed the catalog / who requested
this?" moment with no answer, because nothing is logged against an
identity.

## 4. Additional gaps found via industry research

Benchmarked against Sendoso, PerkUp, Snappy, GiftTree, Loop & Tie, and Bond
— the closest real "corporate gifting platform" comparables:

- **Order tracking / fulfillment status.** Competitor platforms surface
  real-time shipment tracking (FedEx/UPS/USPS events) directly in-app once
  a gift ships. Dream a Dozen has no concept of "shipped," "delivered," or
  even "ordered" at all — consistent with gap #2 above, but worth naming
  as the specific *feature* the category expects, not just "checkout in
  general." ([Top 15 Corporate Gifting Platforms of 2026](https://perkupapp.com/post/top-corporate-gifting-platforms), [Gift Tracking Software for Corporate Programs](https://imprintengine.com/blog/gift-tracking-software-for-corporate-programs/))
- **Per-department / per-campaign budget controls with approval
  workflows.** Enterprise-grade platforms (Sendoso in particular) build
  the *product* around "requester picks, approver signs off before
  anything ships," with configurable spend limits per team or recipient
  group. Dream a Dozen has a single-shot budget range per request with no
  concept of who's requesting, no org-level budget pool, and no approval
  gate — which matters as soon as more than one person in an organization
  is placing these requests. ([B2B Gifting Platforms Compared (2025)](https://smartsmssolutions.com/resources/blog/business/b2b-gifting-platform-comparison), [Best Corporate Gifting Platforms for 2026](https://imprintengine.com/blog/best-corporate-gifting-platforms-for-2026-complete-comparison-guide/))
- **CRM/HR system integrations.** Competitor platforms integrate with CRM
  and HR tools so gifting can be triggered by events (new hire, deal
  closed) rather than a person manually filling a form each time. Not
  applicable at Dream a Dozen's current scale, but worth flagging as the
  next-tier expectation once this becomes a repeat-use tool rather than a
  one-off generator. ([B2B Gifting Platforms Compared (2025)](https://smartsmssolutions.com/resources/blog/business/b2b-gifting-platform-comparison))
- **Reporting/insights dashboard.** Platforms in this space surface
  engagement and spend reporting to admins (what got ordered, by whom, for
  how much) — directly downstream of both the persistence gap and the
  auth gap above, since without accounts or storage there's nothing to
  report on. ([Top 15 Corporate Gifting Platforms of 2026](https://perkupapp.com/post/top-corporate-gifting-platforms))

## 5. Rewire vs. build-from-zero

Not every gap above is the same size of lift:

- **Rewire (smaller lift — logic already exists, just needs a real
  destination):** frontend persistence of `recommendations`/`lastBrief`
  could move from `useState` to `localStorage` or a lightweight backend
  store without touching the recommendation logic itself; the export
  pipeline already produces real files and would just need an "email this"
  or "save this" hook.
- **Build from zero (larger lift — no existing logic to repoint):**
  checkout/payment/order-tracking, auth/accounts, approval workflows, and
  any CRM/HR integration all require new domain logic and almost certainly
  new external services (payment processor, shipping carrier APIs,
  identity provider) — these are not currently stubbed anywhere, partially
  or otherwise, so there's nothing to "point" at a real backend.

## Sources

- [Top 15 Corporate Gifting Platforms of 2026](https://perkupapp.com/post/top-corporate-gifting-platforms)
- [9 Best Gift Sending Services for Businesses (2026)](https://www.sendoso.com/resources/blog/best-gift-sending-services)
- [Gift Tracking Software for Corporate Programs](https://imprintengine.com/blog/gift-tracking-software-for-corporate-programs/)
- [Best Corporate Gifting Platforms for 2026: Complete Comparison Guide](https://imprintengine.com/blog/best-corporate-gifting-platforms-for-2026-complete-comparison-guide/)
- [B2B Gifting Platforms Compared (2025): Features, Pricing Signals, Integrations & Use Cases](https://smartsmssolutions.com/resources/blog/business/b2b-gifting-platform-comparison)
