# FEATURE IMPLEMENTATION PROMPT — Dilution-Aware Risk

**How to use this file:** hand it to an AI session together with `ORBITGUARD_AI_MASTER_HANDOFF.md`. The handoff is the source of truth for architecture and state; this file is the specification for one feature. Section numbers written as `§n` refer to the handoff.

**Change classification (§21):** Type C (scientific/model change) + Type E (differentiation feature).
**Status:** PROPOSAL. Nothing in this document is implemented. Do not describe any part of it as existing behaviour until you have built and measured it.

---

## 0. The instruction

```text
You are the principal engineer for ORBITGUARD.

Implement dilution-aware collision risk: report whether the system KNOWS how
dangerous a conjunction is, not only how dangerous the point estimate says it is.

You must follow the handoff's execution contract (§18):
  1. State the current verified baseline.
  2. Identify the highest-risk unverified assumption.
  3. Run the smallest experiment that can falsify it.
  4. Report measured results.
  5. Decide whether the idea survives.
  6. Only then integrate.

PHASE 0 IS A KILL GATE. Do not write production code until it passes.
If it fails, stop and report; do not implement the feature anyway.

Work on a feature branch off integration/ai-engine. Do not touch main. Do not
push and do not open a PR until explicitly authorised. Use PowerShell-compatible
commands. Never print or commit .env contents or credentials.
```

---

## 1. Problem statement

For a fixed miss distance, collision probability is **not monotonic** in positional uncertainty. It approaches zero both when σ → 0 (you know with confidence that the objects miss) and when σ → ∞ (probability mass is spread too thinly to concentrate anywhere). It peaks in between.

**Consequence:** a conjunction with bad data reports a *low* Pc. The current engine cannot distinguish that from a conjunction that is genuinely safe.

**Consequence for ranking:** §5's score is `100 · norm(log10 Pc over [−9,−3]) · (0.8 + 0.2·urgency)` — monotonic in Pc. So a stale, poorly-observed event scores lower and sorts further down the priority list than a well-observed one. The system currently ranks ignorance as safety.

This is a known trap in operational conjunction assessment ("probability dilution"). It is the first thing a judge with domain background will attack (§17, Trust).

**Illustrative magnitudes**, using the handoff's own passive learned model (§5: `σ_along = 0.75 + 0.45·age km`), near-co-orbital geometry, 0.5 km miss, 10 m HBR. Radial/cross-track coefficients are **ASSUMED** (`0.20 + 0.05·age`) because the handoff does not state them — substitute the real model values:

| TLE age | in-plane σ | Pc | severity | Pc_max | dilution |
|---:|---:|---:|---|---:|---:|
| 0 d | 1.09 km | 3.8e-05 | HIGH | 1.47e-04 | 4× |
| 1 d | 1.73 km | 1.6e-05 | HIGH | 1.47e-04 | 9× |
| 3 d | 3.00 km | 5.5e-06 | AMBER | 1.47e-04 | 27× |
| 5 d | 4.27 km | 2.7e-06 | AMBER | 1.47e-04 | 54× |

Same physical encounter. The older the data, the safer it looks.

---

## 2. Phase 0 — kill gate (run this first, ~30 minutes)

```markdown
## Experiment: severity-vs-data-age monotonicity

### Hypothesis
For a fixed physical encounter, the current risk engine's reported Pc, severity
and score improve as the TLE age fed to the uncertainty model increases.

### Why it matters
If true, the engine systematically under-ranks poorly-observed conjunctions, and
ranking is the product's primary output. If false, this feature collapses to a
presentation change and must be re-scored before any work proceeds.

### Baseline
Current risk_engine + uncertainty model on integration/ai-engine.

### Method
Write scripts/experiment_dilution_gate.py. Call the risk engine DIRECTLY
(do not modify the API for this). Hold geometry fixed: one miss distance, one
relative speed, one encounter geometry. Sweep ONLY the TLE age passed to the
uncertainty model: 0, 0.5, 1, 2, 3, 5 days. Record Pc, severity, score.
Repeat for miss distances 0.2, 0.5, 1.0, 5.0, 9.0 km — the last two matter
because §6 reports real screened events sitting at 5-9 km.

### Metrics
- sign of d(score)/d(age)
- sign of d(Pc)/d(age)
- dilution factor Pc_max/Pc at each age
- the miss distance at which the effect becomes negligible

### Expected result
Pc and score DECREASE with age for small miss distances -> flaw confirmed.

### Kill condition
Score already increases with age, OR severity is age-invariant, OR the dilution
factor stays below 3x across all tested miss distances. Any of these means the
engine already handles this adequately. STOP, report, do not implement.

### Result
<fill in with measured numbers>

### Decision
[KEEP / MODIFY / REJECT]
```

