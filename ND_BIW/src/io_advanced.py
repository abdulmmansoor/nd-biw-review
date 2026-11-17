"""Step: advanced impact and contribution analysis on top of IPBA's input-output model (src/io_model.py).

All methods use the same regional matrices as the impact pages (public data only):

 1. Key sectors (linkages). Backward linkage: Rasmussen's normalized column sums of the Leontief inverse (how much an
    industry pulls from local suppliers per dollar of its sales). Forward linkage: normalized row sums of the Ghosh
    inverse, read as a price/supply model (Dietzenbacher, 1997): how much local production depends on the industry as
    a supplier. Key sectors are above average on both (Rasmussen, 1956; Hirschman, 1958; Miller & Blair, 2022, ch. 12).
 2. Hypothetical extraction (Dietzenbacher & Lahr, 2013; Miller & Lahr, 2001). Total: the place's output, jobs and
    value added that would be lost if the industry disappeared (its final demand gone and no local buying or selling),
    in the Type II model. Backward: lost if it bought nothing from local suppliers (Leontief). Forward: lost if no
    local industry bought from it (Ghosh supply-side model).
 3. Monte Carlo uncertainty of multipliers (ten Raa & Steel, 1994; Lenzen, Wood & Wiedmann, 2010). Each draw takes
    delta (FLQ) and household spending within the model's range, and multiplies every regional coefficient by an
    independent lognormal factor (coefficient error); 90% intervals = 5th to 95th percentiles of 500 draws.
 4. Functions used live by the dashboard: net impact (gross results less displaced local sales and the spending of
    workers who live elsewhere; Bess & Ambargis, 2011) and structural path analysis (the largest chains from new
    final demand to jobs; Defourny & Thorbecke, 1984).
Writes outputs/io_linkages.csv and outputs/io_uncertainty.csv.
"""
import json
import numpy as np
import pandas as pd
from config import OUT

N_DRAWS = 500
COEF_SD = 0.20                   # lognormal sd of coefficient error (about +/-20%)
SEED = 20261117


# ------------------------------------------------------------------ helpers
def leontief(A):
    return np.linalg.inv(np.eye(len(A)) - A)


def type2(m):
    n = len(m["A"])
    A2 = np.zeros((n + 1, n + 1))
    A2[:n, :n], A2[:n, n], A2[n, :n] = m["A"], m["c"], m["w"]
    return A2


def ghosh(A, x):
    """Allocation coefficients B = X^-1 A X (share of each industry's output sold to each local industry)."""
    with np.errstate(divide="ignore", invalid="ignore"):
        B = np.where(x[:, None] > 0, A * x[None, :] / x[:, None], 0.0)
    return np.nan_to_num(B)


# ------------------------------------------------------------------ 1. linkages
def linkages(m):
    """Rasmussen backward and Ghosh forward linkage indices (1 = average), for industries with output in the place."""
    A, x = m["A"], m["x"]
    act = x > 0
    L = leontief(A)[np.ix_(act, act)]
    G = np.linalg.inv(np.eye(act.sum()) - ghosh(A, x)[np.ix_(act, act)])
    k = act.sum()
    bl, fl = np.full(len(x), np.nan), np.full(len(x), np.nan)
    bl[act] = L.sum(axis=0) / (L.sum() / k)
    fl[act] = G.sum(axis=1) / (G.sum() / k)
    return bl, fl


def classify(bl, fl):
    if np.isnan(bl):
        return ""
    if bl >= 1 and fl >= 1:
        return "Key sector"
    if bl >= 1:
        return "Strong buyer (backward)"
    if fl >= 1:
        return "Strong supplier (forward)"
    return "Weakly linked"


