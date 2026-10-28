# llm-dream

Code and data for "Can an LLM dream?", an experiment by Eric Zou that tests Hoel's overfitted brain hypothesis (2021) on an LLM agent with text memory. The agent lives ten simulated days of LongMemEval conversations. Each night a sleep step rewrites its memory from that day's transcript. In the noisy arms some turns of the transcript are corrupted before the sleep step reads them, and the corruption is either structured (a detail swapped for a plausible wrong one) or random (the turn replaced with unrelated text). The question is whether the noisy arms remember as much as faithful replay and do better on transfer questions the agent has not seen before.

The paper link goes here once it is on arXiv.

## What the committed run found

- Far transfer was below faithful replay in all eight noisy arms (−17 to −8 points), and the noisy arms lost more from near to far probes than faithful replay did (near-minus-far +3 to +11 points), the opposite of what Hoel's account predicts.
- Faithful replay reached 76 ± 5 percent final-day recall. Structured noise at 20 percent reached 69 ± 2 percent, a paired difference of −7 ± 7 points; novel multi-session questions changed by −12 ± 10 points and far transfer by −8 ± 8 points. Recall falls with the structured dose (−17 ± 5 points at 40 percent).
- Random noise costs little recall (random 40 percent: 76 ± 3 versus 76 ± 5, a difference of 0 ± 2 points; random 5 percent is the only noisy arm above faithful beyond one seed SD, +2 ± 1), but it did not improve far transfer (random 40 percent: −17 ± 17 points).
- The day-eleven battery was near ceiling: DRM hits 81 to 100 percent, serial hits 93 to 100 percent, and critical-lure false alarms 0 percent in every arm. It cannot test a false-memory difference.
- The strong version of Hoel's prediction, that noisy replay should improve generalization, is not supported by these data. With three seeds, all arm comparisons are exploratory. See `results/results_v2.md`.

## What is in the repo

- `harness/` holds the experiment. `api.py` makes every model call (pinned claude-opus-5-5, model id checked on every reply, no fallbacks). `life.py` builds one ten-day life per seed. `arms.py` has the ten night steps and the sleep prompt. `run_arm.py` runs one arm on one seed and can resume. `battery.py` is the day-eleven memory battery, `transfer.py` the transfer test, `judge.py` the LongMemEval grading prompts. `analyze.py` and `write_results.py` build the summary and results table.
- `scripts/` has `run_all.py` (cross-platform sweep runner), `run_all.sh` (the original bash runner), the judge agreement check, the budget helper, the topic scan and swap that replaced some filler sessions (see `decisions.md`), the answer-copy and evidence-hit checks used in the paper, and the Letta replication check.
- `data/lives_manifest/` lists every session id, day, question and swap for the three seeds. The conversation text is left out because it comes from LongMemEval, and `scripts/rebuild_lives.py` puts it back. The rebuilt files match the ones the runs used exactly.
- `data/transfer_v2/` holds the transfer rules, episodes and probes. `data/day11/` holds the DRM word lists.
- `results/results_v2.md` is the results table for all 30 runs (ten arms, three seeds). `results/summary_v2.json` has the same numbers, and each run's own summary is in `results/runs_v2/`. The full run folders (memory after every night, every corruption, every answer and grade) are in the `runs_v2.tar.xz` file on the Releases page.
- `results/regrade_*` are the regrades with gpt-4o and gpt-5.6-luna. `results/letta_check/` is the check against Letta's published sleep-time compute numbers.
- `paper/make_figures.py` draws the paper figures from `results/summary_v2.json`. The optional Letta replication check needs `pip install -r requirements-letta.txt` and a local Letta server.
- `decisions.md` records every design choice made during the experiment, with the reason and the source.

## Running it

Needs Python 3.12 or newer (numpy 2.5 does not install on 3.11).

```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -c "from huggingface_hub import hf_hub_download as d; d('xiaowu0162/longmemeval-cleaned','longmemeval_s_cleaned.json',repo_type='dataset',local_dir='data/raw')"
git clone https://github.com/zycao29/LLM_CognitivePsychology external/LLM_CognitivePsychology
mkdir -p data/corpus && curl -sL -o data/corpus/moby_dick.txt https://www.gutenberg.org/cache/epub/2701/pg2701.txt
.venv/bin/python scripts/rebuild_lives.py
cp .env.example .env    # then add your keys
.venv/bin/python harness/run_arm.py faithful 0 --out results/runs_new    # results/runs_v2 holds the published sweep
```

On Windows the harness runs the same way with `py -3.13 -m venv .venv` and `.venv\Scripts\python` in place of `.venv/bin/python`.

The sweep runner is cross-platform:

```
# offline pipeline check, no keys
.venv\Scripts\python scripts\run_all.py --backend fake --arms faithful structured_20 --day-tokens 20000 --skip-battery

# real Max-plan sweep (resumable; skips finished runs)
.venv\Scripts\python scripts\usage.py set 20 --weekly-usd 500 --stop-pct 80
.venv\Scripts\python scripts\run_all.py --backend subscription --out results/runs_new
```