> **Known risk, stated honestly:** the illustrative 27–54× factors above are for a 0.5 km miss. §6 reports that real screened events cluster at 5–9 km. At those distances σ/miss is smaller and the effect will be weaker. **The mechanism is certain; the magnitude on your catalog is not.** Phase 0 exists to measure it. If the dilution factor on realistic events is under 3×, the feature is not worth the demo slot — say so and stop.

---

## 3. The science

### 3.1 Closed form (circular in-plane covariance)

```
Pc(σ)   = (HBR² / 2σ²) · exp(−m² / 2σ²)
peak at   σ* = m / √2
Pc_max  = (HBR / m)² / e
```

Derivation: substitute `u = 1/(2σ²)`, giving `Pc = HBR²·u·exp(−m²u)`; then `dPc/du = 0` at `u = 1/m²`.

Use this **only as a unit-test oracle**, not as the production path.

### 3.2 Production implementation (general elliptical covariance)

Your Foster implementation uses a real, generally non-circular projected covariance. Do not replace it. Instead compute the supremum by scaling:

```python
def max_probability(foster_pc, cov_2d, miss_vec, hbr):
    """
    Supremum of Foster Pc over uniform scalings k*C of the projected covariance.
    Reuses the existing Foster routine - no new physics, no new approximation.
    """
    f = lambda log_k: -foster_pc(math.exp(log_k) * cov_2d, miss_vec, hbr)
    # 1-D maximisation over log_k; the objective is unimodal in k.
    # Use the same bounded Brent already used for TCA refinement.
    ...
```

Reasons this is the right shape:

- reuses the validated Foster path, so `Pc_max` and `Pc` are always mutually consistent
- one bounded 1-D maximisation; microseconds, no measurable cost
- degenerates exactly to the closed form when the covariance is circular — **that is your unit test**

**Precision to preserve in every claim:** this is the supremum over covariance *scalings*, not over all possible covariances. Write it that way in code comments, in the API docs, and on any slide. A judge will ask, and the qualifier is a one-sentence answer.

### 3.3 Knowledge-state classification

```
RESOLVED_SAFE        Pc_max < action_threshold
                     -> safe no matter what you subsequently learn

RESOLVED_DANGEROUS   Pc >= action_threshold AND sigma_in_plane <= sigma*
                     -> the point estimate is on the well-determined side of the
                        peak; act on it

UNRESOLVED           Pc < action_threshold AND Pc_max >= action_threshold
                     -> not safe; uninformed
```

`action_threshold` must be a named configuration constant, not a literal. Default it to the handoff's AMBER boundary, `1e-6` (§5).

Guard against over-flagging: `Pc_max` is finite for *any* miss distance, so a distant, harmless event still has one. Gate the whole computation behind the existing screening miss-distance threshold, and return `knowledge_state = RESOLVED_SAFE` with no dilution reporting above it.

### 3.4 Geometry attribution (fold in — it is what explains the result)

Foster projects covariance into the plane perpendicular to **v**_rel. For two near-circular orbits whose velocity vectors differ by angle θ, an object's **along-track** error — the dominant component in your learned model — enters that plane scaled by:

```
projection_factor = cos(θ / 2)
```

**VERIFIED** numerically to four decimal places across θ = 5°…175°:

| θ | 5° | 30° | 60° | 90° | 120° | 150° | 175° |
|---|---:|---:|---:|---:|---:|---:|---:|
| cos(θ/2) | 0.999 | 0.966 | 0.866 | 0.707 | 0.500 | 0.259 | 0.044 |

So a head-on encounter projects the dominant error almost entirely *out* of the encounter plane and is the best-determined geometry there is; a near-co-orbital encounter admits it at full strength and lands deep in the dilution regime. Same miss, same TLE age, Pc spans ~22× on geometry alone.

Surface `projection_factor` and its contribution as a named driver in the existing counterfactual explanation structure. It costs nothing — you already hold the RTN σ and the encounter geometry — and it turns `UNRESOLVED` from a label into an explanation.

---

## 4. Implementation phases

Respect §34 layer boundaries throughout: physics in `core/`, orchestration in `services/`, mapping only in `api/v1/serializers.py`, no authoritative computation in the frontend.

### Phase 1 — core computation (no API change)

**Files:** `src/app/core/collision_probability.py`, `src/app/core/risk_engine.py`, `src/app/core/uncertainty.py`

1. `max_probability(...)` in `collision_probability.py` per §3.2.
2. `sigma_star = miss / sqrt(2)` helper and the `knowledge_state` classifier in `risk_engine.py`.
3. `alongtrack_projection_factor(theta)` in `uncertainty.py`, plus its contribution to the existing driver list.
4. **Do not touch the existing `score` or `risk_level` computation in this phase.** Additive only.