# ------------------------------------------------------------------ 2. hypothetical extraction
def extraction(m):
    """Losses (output, jobs, value added, labor income) from extracting each industry: total (Type II), backward and
    forward (Type I)."""
    A, x, e, w, v = m["A"], m["x"], m["e"], m["w"], m["v"]
    n = len(A)
    A2 = type2(m)
    x2 = np.r_[x, w @ x]                                   # households' income as the extra row
    f2 = x2 - A2 @ x2                                      # final demand that reproduces today's economy
    f1 = x - A @ x
    B = ghosh(A, x)
    vrow = x - B.T @ x                                     # primary inputs per industry (Ghosh): x' = v'(I - B)^-1
    out = []
    for j in range(n):
        if x[j] <= 0:
            out.append({})
            continue
        # total: industry j gone (no final demand, no local purchases or sales)
        a = A2.copy()
        a[j, :], a[:, j] = 0, 0
        f = f2.copy()
        f[j] = 0
        xb = leontief(a) @ f
        dt = x2[:n] - xb[:n]
        # backward: j buys nothing locally
        a1 = A.copy()
        a1[:, j] = 0
        db = x - leontief(a1) @ f1
        # forward: no local industry buys from j (supply-side)
        b = B.copy()
        b[j, :] = 0
        df = x - np.linalg.solve((np.eye(n) - b).T, vrow)
        out.append({"hem_output": dt.sum(), "hem_jobs": e @ dt, "hem_value_added": v @ dt, "hem_labor_income": w @ dt,
                    "backward_output": db.sum(), "backward_jobs": e @ db,
                    "forward_output": df.sum(), "forward_jobs": e @ df})
    return pd.DataFrame(out)


# ------------------------------------------------------------------ 3. Monte Carlo
def perturb(m, rng):
    A = m["A"] * rng.lognormal(-COEF_SD ** 2 / 2, COEF_SD, m["A"].shape)
    s = A.sum(axis=0)
    A = np.where(s > 0.95, A * 0.95 / np.maximum(s, 1e-12), A)      # keep every column productive
    c = m["c"] * rng.lognormal(-COEF_SD ** 2 / 2, COEF_SD, m["c"].shape)
    return {**m, "A": A, "c": c}


def multipliers(m):
    n = len(m["A"])
    L1, L2 = leontief(m["A"]), leontief(type2(m))[:n, :n]
    return {"output_type1": L1.sum(axis=0), "output_type2": L2.sum(axis=0), "jobs_per_million_type2": m["e"] @ L2,
            "labor_income_per_million_type2": m["w"] @ L2, "value_added_per_million_type2": m["v"] @ L2}


def monte_carlo(nat, delta, spend, places, n_draws=N_DRAWS, seed=SEED):
    import io_model
    rng = np.random.default_rng(seed)
    draws = {p: {k: [] for k in ("output_type1", "output_type2", "jobs_per_million_type2",
                                 "labor_income_per_million_type2", "value_added_per_million_type2")} for p in places}
    for _ in range(n_draws):
        d = rng.uniform(max(delta - io_model.DELTA_STEP, 0.0), delta + io_model.DELTA_STEP)
        s = spend * rng.uniform(1 - io_model.SPEND_RANGE, 1 + io_model.SPEND_RANGE)
        models = io_model.build_models(nat, d, s)
        state = perturb(models["ND"], rng)
        for p in places:
            m = state if p == "ND" else perturb(models[p], rng)
            if p != "ND":                                # regions never buy more locally than the state
                m["A"], m["c"] = np.minimum(m["A"], state["A"]), np.minimum(m["c"], state["c"])
            for k, v in multipliers(m).items():
                draws[p][k].append(v)
    return {p: {k: np.array(v) for k, v in dd.items()} for p, dd in draws.items()}


# ------------------------------------------------------------------ 4. used live by the dashboard
def net_effects(effects_df, displacement=0.0, resident_share=1.0):
    """Net effects from gross ones (rows Direct, Indirect, Induced). Displacement: share of the new sales taken from
    existing local businesses (their direct, indirect and induced effects are lost). Resident share: share of the new
    jobs filled by people living in the place (commuters spend most of their pay where they live, so induced effects
    shrink in proportion)."""
    net = effects_df * (1 - displacement)
    net.loc["Induced"] = net.loc["Induced"] * resident_share
    return net


