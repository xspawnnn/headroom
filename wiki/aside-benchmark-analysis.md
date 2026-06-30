# Aside Benchmark Analysis

> Analysis of the benchmark claims made in Aside's YC F2025 launch (June 2026).

---

## The 99% Claim

Aside reports topping three browser-agent benchmarks, including a 99.0% score, but those are self-reported from Aside's own repository with its own grading setup — not an independently audited leaderboard. The company graded its own homework, published the methodology nowhere a third party has reproduced, and the launch tweet presents it as settled fact. That is not a benchmark win; it is a marketing claim with a GitHub repo attached.

---

## Three Additional Problems

### 1. No Accountability for Failure

One early user signed up for the pro plan, reported their first task did not complete, and already burned 100% of their pro plan credits — with no visibility into token spend. That is a billing model that punishes users for the product not working.

### 2. "Completes Tasks Until Done" Is a Liability

An agent that runs multi-step tasks with no approval step is exactly the wrong default for anything customer-facing or sensitive. Framing this as a feature obscures a real risk surface.

### 3. Apples-to-Oranges Benchmark Comparisons

Aside's claimed benchmarks — Online-Mind2Web, BU-Bench-V1, Odysseys — are not the same suite that competitors report against:

| Agent | Benchmark | Score |
|---|---|---|
| Aside | Online-Mind2Web | — |
| Aside | BU-Bench-V1 | — |
| Aside | Odysseys | 99.0% (self-reported) |
| Browser Use | WebVoyager | 89.1% |
| OpenAI CUA | WebVoyager | 87.0% |
| OpenAI CUA | WebArena | 58.1% |

Because none of the competitor numbers appear on Aside's chosen benchmarks, the claim "beats every other browser agent tested" is true only within a test Aside itself selected and graded.

---

## Context

Aside is a two-week-old YC F2025 company at time of writing. The privacy architecture — local-first, post-quantum encryption, sandboxed agent — sounds legitimate on paper, but "sounds legitimate" and "independently verified" are not the same claim.

---

## Evaluation Guidance

If evaluating Aside for actual use:

1. **Wait** for a third party to run Aside against the same benchmark suite competitors use (WebVoyager, WebArena).
2. **Run your own side-by-side test** with a task you can verify failed or succeeded objectively.
3. **Do not take the screenshot at face value** — that is literally what launch screenshots are optimized for.

---

## Confidence

| Claim | Confidence |
|---|---|
| Benchmarks are self-reported | High — sourced directly from Aside's own repo and methodology disclosure |
| Credit-burn complaint exists | High — public user report |
| No-approval-step design is the default | High — documented in their feature list |
| Aside is actually good or bad as a product | **Medium** — too new for independent verification either way |
