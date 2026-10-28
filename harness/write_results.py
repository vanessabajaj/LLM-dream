"""Write results/results_v2.md from results/summary_v2.json and cost.jsonl. Numbers only; the prose sections are fixed
text with the numbers filled in. v1's results.md is left as it is (v1 is kept as lessons learned, decisions.md).

v2 adds to the v1 format: the corruption-rate curve, final recall by delay in nights, transfer near and far, and the
gist-stripping and deletion counts per arm beside each arm's memory size (spec-v2.md "Ready to build", results line).
"""
import json, pathlib, time, collections, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "harness"))
import api, arms
S = json.load(open(ROOT / "results" / "summary_v2.json", encoding="utf-8"))
NAMES = {"nosleep": "No sleep (raw window at the cap)", "faithful": "Faithful replay",
         "structured_05": "Structured noise, 5 percent", "structured_10": "Structured noise, 10 percent",
         "structured_20": "Structured noise, 20 percent", "structured_40": "Structured noise, 40 percent",
         "random_05": "Random noise, 5 percent", "random_10": "Random noise, 10 percent",
         "random_20": "Random noise, 20 percent", "random_40": "Random noise, 40 percent"}
ARMS = [(a, NAMES.get(a, a)) for a in arms.ARMS]
N_RUNS = len(ARMS) * 3
DAYS = 10


def _i(v):
    return int(round(v))  # never prints "-0"


def f(x, pct=True):
    if x is None: return "n/a"
    if isinstance(x, dict):
        if pct: return f"{_i(100*x['mean'])} ± {_i(100*x['sd'])}"
        return f"{_i(x['mean']):,} ± {_i(x['sd']):,}"
    return f"{_i(100*x)}" if pct else f"{_i(x):,}"


def spend():
    """Since the v2 start: Max-plan calls at list price (no money), real money by provider."""
    maxp = collections.Counter(); real = collections.Counter()
    path = ROOT / "cost.jsonl"
    if not path.exists():
        return maxp, real
    for line in open(path, encoding="utf-8"):
        try: r = json.loads(line)
        except ValueError: continue
        if r.get("ts", 0) < api.V2_START or r.get("backend") == "fake": continue
        if r.get("backend") == "subscription":
            maxp["usd"] += r["usd"]; maxp["n"] += 1
        else:
            real[r["provider"]] += r["usd"]; real[f"n_{r['provider']}"] += 1
    return maxp, real


def previous_spend():
    """Keep the archived spend sentence when a checkout no longer has the original cost log."""
    p = ROOT / "results" / "results_v2.md"
    if not p.exists():
        return None
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.startswith("**What ran.**") and "Spend:" in line:
            suffix = line.split("Spend:", 1)[1].strip().rstrip(".")
            marker = "the original sweep recorded "
            if marker in suffix:
                suffix = suffix.rsplit(marker, 1)[1]
            return None if suffix.startswith("not available") else suffix
    return None


def verdict(d):
    if not d: return "not measured"
    m, sd = d["mean"], d["sd"]
    if abs(m) <= sd: return "inside the seed spread (exploratory, n=3)"
    return ("noisy arm higher" if m > 0 else "noisy arm lower") + ", beyond one seed SD (exploratory, n=3)"


def row(cells):
    return "| " + " | ".join(cells) + " |"


# ---- sentences computed from the numbers, so the prose cannot drift from the data -------------
NOISY = [a for a in arms.ARMS if a not in ("nosleep", "faithful")]


def noisy_diffs(metric):
    """{arm: paired difference against faithful} over the noisy arms that have it."""
    pv = S["paired_vs_faithful"]
    return {a: pv[f"{a}_minus_faithful.{metric}"] for a in NOISY if f"{a}_minus_faithful.{metric}" in pv}


def beyond(d, sign):
    return d["mean"] * sign > d["sd"]


def points_range(ds):
    ms = [_i(100 * d["mean"]) for d in ds.values()]
    return f"{min(ms):+d} to {max(ms):+d} points"


def percent_range(key):
    """Range of the per-arm means of a day-11 morning measure, in percent."""
    ms = [_i(100 * v["battery_morning"][key]["mean"]) for v in S["by_arm"].values()
          if (v.get("battery_morning") or {}).get(key)]
    if not ms: return "n/a"
    return f"{ms[0]} percent in every arm" if min(ms) == max(ms) else f"{min(ms)} to {max(ms)} percent"