def structural_paths(m, j, output, top=12, tol=1e-4, depth=5, names=None):
    """Largest paths of jobs from `output` ($ millions) of new final demand in industry j, through the Type II model
    (households as a node). A path j -> i1 -> ... -> ik carries output A[i1, j] x ... x output, and its jobs are
    e[ik] times that output. Returns (paths DataFrame, total jobs)."""
    A2 = type2(m)
    n = len(m["A"])
    e = np.r_[m["e"], 0.0]                                  # households employ no one directly
    label = list(names or range(n)) + ["Household spending"]
    total = float(e @ (leontief(A2)[:, j] * output))
    rows = []

    def walk(path, val):
        k = path[-1]
        jobs = e[k] * val
        if jobs > 0:
            rows.append({"path": " → ".join(str(label[i]) for i in path), "steps": len(path) - 1, "jobs": jobs})
        if len(path) > depth:
            return
        nxt = A2[:, k] * val
        for i in np.nonzero(nxt > tol * output)[0]:
            walk(path + [i], nxt[i])
    walk([j], float(output))
    p = pd.DataFrame(rows).sort_values("jobs", ascending=False).head(top) if rows else pd.DataFrame(
        columns=["path", "steps", "jobs"])
    if total > 0:
        p["share"] = p.jobs / total
    return p.reset_index(drop=True), total


# ------------------------------------------------------------------ main
def main(n_draws=N_DRAWS):
    import io_model
    p = json.loads((OUT / "io_params.json").read_text())
    nat = io_model.national()
    delta, spend = p["delta"], p["household_spend_ratio"]
    models = io_model.build_models(nat, delta, spend)
    codes, names = nat["codes"], nat["names"]
    rows = []
    for place, m in models.items():
        bl, fl = linkages(m)
        ex = extraction(m)
        tot_jobs, tot_out = float(m["e"] @ m["x"]), float(m["x"].sum())
        d = pd.DataFrame({"place": place, "code": codes, "name": names, "output": m["x"], "jobs": m["e"] * m["x"],
                          "backward_index": bl, "forward_index": fl})
        d["linkage_type"] = [classify(b, f) for b, f in zip(bl, fl)]
        d = pd.concat([d, ex.reindex(range(len(d)))], axis=1)
        d["hem_jobs_share"] = d.hem_jobs / tot_jobs * 100
        d["hem_output_share"] = d.hem_output / tot_out * 100
        rows.append(d)
    lk = pd.concat(rows, ignore_index=True)
    lk.to_csv(OUT / "io_linkages.csv", index=False)
    mc = monte_carlo(nat, delta, spend, list(models), n_draws)
    central = {pl: multipliers(m) for pl, m in models.items()}
    urows = []
    for pl, dd in mc.items():
        for k, arr in dd.items():
            q = np.percentile(arr, [5, 50, 95], axis=0)
            urows.append(pd.DataFrame({"place": pl, "code": codes, "name": names, "measure": k,
                                       "central": central[pl][k], "p05": q[0], "p50": q[1], "p95": q[2],
                                       "output": models[pl]["x"]}))
    un = pd.concat(urows, ignore_index=True)
    un = un[un.output > 0].drop(columns="output")
    un.to_csv(OUT / "io_uncertainty.csv", index=False)
    nd = lk[lk.place == "ND"]
    print(f"    ND key sectors: {int((nd.linkage_type == 'Key sector').sum())}; largest extraction loss: "
          f"{nd.loc[nd.hem_jobs.idxmax(), 'name']} ({nd.hem_jobs.max():,.0f} jobs); Monte Carlo {n_draws} draws")
    return {}


if __name__ == "__main__":
    main()
