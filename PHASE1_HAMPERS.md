# Hampers Expansion — Planned Proposal

## 1. Goal

Expand the existing quotation tool to support **two independent recommendation types**:

* Snack Boxes
* Hampers

The existing Snack Box functionality must remain stable and unchanged.

---

## 2. Architecture Direction

Do not convert the application into microservices or create two completely separate applications.

Instead, evolve it into one application with separate domain modules:

```text
shared/
snack_boxes/
hampers/
```

The principle is:

> Snack Box logic and Hamper logic should be independent. Only infrastructure or concepts that are genuinely shared should be extracted into `shared/`.

The existing snack-box recommendation engine should be treated as frozen during the initial hamper implementation.

---

## 3. Frontend Entry Flow

The tool should start with an upfront choice:

```text
What would you like to create?

[ Snack Box ]     [ Hamper ]
```

* **Snack Box** → existing workflow
* **Hamper** → new hamper workflow

The two flows should remain separate.

---

## 4. New Hamper Recommendation Engine

Build a new hamper engine independently from the snack-box engine.

The core flow should be:

```text
BD Request
    ↓
Find Candidate Hamper Containers
    ↓
Generate Item Combinations
    ↓
Check Budget
    ↓
Check Physical Fit
    ↓
Check Composition Rules
    ↓
Score and Rank
    ↓
Return Diverse Hamper Recommendations
```

---

## 5. Hamper Generation Logic

### Step 1: Receive BD requirements

The initial hamper request should support the relevant inputs, starting with:

* Budget
* Number of hamper options required
* Product/category preferences
* Must-include items
* Excluded items

Additional inputs should be added only when the actual business requirements are confirmed.

---

### Step 2: Identify candidate outer hamper boxes

The system should not permanently select one box before generating combinations.

Instead:

1. Identify available hamper boxes.
2. Consider their:

   * price
   * dimensions
   * usable capacity
3. Treat multiple boxes as candidate containers.

Each container creates a separate possible search space.

---

### Step 3: Calculate available item budget

For each candidate hamper container:

```text
Available Item Budget =
Total Budget
− Container Cost
− Applicable Additional Charges
```

The engine then generates item combinations within the remaining budget.

---

### Step 4: Generate candidate item combinations

Using the hamper item catalog, generate combinations that satisfy the requested preferences and composition rules.

The system should avoid poor combinations such as excessive repetition of similar products unless explicitly requested.

---

### Step 5: Apply budget constraints

Each candidate recommendation should calculate:

```text
Total Hamper Price =
Container Price
+ Selected Item Prices
+ Applicable Packaging Charges
+ Applicable Customisation Charges
```

Budget handling should follow three levels:

```text
Above Budget Cap
→ Reject

Below Budget but poor utilisation
→ Valid but lower ranked

Close to Budget
→ Higher ranked
```

The goal is to utilise the customer's budget effectively without exceeding the defined maximum.

---

### Step 6: Apply physical-fit constraints

The system must verify that selected items can reasonably fit inside the selected hamper container.

The first implementation should **not attempt a full 3D bin-packing solver**.

Instead, use a conservative fit-validation approach based on:

* container dimensions
* item dimensions
* item volume
* individual item fit
* allowed item orientation/rotation where applicable
* safety margin or usable-capacity factor

The architecture should allow a more advanced physical arrangement algorithm to be added later.

---

### Step 7: Score and rank recommendations

Valid hamper combinations should be scored based on factors such as:

* budget utilisation
* category/composition balance
* product diversity
* business preferences
* physical fit confidence

The system should return multiple recommendations that are meaningfully different from each other rather than minor variations of the same hamper.

---

## 6. Core Hamper Data Model

The new hamper module should be designed around four main concepts:

```text
HamperRequest
HamperContainer
HamperItem
HamperRecommendation
```

Conceptually:

```text
HamperRequest
├── Budget
├── Preferences
├── Must Include
├── Exclusions
└── Number of Options


HamperContainer
├── Name
├── Price
├── Dimensions
└── Capacity


HamperItem
├── Name
├── Price
├── Dimensions
├── Category
└── Packaging Information


HamperRecommendation
├── Selected Container
├── Selected Items
├── Total Price
├── Budget Utilisation
├── Composition Information
└── Physical Fit Status
```

---

## 7. Implementation Phases

### Phase 1 — Structural separation

Create the new hamper domain without modifying the existing snack recommendation logic.

Establish clear boundaries between:

```text
shared/
snack_boxes/
hampers/
```

Do not perform a large speculative refactor of the existing snack engine.

---

### Phase 2 — Hamper data layer

Load and normalize the hamper catalog data.

Ensure the new engine can distinguish between:

* outer hamper containers
* items placed inside hampers
* item categories
* prices
* dimensions
* packaging information

---

### Phase 3 — Basic hamper recommendation engine

Implement:

```text
Budget
→ Candidate Containers
→ Candidate Item Combinations
→ Budget Validation
→ Basic Physical Fit Validation
→ Scoring
→ Ranked Recommendations
```

---

### Phase 4 — Frontend integration

Add the new landing choice:

```text
[ Snack Box ] [ Hamper ]
```

Build a separate hamper input flow and results display without changing the existing snack-box workflow.

---

### Phase 5 — Advanced improvements

After the basic hamper engine is working and validated against real business requirements, consider:

* advanced 3D packing
* smarter container selection
* occasion-specific hamper composition
* predefined hamper templates
* branded/customised components
* visual hamper layout
* additional pricing rules

---

## 8. Core Principle

The implementation should follow this rule:

> **Do not force hampers into the existing snack-box recommendation model, and do not refactor the snack engine until a genuinely shared abstraction has been proven by both domains.**

The immediate objective is to build a clean, independent **Hamper Engine** alongside the existing **Snack Box Engine**, while sharing only infrastructure that is demonstrably common.