def outcome_lead():
    far, nmf, rec = noisy_diffs("transfer.far"), noisy_diffs("transfer.near_minus_far"), noisy_diffs("final_acc")
    if not far:
        return "Transfer was not measured, so the generalization prediction is untested."
    up = [NAMES[a] for a, d in far.items() if beyond(d, +1)]
    lower = sum(d["mean"] < 0 for d in far.values())
    lead = (f"The strong prediction is not supported: far transfer was below faithful replay in {lower} of {len(far)} noisy arms "
            f"({points_range(far)}), and no noisy arm improved it beyond one seed SD." if not up else
            f"The transfer result is mixed: far transfer improved beyond one seed SD in {', '.join(up)}, "
            f"while the noisy arms overall ranged {points_range(far)}.")
    if nmf:
        pos = sum(d["mean"] > 0 for d in nmf.values())
        lead += (f" Near-minus-far was positive in {pos} of {len(nmf)} noisy arms ({points_range(nmf)}), so noisy replay lost"
                 f" {'more' if pos > len(nmf) / 2 else 'less'} from near to far probes than faithful replay, where Hoel's account predicts less.")
    if rec:
        better = [f"{NAMES[a]} ({f(d)} points)" for a, d in rec.items() if beyond(d, +1)]
        lead += (f" On final recall the noisy arms ranged {points_range(rec)} against faithful; "
                 + (f"only {', '.join(better)} beat it beyond one seed SD." if better else "none beat it beyond one seed SD."))
    return lead


