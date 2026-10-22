# Failure Log

Issues found during manual testing (Phase 5). Each becomes an eval case in Phase 6,
measured before and after the fix.

## Retrieval
- **R1: Boilerplate pages outrank content.** Query "What risks does NIST identify for
  generative AI producing false or misleading content?" retrieved cover/title pages
  (600-1 p.1, p.2, p.3). Answer exists in 600-1 (confabulation, information integrity).
  Model correctly refused rather than hallucinate. Root causes: front-matter chunks in
  the index (reproduced 2 of 2 runs); vocabulary mismatch ("false content" vs "confabulation"); small embedding model.

## Generation
- **G1: Severity conflated with confidence.** Audit report rated DI=0.2 as "Medium"
  because n=5. Should be "High severity, low confidence." Seen in 2 of 2 runs.
- **G2: Prompt rule presented as external standard.** Report called n>=30 "the standard
  minimum"; that threshold came from our system prompt.
- **G3: Possible strengthening of source language.** Q&A answer used "must" where the
  voluntary NIST RMF may say "should." Needs a quote/wording faithfulness check.
- **G4: Tangential padding.** Q&A answer on post-deployment bias monitoring included
  loosely related points (100-1 p.6, p.12).

## Verification gaps
- **V1: Citation check verifies the page was retrieved, not that it supports the claim.**

## Reliability
- **REL1: Free-tier rate limits (429)** hit after repeated runs. Mitigated with a
  3-model fallback chain and a single wait-and-retry. Evals must pace requests.

## Fixed during Phase 5
- **F1: Swapped column defaults produced a 100/100 fairness score** on a misconfigured
  audit. Fixed with name-based defaults and positive-label validation.
- **F2: Export button nested inside Evaluate never fired.** Fixed with session state
  and download buttons.

## Refusals
- **G5: Correct refusals and retrieval misses look identical.** Q: "What is the maximum
  fine for violating the NIST AI RMF?" Model correctly invented no fine (pass), but replied
  "passages do not contain information" instead of correcting the false premise (the RMF
  is voluntary, stated in 100-1). Same wording as R1, where the answer existed but
  retrieval missed it. Users cannot tell "not in NIST" from "search failed."
- **UX1: Yellow "no citations" warning shown for correct refusals,** same as for failures.

## Phase 6b results: retrieval experiments
Retrieval benchmark (12 cases, evidence-term relevance). One change at a time:

| config | hit@4 | MRR | misses |
|---|---|---|---|
| MiniLM (baseline) | 0.75 | 0.607 | R1, voluntary |
| MiniLM + boilerplate filter | 0.75 | 0.607 | R1, voluntary |
| bge-small + filter | 0.667 | 0.506 | R1 |
| **bge-base + filter (adopted)** | **0.833** | **0.704** | R1 |

- Boilerplate filter removed junk results (2.1% to 0%) but did not change scores, as predicted.
- bge-small regressed despite being search-tuned; size mattered more than training objective here.
- **voluntary** now retrieved, unblocking a proper answer to G5 (false-premise fines question).
- **R1 unresolved by embeddings alone.** Vocabulary gap ("false content" vs "confabulation")
  needs query-side handling. Caution: any fix must be checked on held-out questions, not just R1,
  to avoid tuning the system to the test.
- Caveat: 12 cases; hit@4 gain is one case. MRR gain is the stronger signal.

## Phase 6c: query rewriting (criteria set BEFORE running)
Held-out baseline (bge-base, no rewrite, 7 cases): hit@1 0.286, hit@4 0.857, MRR 0.464. Miss: H_emotional.
Two variants: "plain" (LLM rewrites into NIST vocabulary from its own knowledge) and
"taxonomy" (same, plus the 12 risk category names from 600-1's own structure).
Note: several held-out terms are taxonomy category names, so "taxonomy" has an advantage there;
H_emotional, H_overreliance, H_red_team, and H_provenance are NOT category names and test generalization.

Adopt a variant only if ALL hold:
1. Held-out MRR improves over 0.464.
2. Dev set does not regress (hit@4 >= 0.833, MRR >= 0.704).
3. R1 is no longer a miss.
If none qualifies, rewriting is not adopted, and that is a valid result.

- **REL2: Daily free-tier quota exhausted on 3.6 and 3.5 Flash during eval runs.**
  Fallback chain still succeeded on the third model, but each call first waited through
  the client library's internal retries on both exhausted models, making runs very slow,
  and mixed models within a single experiment. Fix: run rewrite experiments on
  gemini-3.5-flash-lite (separate, larger quota; adequate for a simple rewrite task),
  using the same model across all four runs for a fair comparison.

### Phase 6c results
| set | config | hit@1 | hit@4 | MRR | misses |
|---|---|---|---|---|---|
| dev | no rewrite | 0.583 | 0.833 | 0.704 | R1 |
| dev | plain | 0.583 | 0.917 | 0.736 | - |
| dev | taxonomy | 0.75 | 0.917 | 0.836 | - |
| held-out | no rewrite | 0.286 | 0.857 | 0.464 | H_emotional |
| held-out | **plain (adopted)** | 0.714 | 1.0 | 0.833 | - |
| held-out | taxonomy | 0.571 | 0.857 | 0.743 | - |

- Both variants met all pre-registered criteria. **R1 resolved.** H_emotional resolved.
- Taxonomy won on dev but lost on held-out, despite an expected held-out advantage. Dev questions
  are mostly taxonomy categories, so taxonomy looks good there by construction. No tie-breaker
  was pre-registered; chose plain because held-out performance measures generalization.
- Rewrites run on gemini-3.5-flash-lite (REWRITE_MODEL), with the main chain as fallback.
- Caveats: 7 held-out cases (one case ~0.14 hit@4); LLM rewrites vary run to run.
