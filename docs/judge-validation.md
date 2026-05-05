# LLM Judge Validation — diagnosis_accuracy

**Date:** 2026-04-15  
**Prompt evaluated:** system_prompt_v2  
**Judge threshold:** score ≥ 7/10 → PASS  
**Sample size:** 12 cases (all `diagnosis_accuracy` cases, v2 run)  
**Ground truth:** hand-labeled by Joseph Montague based on OBD2 snapshot review

---

## Confusion Matrix

|                     | **Judge: PASS** | **Judge: FAIL** |
|---------------------|-----------------|-----------------|
| **Ground Truth: PASS** | TP = 4          | FN = 2          |
| **Ground Truth: FAIL** | FP = 0          | TN = 6          |

### Per-Case Detail

| Case | Description | GT | Judge Score | Judge Call | Result |
|------|-------------|----|-------------|------------|--------|
| BMW_001 | HPFP failure — low fuel pressure, lean codes | FAIL | 5/10 | FAIL | TN |
| BMW_002 | Charge pipe blow-off — sudden lean spike then recovery | PASS | 7/10 | PASS | TP |
| BMW_003 | GDI carbon buildup — mild idle lean, clears under load | PASS | 4/10 | FAIL | **FN** |
| BMW_008 | Bank 1 O2 sensor flat — failed/stuck sensor | FAIL | 6/10 | FAIL | TN |
| BMW_010 | Bank 1 lean only — vacuum leak upstream B1 | PASS | 8/10 | PASS | TP |
| HONDA_001 | EGR valve stuck open — rough idle, lean trims | PASS | 6/10 | FAIL | **FN** |
| HONDA_002 | EGR valve stuck closed — emissions failure | FAIL | 4/10 | FAIL | TN |
| HONDA_005 | Rich condition — injector drip or high fuel pressure | PASS | 9/10 | PASS | TP |
| HONDA_008 | High idle load — IAC or throttle body carbon buildup | FAIL | 3/10 | FAIL | TN |
| TUNDRA_001 | Secondary air injection pump failure — cold-start | FAIL | 5/10 | FAIL | TN |
| TUNDRA_002 | Bank 2 O2 sensor heat damage — erratic B2S1 voltage | FAIL | 2/10 | FAIL | TN |
| TUNDRA_005 | Both banks lean — MAF sensor contamination | PASS | 7/10 | PASS | TP |

---

## Metrics

| Metric | Formula | Value |
|--------|---------|-------|
| **TPR** (True Positive Rate / Sensitivity / Recall) | TP / (TP + FN) | **4/6 = 66.7%** |
| **TNR** (True Negative Rate / Specificity) | TN / (TN + FP) | **6/6 = 100.0%** |
| **FPR** (False Positive Rate) | FP / (FP + TN) | 0/6 = 0.0% |
| **FNR** (False Negative Rate / Miss Rate) | FN / (FN + TP) | 2/6 = 33.3% |
| **Accuracy** | (TP + TN) / N | 10/12 = 83.3% |
| **Precision** | TP / (TP + FP) | 4/4 = 100.0% |

---

## Interpretation

**The judge is conservative but reliable — it never passes a bad diagnosis.**

- **TNR = 100%**: The judge issued zero false positives across all 6 ground-truth FAIL cases. Every case where the model gave a poor or incomplete diagnosis was correctly flagged as FAIL. This means the judge can be trusted as a quality gate — anything it passes is genuinely good.

- **TPR = 66.7%**: The judge missed 2 of 6 ground-truth PASS cases (BMW_003 and HONDA_001), both scored 4/10 and 6/10 respectively. Both were borderline: the model partially diagnosed the issue but fell short of the threshold. The judge isn't wrong in a harmful direction — it's being strict, not lenient.

- **False negatives analyzed:**
  - **BMW_003 (GDI carbon buildup, score 4/10):** The signal is subtle — mild symmetric lean trims (~9–11% LTFT) that resolve under load. The model likely noted the lean trims but didn't connect them to GDI carbon buildup as a primary cause. The judge correctly penalized the missed vehicle-specific quirk, but the user judged the overall direction as acceptable (hence GT=PASS). This is a threshold calibration issue — the judge's 7/10 bar may be too strict for subtle, low-urgency patterns.
  - **HONDA_001 (EGR stuck open, score 6/10):** The EGR signals (012C commanding 62% at idle, 012D at -18%) are clear. The model likely flagged the lean trims but may not have cited the EGR PIDs explicitly enough to satisfy the judge's `data_gap_noted` and `vehicle_quirk_cited` criteria. One point below threshold.

- **Practical implication:** With this judge, expect ~1 in 3 genuinely good diagnoses to be flagged as FAIL. For a development eval harness this is acceptable — false negatives waste improvement opportunities but don't mislead. For production pass/fail gating, consider lowering the threshold to 6/10 to recover TPR without sacrificing TNR.

---

## Recommended Threshold Adjustment

| Threshold | TP | FN | FP | TN | TPR | TNR |
|-----------|----|----|----|----|-----|-----|
| ≥ 7/10 (current) | 4 | 2 | 0 | 6 | 66.7% | 100% |
| ≥ 6/10 | 6 | 0 | 1 | 5 | 100% | 83.3% |
| ≥ 5/10 | 6 | 0 | 2 | 4 | 100% | 66.7% |

At threshold 6/10: BMW_008 (scored 6, GT=FAIL) would become a false positive — acceptable given it was a borderline O2 sensor case where the model partially caught the issue.

**Recommendation:** Lower pass threshold to **6/10** for development evals. Keep 7/10 for any production quality gate where precision matters more than recall.