**Tests (all required):**

| Test | Asserts |
|---|---|
| `test_max_probability_matches_closed_form` | circular covariance → `(HBR/m)²/e` within 1e-9 relative |
| `test_max_probability_is_upper_bound` | over a random sweep of scalings, `Pc(k·C) <= Pc_max` always |
| `test_peak_location` | maximising σ equals `m/√2` for the circular case |
| `test_knowledge_state_transitions` | age sweep moves a fixed encounter RESOLVED → UNRESOLVED at the expected age |
| `test_projection_factor` | matches `cos(θ/2)` across θ = 5°…175° |
| `test_far_event_not_flagged` | a 50 km miss returns RESOLVED_SAFE, no dilution reporting |
| `test_existing_131_unchanged` | full suite still passes |

### Phase 2 — API contract (additive only)

**File:** `src/app/api/v1/serializers.py`

Add as **optional** fields, consistent with how §4 says `collision_probability`, `uncertainty` and `narrative` were added. Existing field names and semantics must not change.

```json
{
  "collision_probability": 5.48e-06,
  "collision_probability_max": 1.47e-04,
  "dilution_factor": 27.0,
  "knowledge_state": "UNRESOLVED",
  "knowledge_explanation": "in-plane sigma 3.00 km exceeds sigma* 0.35 km; 99% of along-track error enters the encounter plane at this geometry (theta=10 deg)",
  "risk_level": "AMBER",
  "risk_level_if_resolved": "CRITICAL"
}
```

Ranking change, **behind a config flag, default off in this phase**: when `knowledge_state == UNRESOLVED`, sort `all_candidates` by `score_max` rather than `score`. Add a test that exercises both flag states. Turning the flag on is a separate, deliberate decision once Phase 0's numbers justify it — do not fold a ranking change into an additive release.

Reporting floor: keep §5's `< 1e-12` convention for `collision_probability_max` too.

### Phase 3 — frontend

**Files:** `frontend/src/api/orbitguard.js`, the event detail page

- map the new fields, tagging `source: live|mock` as the existing adapter does
- use `??` not `||` (§4 — 0 is a real value, and `dilution_factor` of 0 is meaningful)
- a badge for `knowledge_state`; `UNRESOLVED` must read as a *warning*, not as a neutral label
- show the interval `Pc … Pc_max`, never `Pc_max` alone
- degrade cleanly when the fields are absent (older backend, mock mode)

### Phase 4 — optional, only if Phases 1–3 are done and tested

The three-way recommendation. `MANEUVER` / `RE_OBSERVE` / `MONITOR`, driven by `knowledge_state`.

The Δv-vs-lead-time trade is closed form and **cross-checks against the existing planner to 0.1 h**:

```
along-track displacement from a tangential burn:  D = 3 · Δv · t     [linear in t]
required burn for target separation D:            Δv = D / (3 · t)
```

so halving the lead time doubles the burn:

| lead time | Δv for 10 km | propellant (500 kg, Isp 220 s) |
|---:|---:|---:|
| 24 h | 0.039 m/s | 8.9 g |
| 12 h | 0.077 m/s | 17.9 g |
| 6 h | 0.154 m/s | 35.8 g |
| 2 h | 0.463 m/s | 107.3 g |
| 1 h | 0.926 m/s | 214.5 g |

Combined with the learned `σ(age)` curve, this yields a real value-of-information statement — waiting 6 h for a fresh TLE costs ~18 g of propellant and flips AMBER to HIGH:

```json
"recommendation": {
  "action": "RE_OBSERVE",
  "rationale": "risk UNRESOLVED (dilution 27x); a fresh TLE resolves AMBER vs HIGH",
  "decision_deadline_utc": "2026-09-13T14:20:00Z",
  "cost_of_waiting": {"extra_delta_v_ms": 0.077, "extra_propellant_g": 17.9},
  "after_deadline": "required delta-v exceeds the configured budget"
}
```

`decision_deadline_utc` must come from the planner's actual Δv budget, not from the closed form above — the closed form is the sanity check.

---

## 5. Feature contract (§35)