`scripts/run_all.sh` is still there for the original bash flow. `scripts/run_all.py` checks the transfer files, refuses to start a subscription sweep without a budget, and stops on the judge gate. Use `--dry-run` to print the commands without running them.

The offline tests need no API key: `pip install -r requirements.txt -r requirements-dev.txt`, then `python -m pytest tests`. CI runs the same suite on Linux and Windows (`.github/workflows/tests.yml`).

`run_arm.py` takes any arm name from `harness/arms.py` and a seed from 0 to 2. Results go to `<out>/<arm>_s<seed>/`. The committed `results/runs_v2/` folders hold only the original sweep's summaries, and both runners refuse to start a new run inside them. `harness/analyze.py` followed by `harness/write_results.py` rebuilds the table. If the original `state.json` files are unavailable, `harness/analyze.py --from-summaries` rebuilds from the committed per-run `summary.json` files. A resumed run must use the same `WP_BACKEND` that wrote its `state.json`; the harness aborts rather than mixing backends.

One full run (ten days plus the day-eleven tests) costs about 65 USD at Anthropic list price. `harness/api.py` stops at 100 USD of API spend (`SPEND_CAP_USD`), so raise that before running more than one arm. The original sweep ran Opus through Claude Code on a Max plan (`WP_BACKEND=subscription`), which also needs a budget set before it starts. The default backend is the API.

The API path now gives sleep calls the full 64k output budget, answers 16k, corruption batches 32k, and judges 4k. A `max_tokens` stop is a hard abort, not a silently truncated memory or answer.

## Running it for free

Nothing below needs an API key or spends money. The data setup above (LongMemEval, the Cao repo, Moby Dick, `rebuild_lives.py`) is free too; skip the `.env` step.

**Offline check (no model at all).** `WP_BACKEND=fake` answers every call with canned replies shaped like the real ones, so the whole pipeline (ten days, every arm, final questions, transfer probes, day-11 battery) runs in seconds. The scores mean nothing; this is for checking that changes don't break the harness. Fake runs go to `results/runs_fake/`, never beside real ones.

```
WP_BACKEND=fake .venv/bin/python harness/run_arm.py faithful 0
WP_BACKEND=fake .venv/bin/python harness/run_arm.py structured_20 0 --day-tokens 20000   # short days, caps scaled down
```

On Windows PowerShell: `$env:WP_BACKEND="fake"; .venv\Scripts\python harness\run_arm.py faithful 0`.

**Real run on your Claude subscription.** `WP_BACKEND=subscription` sends every Opus call through Claude Code (`claude -p`, logged in), which uses your plan's usage instead of money. With no keys in `.env`:
- the judge is Opus alone (no OpenAI call; set `WP_MAIN_JUDGE` to override), so labels can differ from the paper's gpt-5.6-luna labels;
- token counts are tiktoken estimates rather than Claude's tokenizer, so day lengths and caps are approximate.

The harness pauses (exit code 3) at a usage budget you set. Run `scripts/usage.py set <percent>` with the percentage `/usage` shows in Claude Code first. Its `WEEKLY_USD` is the original author's Max-plan estimate, so on a smaller plan lower it or keep the budget tight; the harness also pauses when Claude Code reports a usage limit. A full ten-day run used about 65 USD of list-price usage on a Max plan, more than a Pro plan allows in a week, so start with short days:

```
WP_BACKEND=subscription .venv/bin/python harness/run_arm.py faithful 0 --days 3 --day-tokens 20000 --out results/runs_free
```

## Known limitations

- Three seeds, 100 recall questions and 24 transfer probes per life. Treat arm differences as exploratory; a difference inside one seed SD is not evidence of a difference.
- The day-eleven battery is near ceiling for hits and at the floor for critical-lure false alarms, so it does not test false-memory effects. The battery night also uses each arm's own night step, so noisy arms corrupt the battery study material; a future battery should give every arm identical material. A harder incidental-encoding battery is the next step.
- The simulated days are stitched from different LongMemEval users, and temporal-reasoning questions are excluded. Absolute accuracy is not comparable with published LongMemEval numbers.
- The original run folders (`state.json`) are not in this checkout; only per-run `summary.json` files are committed. The ten-day memory means are corrected here, but the old stripping/deletion, nights-over-cap and sleep-time totals still include the day-11 consolidation.
- `cost.jsonl` is ignored and this checkout contains only fake-backend records. `write_results.py` preserves the archived spend sentence when it has no billable records.

## Licence

The code is MIT. LongMemEval (Wu et al., 2024) is MIT and is downloaded rather than copied here. `external/longmemeval_evaluate_qa.py` is LongMemEval's grading script, copied unchanged for its prompt templates. The day-eleven battery reads its prompt from Cao, Schooler and Zafarani's repo, which the setup clones. The Letta check adapts `run_stateful_gsm_symbolic.py` from letta-ai/sleep-time-compute (MIT).
