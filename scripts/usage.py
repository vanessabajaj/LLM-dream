"""
Record the /usage figure so the harness can pause at the stop point (decisions.md, "Usage pause on the Max plan").
  python scripts/usage.py set 20          # you are at 20 percent of the weekly limit right now
  python scripts/usage.py status          # budget left this period at list price
The defaults are the original author's figures. Override them for another plan:
  python scripts/usage.py set 20 --weekly-usd 500 --stop-pct 80 --reset 2026-10-15T00:00:00-04:00
Environment variables WP_WEEKLY_USD, WP_STOP_PCT and WP_RESET do the same.
"""
import sys, json, time, pathlib, datetime, argparse, os
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "harness"))
import api

DEFAULT_WEEKLY_USD = 1450.0
DEFAULT_STOP_PCT = 62
DEFAULT_RESET = "2026-10-15T00:00:00-04:00"


def parse_reset(value):
    dt = datetime.datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt


def main():
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["set", "status"])
    p.add_argument("pct", nargs="?", type=float, help="current /usage percentage (for set)")
    p.add_argument("--weekly-usd", type=float, default=float(os.environ.get("WP_WEEKLY_USD", DEFAULT_WEEKLY_USD)))
    p.add_argument("--stop-pct", type=float, default=float(os.environ.get("WP_STOP_PCT", DEFAULT_STOP_PCT)))
    p.add_argument("--reset", default=os.environ.get("WP_RESET", DEFAULT_RESET), help="ISO timestamp of the next weekly reset")
    a = p.parse_args()
    if a.cmd == "set":
        if a.pct is None:
            p.error("set needs the current /usage percentage")
        b = {"pct_at_set": a.pct, "set_ts": time.time(), "weekly_usd": a.weekly_usd, "stop_pct": a.stop_pct,
             "reset_ts": parse_reset(a.reset).timestamp(), "set_at": time.ctime()}
        api.BUDGET_FILE.write_text(json.dumps(b, indent=1), encoding="utf-8")
        print(f"set: {a.pct} percent at {b['set_at']}; room until {a.stop_pct} percent is {(a.stop_pct-a.pct)/100*a.weekly_usd:.0f} USD list price")
    st = api.budget_status()
    if st is None:
        print("no budget set"); return 1
    allowed, spent, start = st
    print(f"budget this period: {allowed:.0f} USD list price from {time.ctime(start)}; spent {spent:.2f}; left {allowed-spent:.2f}")
    print(f"real money since v2 start: {api.real_spend_v2():.2f} USD of the {api.SPEND_CAP_USD:.0f} USD cap")


if __name__ == "__main__":
    sys.exit(main())