```text
FEATURE     Dilution-aware collision risk

PROBLEM     A conjunction with poor data reports a low Pc and is indistinguishable
            from a genuinely safe one. Ranking is monotonic in Pc, so poorly
            observed events sort down the priority list.

INPUTS      Projected 2-D encounter-plane covariance, miss vector, HBR,
            encounter geometry angle, TLE age (via the existing learned model).

ALGORITHM   Supremum of the existing Foster Pc over uniform scalings of the
            projected covariance, by bounded 1-D maximisation. Classification
            against a configured action threshold and sigma* = miss/sqrt(2).
            Along-track projection factor cos(theta/2) as an explanatory driver.

OUTPUT      collision_probability_max, dilution_factor, knowledge_state,
            knowledge_explanation, risk_level_if_resolved.

ASSUMPTIONS - Foster 2-D encounter-plane model is valid for the encounter
              (short-encounter, linear relative motion).
            - Covariance shape is correct and only its SCALE is uncertain.
            - The learned uncertainty model is within its validity range
              (§5: passive model trained on ages <= 1.34 d).

FAILURE     - Very long or very slow encounters where Foster 2-D itself is
  MODES       inappropriate; dilution reasoning inherits that limitation.
            - Extrapolated TLE ages beyond the trained range.
            - Over-flagging distant events if the miss-distance gate is removed.

FALLBACK    If Pc_max cannot be computed (non-convergent maximisation, degenerate
            covariance), omit the optional fields entirely and log. Never emit a
            fabricated value and never silently substitute the closed form for a
            non-circular covariance.

METRICS     Phase 0 age-sweep table; dilution factor distribution over the real
            screened catalog; count of events whose severity changes.

TESTS       See Phase 1 table; all 131 existing tests must still pass.

DEMO        Section 6 below.

LIMITATIONS Supremum over covariance SCALING, not over all covariances. Does not
            estimate the true covariance - it bounds what the risk could be.
```

---

## 6. Demo narrative

The moment that lands is step 2 → 3: a number getting *better* for a bad reason, then being caught.

1. Live CelesTrak event, fresh data. Pc, severity, counterfactual drivers. *(Already exists.)*
2. The same event with a 3-day-old TLE. Severity drops to AMBER. **Pause here.** "Nothing physical changed. Only our knowledge did — and the naive answer got more comforting."
3. Dilution-awareness on. Badge flips to UNRESOLVED, `Pc_max` 1.5e-04, dilution 27×. "We are not safe. We are uninformed, and we can tell the difference."
4. Geometry driver: "99 % of our along-track error projects into the encounter plane at this geometry. A head-on pass would project it out."
5. *(Phase 4)* RE_OBSERVE, deadline, 18 g cost of waiting.

Per §38, verify before presenting: correct branch and commit, Python service **restarted** (not just refreshed), CONJ-001 TCA still in the future, frontend renders 0 correctly.

---

## 7. Definition of done (§36)

**Functional** — happy path works; far events and degenerate covariances handled; API behaviour defined for present and absent fields.

**Scientific** — assumptions documented; the scaling-supremum limitation stated in code, API docs and slides; validity range of the learned model stated.

**Evidence** — Phase 0 table filled in with measured numbers; dilution factor distribution over the real catalog recorded; the closed-form unit test passes.

**Safety / trust** — `UNRESOLVED` is visually a warning; fallback omits rather than fabricates; no fabricated confidence anywhere (§39).

**Integration** — all 131 existing tests pass; `risk_level` and `score` semantics unchanged in Phase 2; ranking change gated behind a flag with tests for both states.

**Demo** — steps 1–4 above run end to end on a restarted service.

**Documentation** — feature contract filled in; handoff updated with a new section distinguishing what is now VERIFIED from what remains PROPOSAL; §41 research backlog row closed with evidence, not with "done".

---

## 8. Do not claim

- ❌ "the maximum possible collision probability" → ✅ "the maximum over covariance scalings"
- ❌ "we quantify epistemic vs aleatoric uncertainty separately" → not implemented; §25 explicitly warns against this claim
- ❌ "our AI decides when to trust itself" → it is a closed-form bound plus a threshold, and saying so is stronger
- ❌ any dilution magnitude from this document on a slide → use **your** Phase 0 measured numbers
- ❌ "calibrated confidence" for anything other than the learned uncertainty model's actual held-out coverage figures

---

## 9. Commands

```powershell
$py   = "C:\Users\anime\dev\orbitguard\.venv\Scripts\python.exe"
$work = "C:\Users\anime\dev\orbitguard-integration"

# branch (never main)
git -C $work checkout integration/ai-engine
git -C $work checkout -b ai/dilution-aware-risk

# Phase 0 kill gate
& $py scripts\experiment_dilution_gate.py

# tests
& $py -m pytest
& $py tests\test_problem_statement_compliance.py

# service must be RESTARTED to pick up core changes (§6) - check the port first
Get-NetTCPConnection -State Listen | Where-Object LocalPort -in 8000,5000,5173
& $py -m uvicorn app.main:app --app-dir src --port 8000
```

Commit when tests pass. **Do not push and do not open a PR** until explicitly authorised (§2).