def main():
    by, pv, curve = S["by_arm"], S["paired_vs_faithful"], S["curve"]
    maxp, real = spend()
    runs_done = S["finished_runs"]
    head = pv.get("structured_20_minus_faithful.final_acc")
    novel = pv.get("structured_20_minus_faithful.final_acc_novel")
    far = pv.get("structured_20_minus_faithful.transfer.far")
    nmf = pv.get("structured_20_minus_faithful.transfer.near_minus_far")
    lure = pv.get("structured_20_minus_faithful.battery_morning.drm_lure_fa")
    rand40_head = pv.get("random_40_minus_faithful.final_acc")
    rand40_novel = pv.get("random_40_minus_faithful.final_acc_novel")
    rand40_far = pv.get("random_40_minus_faithful.transfer.far")
    ja = S.get("judge_agreement_overall")
    legacy = any(r.get("legacy_includes_battery_totals") for r in S["runs"].values())
    caps = ", ".join(f"{c:,}" for c in arms.CAPS[:DAYS])
    if maxp["n"] or real["n_openai"] or real["n_anthropic"]:
        spend_txt = (f"Spend: {maxp['usd']:.2f} USD list price on the Max plan over {maxp['n']} Opus calls (no money), "
                     f"{real['openai']:.2f} USD on OpenAI over {real['n_openai']} judge calls"
                     + (f", {real['anthropic']:.2f} USD on the Anthropic API key over {real['n_anthropic']} calls" if real["n_anthropic"] else "") + ".")
    else:
        prev = previous_spend()
        spend_txt = "Spend: not available in this checkout (cost.jsonl has no billable calls)" + (f"; the original sweep recorded {prev}" if prev else "") + "."

    L = ["# Results: noisy replay at four doses", "",
         f"Generated {time.strftime('%d %B %Y %H:%M UTC', time.gmtime())}. Model under test claude-opus-5-5, effort medium, through Claude Code on the Max plan. Days of 130,000 tokens; the memory cap grows each night ({caps} tokens). Ten days, ten arms, three seeds.", "",
         "## One-screen summary", "",
         f"**What ran.** {runs_done} of {N_RUNS} runs finished (ten arms x three seeds). Each run: ten days of about 30 LongMemEval sessions plus the transfer-test episodes, one night step per day, 100 memory questions asked before sleep, after sleep and at the end, 24 transfer probes after night 10, then an eleventh day with the memory-effects battery. {spend_txt}", "",
         f"**Judges.** gpt-5.6-luna grades every answer, Opus 5.5 grades it again. They agree on {f(ja)} percent of {S['judge_graded']:,} graded answers ({S['judge_disagreements']} disagreements). Numbers below are luna's unless marked.", "",
         f"**Main result.** Final-day recall, structured noise at 20 percent minus faithful replay, mean over seeds: **{f(head)} points** (per seed: {[round(100*v) for v in head['values']] if head else 'n/a'}). Verdict: {verdict(head)}. Random noise at 40 percent was close to faithful on overall recall ({f(rand40_head)} points), but did not show a transfer advantage: far probes {f(rand40_far)} points and near-minus-far {f(pv.get('random_40_minus_faithful.transfer.near_minus_far'))} points.", "",
         f"Novel tasks (multi-session questions), structured 20 percent: {f(novel)} points, {verdict(novel)}. Far transfer probes, same arm: {f(far)} points, {verdict(far)}. Near-minus-far transfer, same arm: {f(nmf)} points, {verdict(nmf)}. DRM critical-lure false alarms after sleep: {f(lure)} points, {verdict(lure)}; the lure false-alarm rate was {percent_range('drm_lure_fa')}{', so this comparison is at the floor' if percent_range('drm_lure_fa') == '0 percent in every arm' else ''}.", "",
         *(((ROOT / "results" / "reading_v2.md").read_text(encoding="utf-8"), "") if (ROOT / "results" / "reading_v2.md").exists() else ()),
         "## Hypothesis under test", "",
         "Hoel's overfitted brain hypothesis predicts that noisy, dream-like replay should trade some fidelity for better generalization. v2 tests that prediction on a text-memory LLM agent at four corruption rates, with structured and random noise side by side, a transfer test built for it, and a day-eleven false-memory battery.", "",
         "## Outcome", "",
         f"{outcome_lead()} At 20 percent structured corruption, final recall was {f(by['structured_20']['final_acc'])} versus {f(by['faithful']['final_acc'])} for faithful replay, a paired difference of {f(head)} points; novel multi-session questions changed by {f(novel)} points and far transfer by {f(far)} points. Random noise at 40 percent stayed close to faithful on overall recall ({f(by['random_40']['final_acc'])} versus {f(by['faithful']['final_acc'])}; {f(rand40_head)} points) and on novel questions ({f(rand40_novel)} points), but far transfer changed by {f(rand40_far)} points. The day-eleven battery was near ceiling (DRM hits {percent_range('drm_hit')}, serial hits {percent_range('serial_hit')}, critical-lure false alarms {percent_range('drm_lure_fa')}), so it cannot test a false-memory difference. With three seeds these comparisons are exploratory, not confirmatory.", "",
         "## Method in brief", "",
         "Ten arms share one model, one life per seed, one agent prompt and one question schedule. Only the night step differs. No sleep keeps a raw window of the day's last turns, sized to the night's cap. Faithful replay has the model rewrite its memory from the day's transcript: the memory is a list of items with a gist line, details and a score from 1 to 5, and when it is over the cap the harness strips details from the lowest-scored items first and deletes whole items only when every item is down to its gist. "
         "Structured noise swaps, changes or splices 5, 10, 20 or 40 percent of the day's turns from earlier days before the same rewrite; random noise replaces or salts the same share of turns with text from an unrelated corpus. Days are about 30 LongMemEval sessions stitched to 130,000 tokens, with 12 hidden counter-default rules planted as 2 or 3 episodes each across the ten days. After night 10 each rule gets one near probe and one far probe. Day eleven is a Cao-style memory battery with new DRM lists from the USF association norms. Full detail in spec-v2.md and decisions.md.", "",
         "## Numbers, mean ± sd over three seeds (percent)", "",
          row(["arm", "evening (before sleep)", "morning (after sleep)", "one-night drop", "final recall", "final, days 1-5", "final, days 6-10", "final, novel (multi-session)", "final, abstention", "memory tokens, mean nights 1-10"]),
         "|---|---|---|---|---|---|---|---|---|---|"]
    for a, name in ARMS:
        v = by.get(a)
        if not v: L.append(row([name, "not run"] + [""] * 8)); continue
        L.append(row([name, f(v["evening_acc"]), f(v["morning_acc"]), f(v["one_night_drop"]), f(v["final_acc"]), f(v["final_acc_early"]), f(v["final_acc_late"]), f(v["final_acc_novel"]), f(v["final_abstention_acc"]), f(v["mean_memory_tokens"], pct=False)]))
    L += ["", "Paired differences against faithful replay, same seed (percentage points):", "",
          row(["comparison", "final recall", "final, novel", "one-night drop", "abstention", "transfer near", "transfer far", "transfer near minus far"]), "|---|---|---|---|---|---|---|---|"]
    for a, name in ARMS:
        if a == "faithful": continue
        g = lambda m: f(pv.get(f"{a}_minus_faithful.{m}"))
        L.append(row([f"{name} minus faithful", g("final_acc"), g("final_acc_novel"), g("one_night_drop"), g("final_abstention_acc"), g("transfer.near"), g("transfer.far"), g("transfer.near_minus_far")]))

    L += ["", "## Corruption-rate curve", "",
          "Faithful replay is the 0 percent point of both curves. Each cell is mean ± sd over seeds (percent).", "",
          row(["rate", "structured: final recall", "structured: novel", "structured: far transfer", "random: final recall", "random: novel", "random: far transfer"]), "|---|---|---|---|---|---|---|"]
    st_pts = {p["rate"]: p for p in curve.get("structured", [])}; rn_pts = {p["rate"]: p for p in curve.get("random", [])}
    for rate in (0.0, 0.05, 0.10, 0.20, 0.40):
        s, r = st_pts.get(rate), rn_pts.get(rate)
        c = lambda p, k: f(p[k]) if p else "not run"
        L.append(row([f"{int(rate*100)} percent", c(s, "final_acc"), c(s, "final_acc_novel"), c(s, "transfer_far"), c(r, "final_acc"), c(r, "final_acc_novel"), c(r, "transfer_far")]))

    L += ["", "## Final recall by delay", "",
          "Final-day recall of questions whose last evidence was N nights before the final questions (percent, mean over seeds; sd omitted, each cell rests on 4 to 21 questions per life).", "",
          row(["arm"] + [f"{d} night{'s' if d > 1 else ''}" for d in range(1, DAYS + 1)]), "|---|" + "---|" * DAYS]
    for a, name in ARMS:
        v = by.get(a)
        if not v: L.append(row([name, "not run"] + [""] * (DAYS - 1))); continue
        L.append(row([name] + [("n/a" if v["final_acc_by_delay"][str(d)] is None else f"{100*v['final_acc_by_delay'][str(d)]['mean']:.0f}") for d in range(1, DAYS + 1)]))

    L += ["", "## Transfer test", "",
          "Share of the 12 hidden rules the agent followed on a probe after night 10 (percent, mean ± sd over seeds). Near probes resemble the planted episodes; far probes apply the rule in a different kind of request. Hoel's account predicts the noisy arms lose less from near to far; the near-minus-far column is that comparison.", "",
          row(["arm", "near (luna)", "far (luna)", "near minus far", "near (Opus)", "far (Opus)", "rules with 2 episodes", "rules with 3 episodes"]), "|---|---|---|---|---|---|---|---|"]
    for a, name in ARMS:
        v = by.get(a)
        if not v or v.get("transfer.near") is None: L.append(row([name, "not run"] + [""] * 6)); continue
        L.append(row([name, f(v["transfer.near"]), f(v["transfer.far"]), f(v["transfer.near_minus_far"]), f(v["transfer.near_opus"]), f(v["transfer.far_opus"]), f(v["transfer_by_episodes"]["2"]), f(v["transfer_by_episodes"]["3"])]))
    L += ["", "Each rule passed an empty-memory check before the sweep: an agent with no memory followed it on under 20 percent of samples, so following it on a probe means the memory carried it."]

    L += ["", "## Memory size and forgetting per arm", "",
          "Memory tokens are the agent-facing text after a night, counted with Claude's tokenizer. Stripping and deletion are the harness's forgetting when the sleep step wrote more than the cap allows: details go from the lowest-scored items first, the last one cut at a sentence boundary (partial), and whole items go only when every item is down to its gist. Means cover nights 1-10; the day-11 battery night is reported separately in summary_v2.json." + (" For this original sweep, the stripping/deletion, nights-over-cap and sleep output/seconds totals still cover eleven nights because the saved per-run summaries did not split out the day-11 consolidation." if legacy else ""), "",
          row(["arm", "memory tokens, mean nights 1-10", "memory as share of cap", "tokens after night 10", "items after night 10", "details stripped", "of which partial", "items deleted", "nights over cap", "turns corrupted", "sleep output tokens per night", "sleep seconds per night"]),
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for a, name in ARMS:
        v = by.get(a)
        if not v: L.append(row([name, "not run"] + [""] * 10)); continue
        n = lambda k: f(v[k], pct=False)
        L.append(row([name, n("mean_memory_tokens"), f(v["mean_memory_fill"]), n("final_memory_tokens"), n("final_items"), n("details_stripped"), n("details_partial"), n("items_deleted"), n("nights_over_cap"), n("corrupted_turns"), n("sleep_output_tokens"), n("sleep_seconds")]))
    L += ["", "Memory tokens after each night, mean over seeds, with the cap:", "",
          row(["arm"] + [f"night {d+1} (cap {arms.CAPS[d]:,})" for d in range(DAYS)]), "|---|" + "---|" * DAYS]
    for a, name in ARMS:
        v = by.get(a)
        if not v: L.append(row([name, "not run"] + [""] * (DAYS - 1))); continue
        L.append(row([name] + [("n/a" if (len(v["memory_tokens_by_night"]) <= d or v["memory_tokens_by_night"][d] is None) else f"{v['memory_tokens_by_night'][d]['mean']:,.0f}") for d in range(DAYS)]))

    L += ["", "## Memory-effects battery, morning after the arm's own night step (percent)", "",
          row(["arm", "DRM hits", "DRM critical-lure false alarms", "DRM unrelated false alarms", "serial hits", "primacy (pos 1-3)", "middle (6-10)", "recency (13-15)", "fan 1 accuracy", "fan 2 accuracy"]), "|---|---|---|---|---|---|---|---|---|---|"]
    for a, name in ARMS:
        v = by.get(a, {}).get("battery_morning")
        if not v or v.get("drm_hit") is None: L.append(row([name, "not run"] + [""] * 8)); continue
        L.append(row([name, f(v["drm_hit"]), f(v["drm_lure_fa"]), f(v["drm_unrelated_fa"]), f(v["serial_hit"]), f(v["serial_primacy"]), f(v["serial_middle"]), f(v["serial_recency"]), f(v["pl_fan1_acc"]), f(v["pl_fan2_acc"])]))
    L += ["", "Same tests in the evening, with the study lists still in context, are in summary_v2.json under battery_evening. The DRM lists are new ones built from the USF free-association norms, because Opus recognised the classic lists in v1. Human reference points: Roediger and McDermott 1995 found people false-recognise the critical lure at about the same rate as studied words (0.98 to 1.11 of the hit rate, Tables 1 and 2); Cao, Schooler and Zafarani 2025 report 0.11 for GPT-4 with a hit rate of 1.", "", f"The battery is near ceiling: DRM hits are {percent_range('drm_hit')}, serial hits {percent_range('serial_hit')}, person-location fan-1 accuracy {percent_range('pl_fan1_acc')}, and critical-lure false alarms are {percent_range('drm_lure_fa')}. It therefore cannot discriminate the arms or test the false-memory prediction.", "",
          "## Housekeeping", "",
          f"Refusals: {sum(by[a]['refusals'] for a in by)}. Judge agreement per arm (luna against Opus): " + ", ".join(f"{NAMES[a]} {f(by[a]['judge_agreement'])}" for a in by) + ". Every request and response is in logs/calls/ as JSON; every call's tokens are in cost.jsonl; each run's memory after each night is in results/runs_v2/<arm>_s<seed>/memory_night<d>.txt and .json (items with ids and scores); every corruption (turn index, kind, before, after) and every transfer probe reply is in that run's state.json. Transfer rules, episodes and probes per seed are in data/transfer_v2/transfer_s<seed>.json.", "",
          "## What this does not show", "",
          "- Whether the agent dreams in any felt sense.", "- Whether the result holds when knowledge lives in weights rather than in a text memory.", "- Whether it holds past one model (claude-opus-5-5) or one cap curve (15 percent of each day, decaying with age).",
          "- Absolute accuracy is not comparable with published LongMemEval numbers: days are stitched from several users' histories, temporal-reasoning questions are excluded, and the judge is gpt-5.6-luna rather than gpt-4o.",
          "- Three seeds. Treat every arm comparison as exploratory rather than a confirmatory test; a difference inside one seed SD is not evidence of a difference. Recall rests on 100 questions per life, transfer on 24 probes per life.",
          "- The day-eleven battery is at ceiling on hits and at the floor on critical-lure false alarms, so it cannot show a false-memory effect. The battery night also uses each arm's own night step, so noisy arms corrupt the battery study material as well as their daily memories; a future battery should give every arm identical study material. A harder incidental-encoding battery is needed.",
          *(["- The original per-run summaries did not separate the day-11 consolidation from the ten-day memory totals; mean memory and fill are corrected here, but the stripping/deletion, nights-over-cap and sleep-time totals still include that night."] if legacy else []),
          "- The Letta replication check ran after the sweep, results in results/letta_check/summary.md.", ""]
    (ROOT / "results" / "results_v2.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L[:12]))


if __name__ == "__main__":
    main()
