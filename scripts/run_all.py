"""Cross-platform sweep runner: every arm x seed, resumable, one run at a time.

  python scripts/run_all.py --backend subscription
  python scripts/run_all.py --backend fake --arms faithful structured_20 --day-tokens 20000 --skip-battery
  python scripts/run_all.py --seeds 0 --days 3 --out results/runs_smoke

Finished runs are skipped. Exit codes: 2 setup error, 3 Max-plan budget pause, 4 judge gate, other run errors pass through.
The aggregate step runs only for the real results/runs_v2 sweep; smoke runs keep their own directory.
A run folder holding only a committed summary.json (the original sweep) is skipped and never overwritten,
so new runs need their own --out.
"""
import argparse, json, os, pathlib, subprocess, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "harness"))
import arms


def state_done(path):
    try:
        return "all" in json.loads(path.read_text(encoding="utf-8"))["phases_done"]
    except Exception:
        return False


def write_summary(d, env, log):
    """analyze.py --run into d/summary.json; its stderr goes to the log so a warning cannot corrupt the JSON."""
    with open(d / "summary.json", "w", encoding="utf-8") as f, open(log, "a", encoding="utf-8") as e:
        subprocess.run([sys.executable, str(ROOT / "harness" / "analyze.py"), "--run", str(d)],
                       cwd=ROOT, env=env, stdout=f, stderr=e, check=True)


def append(path, text):
    with open(path, "a", encoding="utf-8") as f:
        f.write(text + "\n")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    p.add_argument("--arms", nargs="+", choices=arms.ARMS, default=arms.ARMS)
    p.add_argument("--backend", default=os.environ.get("WP_BACKEND", "subscription"), choices=["subscription", "api", "fake"])
    p.add_argument("--out", default=None)
    p.add_argument("--days", type=int, default=10)
    p.add_argument("--day-tokens", type=int)
    p.add_argument("--skip-final", action="store_true")
    p.add_argument("--skip-battery", action="store_true")
    p.add_argument("--skip-transfer", action="store_true")
    p.add_argument("--require-preview", action="store_true", help="require results/transfer_preview.md before starting")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()

    out = pathlib.Path(a.out) if a.out else ROOT / "results" / ("runs_fake" if a.backend == "fake" else "runs_v2")
    out = out if out.is_absolute() else ROOT / out
    logs = ROOT / "logs" / out.name
    env = dict(os.environ, WP_BACKEND=a.backend, PYTHONUNBUFFERED="1")

    for seed in a.seeds:
        life = ROOT / "data" / "lives_v2" / f"life_s{seed}.json"
        if not life.exists() and not a.dry_run:
            print(f"missing {life}; run scripts/rebuild_lives.py first"); return 2
    if not a.skip_transfer and not a.dry_run:
        for seed in a.seeds:
            t = ROOT / "data" / "transfer_v2" / f"transfer_s{seed}.json"
            if not t.exists():
                print(f"missing {t}; build it with harness/transfer.py build {seed}"); return 2
    if a.require_preview and not (ROOT / "results" / "transfer_preview.md").exists() and not a.dry_run:
        print("results/transfer_preview.md is missing"); return 2
    if a.backend == "subscription" and not a.dry_run:
        rc = subprocess.run([sys.executable, str(ROOT / "scripts" / "usage.py"), "status"], cwd=ROOT, env=env).returncode
        if rc != 0:
            print("set the Max-plan budget first: scripts/usage.py set <percent>"); return 2

    logs.mkdir(parents=True, exist_ok=True)
    print(f"backend {a.backend}; out {out}; seeds {a.seeds}; arms {a.arms}")
    for seed in a.seeds:
        for arm in a.arms:
            d = out / f"{arm}_s{seed}"
            log = logs / f"{arm}_s{seed}.log"
            if state_done(d / "state.json"):
                print(f"skip {arm}_s{seed} (done)")
                if not a.dry_run:
                    write_summary(d, env, log)
                continue
            if (d / "summary.json").exists() and not (d / "state.json").exists():
                # a committed result from the original sweep: never rerun into it or overwrite its summary
                print(f"skip {arm}_s{seed} (published summary only; use --out for new runs)")
                continue
            cmd = [sys.executable, str(ROOT / "harness" / "run_arm.py"), arm, str(seed), "--days", str(a.days), "--out", str(out)]
            if a.day_tokens: cmd += ["--day-tokens", str(a.day_tokens)]
            if a.skip_final: cmd.append("--skip-final")
            if a.skip_battery: cmd.append("--skip-battery")
            if a.skip_transfer: cmd.append("--skip-transfer")
            print(f"start {arm}_s{seed}")
            if a.dry_run:
                print("  " + " ".join(cmd)); continue
            append(log, f"{arm}_s{seed}: {' '.join(cmd)}")
            with open(log, "a", encoding="utf-8") as f:
                rc = subprocess.run(cmd, cwd=ROOT, env=env, stdout=f, stderr=subprocess.STDOUT).returncode
            if rc == 3:
                print("PAUSED at the Max-plan budget stop point; update scripts/usage.py set N, then rerun"); return 3
            if rc != 0:
                print(f"{arm}_s{seed} exited {rc}; see {log}"); return rc
            write_summary(d, env, log)
            with open(log, "a", encoding="utf-8") as f:
                rc = subprocess.run([sys.executable, str(ROOT / "scripts" / "judge_check.py"), "--runs-dir", str(out)],
                                    cwd=ROOT, env=env, stdout=f, stderr=subprocess.STDOUT).returncode
            if rc != 0:
                print(f"judge gate failed after {arm}_s{seed}; see {log}"); return 4
            if out == ROOT / "results" / "runs_v2":
                with open(logs / "analyze_latest.txt", "w", encoding="utf-8") as f:
                    subprocess.run([sys.executable, str(ROOT / "harness" / "analyze.py")],
                                   cwd=ROOT, env=env, stdout=f, stderr=subprocess.STDOUT, check=True)

    if not a.dry_run and out == ROOT / "results" / "runs_v2":
        with open(logs / "analyze_latest.txt", "w", encoding="utf-8") as f:
            subprocess.run([sys.executable, str(ROOT / "harness" / "analyze.py")],
                           cwd=ROOT, env=env, stdout=f, stderr=subprocess.STDOUT, check=True)
        with open(logs / "write_results.txt", "w", encoding="utf-8") as f:
            subprocess.run([sys.executable, str(ROOT / "harness" / "write_results.py")],
                           cwd=ROOT, env=env, stdout=f, stderr=subprocess.STDOUT, check=True)
        print("wrote results/results_v2.md")
    elif not a.dry_run:
        print(f"done; per-run summaries are in {out}; aggregate only runs for results/runs_v2")
    return 0


if __name__ == "__main__":
    sys.exit(main())
