"""
Phase 3 checkpoint report -- read-only analysis of whatever has landed so far.

Written 2026-10-19 for the checkpoint the author requires after the clean-subset
arm (20 runs), before the remaining ~70 h go in on top of it. Reads
results/metrics/ssrtd_real_results.csv and never writes to it.

The statistic that matters is NOT the raw overlap share but the enrichment over
independence (RESEARCH_LOG.md section 9.4, PAPER_NOTES item 18):

    enrichment = P(E-claimed | S-claimed) / P(E-claimed)
               = SE_overlap_005 / E_gt005_pct

which is 1.0 if the two supports are independent. On video_01 clean it is 2.42x.

    python -m src.phase3_checkpoint                     # default arm clean-subset
    python -m src.phase3_checkpoint --arm noise-subset
    python -m src.phase3_checkpoint --arm all --csv <path>
"""

import argparse
import csv
import math
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
RESULTS_CSV = PROJECT_DIR / "results" / "metrics" / "ssrtd_real_results.csv"
PLAN_CSV = PROJECT_DIR / "results" / "ssrtd_real" / "plan.csv"
ERROR_LOG = PROJECT_DIR / "logs" / "phase3_errors.log"
RUNNER_LOG = PROJECT_DIR / "logs" / "phase3_runner.log"


def f(row, key):
    """float or None -- blank cells are expected (noise columns on clean rows)."""
    v = (row.get(key) or "").strip()
    if v == "":
        return None
    try:
        return float(v)
    except ValueError:
        return None


def mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def sd(xs):
    if len(xs) < 2:
        return float("nan")
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def median(xs):
    s = sorted(xs)
    n = len(s)
    if n == 0:
        return float("nan")
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return float("nan"), float("nan")
    mx, my = mean(xs), mean(ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return float("nan"), float("nan")
    r = sxy / math.sqrt(sxx * syy)
    return r, _p_from_r(r, n)


def _ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(xs, ys):
    return pearson(_ranks(xs), _ranks(ys))


def _p_from_r(r, n):
    """Two-sided p for H0: rho = 0, via the t approximation. Indicative only."""
    if abs(r) >= 1.0:
        return 0.0
    t = abs(r) * math.sqrt((n - 2) / (1 - r * r))
    df = n - 2
    # Student t survival function by continued-fraction-free incomplete beta.
    x = df / (df + t * t)
    return _betainc_half(df / 2.0, 0.5, x)


def _betainc_half(a, b, x):
    """Regularised incomplete beta I_x(a,b) by series; small-df accuracy is enough."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    front = math.exp(a * math.log(x) + b * math.log(1 - x) - lbeta) / a
    # Lentz continued fraction
    fv, c, d = 1.0, 1.0, 0.0
    for i in range(0, 300):
        m = i // 2
        if i == 0:
            num = 1.0
        elif i % 2 == 0:
            num = (m * (b - m) * x) / ((a + 2 * m - 1) * (a + 2 * m))
        else:
            num = -((a + m) * (a + b + m) * x) / ((a + 2 * m) * (a + 2 * m + 1))
        d = 1.0 + num * d
        if abs(d) < 1e-30:
            d = 1e-30
        d = 1.0 / d
        c = 1.0 + num / c
        if abs(c) < 1e-30:
            c = 1e-30
        fv *= c * d
        if abs(1.0 - c * d) < 1e-12:
            break
    return front * (fv - 1.0)


def load(csv_path, arm):
    if not csv_path.exists():
        raise SystemExit(f"no results yet at {csv_path}")
    with open(csv_path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if arm != "all":
        rows = [r for r in rows if r.get("arm") == arm]
    rows.sort(key=lambda r: r.get("video_id", ""))
    return rows


def expected(arm):
    if not PLAN_CSV.exists():
        return None
    with open(PLAN_CSV, newline="", encoding="utf-8") as fh:
        plan = list(csv.DictReader(fh))
    if arm != "all":
        plan = [p for p in plan if p.get("arm") == arm]
    return len(plan)


def report(rows, arm, csv_path=RESULTS_CSV):
    exp = expected(arm) if Path(csv_path) == RESULTS_CSV else None
    print(f"=== Phase 3 checkpoint: arm {arm} ===")
    print(f"rows: {len(rows)}" + (f" of {exp} planned" if exp else ""))
    if not rows:
        return

    print()
    hdr = (f"{'video_id':12s} {'S>.05%':>7s} {'E>.05%':>7s} {'P(E|S)%':>8s} "
           f"{'enrich':>8s} {'S_px':>9s} {'both':>8s} {'exp.ind':>8s} "
           f"{'fg%':>6s} {'min':>5s}")
    print(hdr)
    print("-" * len(hdr))

    enr, ovl, fg, sclaim = [], [], [], []
    tot_both, tot_exp = 0.0, 0.0
    for r in rows:
        s5, e5, ov = f(r, "S_gt005_pct"), f(r, "E_gt005_pct"), f(r, "SE_overlap_005")
        ratio = (ov / e5) if (ov is not None and e5) else None
        spx, both = f(r, "S_claimed_px"), f(r, "SE_both_px")
        # voxels that would overlap if the two supports were independent
        exp_ind = (spx * e5 / 100.0) if (spx is not None and e5 is not None) else None
        if both is not None and exp_ind:
            tot_both += both
            tot_exp += exp_ind
        print(f"{r.get('video_id',''):12s} "
              f"{_fmt(s5,3):>7s} {_fmt(e5,3):>7s} {_fmt(ov,3):>8s} "
              f"{(_fmt(ratio,1)+'x') if ratio else '      --':>8s} "
              f"{_fmt(spx,0):>9s} {_fmt(both,0):>8s} {_fmt(exp_ind,1):>8s} "
              f"{_fmt(f(r,'foreground_density'),3):>6s} "
              f"{_fmt((f(r,'total_seconds') or 0)/60.0,1):>5s}")
        if ratio is not None:
            enr.append(ratio)
            ovl.append(ov)
            d = f(r, "foreground_density")
            if d is not None:
                fg.append(d)
                sclaim.append(ratio)

    print()
    print("--- spread across the arm ---")
    for name, xs in (("enrichment (x)", enr), ("raw overlap P(E|S) %", ovl),
                     ("foreground_density %", fg)):
        if xs:
            print(f"{name:24s} min {min(xs):7.3f}  median {median(xs):7.3f}  "
                  f"max {max(xs):7.3f}  mean {mean(xs):7.3f}  sd {sd(xs):6.3f}")
    if tot_exp:
        print(f"{'POOLED over the arm':24s} {tot_both:,.0f} overlapping voxels against "
              f"{tot_exp:,.1f} expected under independence = "
              f"**{tot_both/tot_exp:.1f}x**")
        print("  (pooled is the figure to quote across videos: the per-video "
              "ratio is high-variance when a scene is near-empty and its")
        print("   supports are only thousands of voxels.)")
    if enr:
        above = sum(1 for x in enr if x > 1.0)
        print(f"{'enrichment > 1.0':24s} {above}/{len(enr)} videos"
              + ("  (replicates)" if above == len(enr) else "  <-- NOT unanimous"))
        weak = [r.get("video_id") for r, x in zip(rows, enr) if x < 1.5]
        if weak:
            print(f"{'videos below 1.5x':24s} {', '.join(weak)}")

    if len(fg) >= 3:
        print()
        print("--- does it depend on how busy the scene is? ---")
        rp, pp = pearson(fg, sclaim)
        rs, ps = spearman(fg, sclaim)
        print(f"enrichment vs foreground_density:  Pearson r {rp:+.3f} (p~{pp:.3f}), "
              f"Spearman rho {rs:+.3f} (p~{ps:.3f}), n={len(fg)}")
        ro = [o for r, o in zip(rows, ovl)]
        rp2, pp2 = pearson(fg, ro[:len(fg)])
        print(f"raw overlap vs foreground_density: Pearson r {rp2:+.3f} (p~{pp2:.3f})")
        print("p-values are indicative (t approximation, n small, videos not "
              "independent samples of a population).")

    print()
    print("--- health ---")
    times = [(f(r, "total_seconds") or 0) / 60.0 for r in rows]
    if times:
        print(f"wall time per run: min {min(times):.1f}  median {median(times):.1f}  "
              f"max {max(times):.1f} min")
    peaks = [f(r, "peak_wset_mb") for r in rows if f(r, "peak_wset_mb")]
    if peaks:
        print(f"peak working set:  max {max(peaks):.0f} MB")
    nonconv = [r.get("video_id") for r in rows
               if str(r.get("converged", "")).strip().lower() in ("false", "0")]
    print(f"did not hit tol in max_iter: {len(nonconv)}/{len(rows)}"
          + (f"  ({', '.join(nonconv[:6])}{'...' if len(nonconv) > 6 else ''})"
             if nonconv else ""))
    commits = sorted({r.get("commit", "")[:7] for r in rows})
    numpys = sorted({r.get("numpy_version", "") for r in rows})
    paths = sorted({r.get("s_update_path", "") for r in rows})
    print(f"commit(s) {commits}  numpy {numpys}  s_update_path {paths}")

    if ERROR_LOG.exists() and ERROR_LOG.stat().st_size:
        print()
        print(f"--- {ERROR_LOG.name} (last 15 lines) ---")
        lines = ERROR_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        for ln in lines[-15:]:
            print("  " + ln)
    else:
        print("no entries in logs/phase3_errors.log")


def _fmt(v, nd):
    return "--" if v is None else f"{v:.{nd}f}"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arm", default="clean-subset",
                    help="clean-subset | noise-subset | factor2-subset | clean-rest | all")
    ap.add_argument("--csv", default=str(RESULTS_CSV))
    args = ap.parse_args()
    report(load(Path(args.csv), args.arm), args.arm, Path(args.csv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
