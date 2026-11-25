"""Step: IPBA input-output impact model for North Dakota and its 8 planning regions (public data only).

Method (documented in docs/io_model_method.md):
 1. National domestic coefficients, industry by industry: A = D x Bd, where B = Use / industry output, D = Make /
    commodity output (market shares), and Bd removes imports commodity by commodity (BEA summary tables, 2023).
 2. Regionalisation with Flegg's location quotient (FLQ): r_ij = a_ij x min(1, FLQ_ij), FLQ_ij = lambda x SLQ_i/SLQ_j
    (lambda x SLQ_i on the diagonal), lambda = [log2(1 + regional jobs / US jobs)]^delta. delta is calibrated so that
    North Dakota's Type I output multipliers match EPA's StateIO model on average; the same delta is used for regions.
 3. Type I multipliers from (I - A_r)^-1. Type II adds households: labor income is the household "input"; households
    spend HH_SPEND of each dollar of labor income on consumption, in the national pattern of personal consumption,
    bought locally in proportion to min(1, SLQ).
 4. Effects: output, jobs (QCEW wage and salary jobs), labor income (employee compensation) and value added.
Fixed coefficients: no price, supply or capacity effects. Writes outputs/io_model.npz (matrices for the dashboard),
io_multipliers.csv, io_contribution.csv, io_validation.csv and io_params.json.
"""
import json
import numpy as np
import pandas as pd
from config import LIVE, OUT, REGIONS
import io_data
from io_data import stateio

DELTA_DEFAULT = 0.3
DELTA_GRID = [round(x, 2) for x in np.arange(0.0, 0.61, 0.05)]
FINAL = ["F010", "F02S", "F02E", "F02N", "F02R", "F030", "F06C", "F06S", "F06E", "F06N", "F07C", "F07S", "F07E", "F07N",
         "F10C", "F10S", "F10E", "F10N"]          # domestic final uses (exports F040 and imports F050 handled apart)
NO_JOBS_SLQ1 = ["HS", "482"]                     # no QCEW jobs (owner-occupied housing; railroads): treated as average


# ------------------------------------------------------------------ national
def national():
    use, make, names = io_data.tables()
    t = pd.read_csv(OUT / "io_industries.csv")
    codes = t.code.tolist()
    U = use.loc[codes, codes]
    g = use.loc["Total Industry Output", codes]
    V = make.loc[codes, codes]
    q = make.loc["Total Commodity Output", codes]
    dom_use = U.sum(axis=1) + use.loc[codes, FINAL].sum(axis=1)
    imports = -use.loc[codes, "F050"]
    s = (imports / dom_use.where(dom_use > 0)).fillna(0).clip(0, 1)
    B = U.div(g.where(g > 0), axis=1).fillna(0)
    D = V.div(q.where(q > 0), axis=1).fillna(0)
    A = D.values @ (B.values * (1 - s.values)[:, None])
    pce = use.loc[codes, "F010"] * (1 - s)
    h = D.values @ pce.values / use.loc[codes, "F010"].sum()
    return {"codes": codes, "names": t.name.tolist(), "A": A, "g": g.values, "va": (use.loc["Total Value Added", codes] / g).values,
            "comp": (use.loc["V001", codes] / g).values, "h": h, "import_share": s.values, "t": t}


def household_spend_ratio():
    """Consumption per dollar of employee compensation: (1 - social insurance contributions / compensation) x PCE /
    personal income, NIPA Table 2.1, model year."""
    d = pd.read_csv(LIVE / "nipa" / "NipaDataA.txt", dtype=str)
    d.columns = ["code", "year", "value"]
    v = d[d.year == str(io_data.IO_YEAR)].set_index("code").value.str.replace(",", "").astype(float)
    return (1 - v["A061RC"] / v["A033RC"]) * v["DPCERC"] / v["A065RC"]


# ------------------------------------------------------------------ regional
def slq(jobs_r, jobs_n, codes):
    with np.errstate(divide="ignore", invalid="ignore"):
        s = (jobs_r / jobs_r.sum()) / (jobs_n / jobs_n.sum())
    s = pd.Series(s, index=codes).replace([np.inf, -np.inf], np.nan)
    s[[c for c in NO_JOBS_SLQ1 if c in s.index]] = 1.0
    return s.fillna(0).values


def flq(A, s, size, delta):
    lam = np.log2(1 + size) ** delta if delta > 0 else 1.0
    with np.errstate(divide="ignore", invalid="ignore"):
        cilq = np.where(s[None, :] > 0, s[:, None] / s[None, :], 0.0)
    f = lam * cilq
    np.fill_diagonal(f, lam * s)
    return A * np.minimum(f, 1.0), lam


def regional(nat, place, delta, spend, cap=None):
    """Regional model. `cap` (the state model) keeps a planning region from buying more of its inputs or consumer goods
    at home than the whole state does: anything bought inside a region is also bought inside the state."""
    t = nat["t"]
    codes = nat["codes"]
    jr, jn = t[f"jobs_{place}"].values, t.jobs_US.values
    s = slq(jr, jn, codes)
    size = jr.sum() / jn.sum()
    Ar, lam = flq(nat["A"], s, size, delta)
    prod, pay = t.productivity_ND.values, t.pay_ratio_ND.values
    with np.errstate(divide="ignore", invalid="ignore"):
        out_per_job = np.where(jn > 0, nat["g"] / jn, np.nan) * prod          # $ millions per job
    e = np.where(np.isfinite(out_per_job) & (out_per_job > 0), 1 / out_per_job, 0.0)
    w = np.minimum(nat["comp"] * pay / prod, nat["va"])                     # labor income per $ of output
    x = np.where(jn > 0, jr * out_per_job, nat["g"] * size)                  # regional output, $ millions
    c = nat["h"] * np.minimum(s, 1.0) * spend
    if cap is not None:
        Ar, c = np.minimum(Ar, cap["A"]), np.minimum(c, cap["c"])
    return {"A": Ar, "e": e, "w": w, "v": nat["va"], "c": c, "x": np.nan_to_num(x), "slq": s, "lambda": lam,
            "size": size, "jobs": jr}


def leontief(A):
    return np.linalg.inv(np.eye(len(A)) - A)


def type2(m):
    n = len(m["A"])
    A2 = np.zeros((n + 1, n + 1))
    A2[:n, :n], A2[:n, n], A2[n, :n] = m["A"], m["c"], m["w"]
    return A2


def tax_rates(ratios, codes, x_nd):
    """Effective tax rates per model base (see src/tax_ratios.py):
    tli = (state, local) taxes per $ of labor income (household taxes / personal income x personal income share),
    tva = (state, local) taxes per $ of value added (business taxes / GDP),
    tsev = state severance taxes per $ of output: oil and gas (collections / value of production) and mining."""
    r = ratios
    pis = r.pi_share_of_labor_income.iloc[0]
    tli = np.array([r[(r.level == lv) & (r.base == "household")].rate.sum() * pis for lv in ("state", "local")])
    tva = np.array([r[(r.level == lv) & (r.base == "business")].rate.sum() for lv in ("state", "local")])
    tsev = np.zeros(len(codes))
    tsev[codes.index("211")] = r[r.base == "severance_oil"].rate.sum()           # per $ of oil and gas sales
    i212 = codes.index("212")
    tsev[i212] = r[r.base == "severance_other"].amount_musd.sum() / x_nd[i212] if x_nd[i212] > 0 else 0.0
    return tli, tva, tsev


def taxes(m, vec):
    """(state, local) taxes in $ millions for an output vector, if the model carries tax rates."""
    if "tli" not in m:
        return np.nan, np.nan
    li, va = m["w"] @ vec, m["v"] @ vec
    return (m["tli"][0] * li + m["tva"][0] * va + m["tsev"] @ vec, m["tli"][1] * li + m["tva"][1] * va)


def effects(m, j, output):
    """Direct, indirect and induced effects of `output` ($ millions) of new final demand for industry j."""
    n = len(m["A"])
    L1 = leontief(m["A"])[:, j] * output
    L2 = leontief(type2(m))[:n, j] * output
    d = np.zeros(n)
    d[j] = output
    rows = {}
    for name, vec in (("Direct", d), ("Indirect", L1 - d), ("Induced", L2 - L1)):
        st_, lo = taxes(m, vec)
        rows[name] = {"output": vec.sum(), "jobs": m["e"] @ vec, "labor_income": m["w"] @ vec, "value_added": m["v"] @ vec,
                      "state_taxes": st_, "local_taxes": lo}
    return pd.DataFrame(rows).T, L2


def multipliers(m):
    n = len(m["A"])
    L1, L2 = leontief(m["A"]), leontief(type2(m))[:n, :n]
    out = {}
    for k, coef in (("output", np.ones(n)), ("jobs", m["e"]), ("labor_income", m["w"]), ("value_added", m["v"])):
        t1, t2 = coef @ L1, coef @ L2
        with np.errstate(divide="ignore", invalid="ignore"):
            out[f"{k}_type1"] = np.where(coef > 0, t1 / coef, np.nan) if k != "output" else t1
            out[f"{k}_type2"] = np.where(coef > 0, t2 / coef, np.nan) if k != "output" else t2
        out[f"{k}_per_million_type2"] = t2          # effect per $1 million of final demand
        # the same effect per $1 million split into direct (the industry itself), indirect (local suppliers and their
        # suppliers) and induced (local spending of the labor income earned); the three add up to the Type II total
        out[f"{k}_direct_per_million"] = coef
        out[f"{k}_indirect_per_million"] = t1 - coef
        out[f"{k}_induced_per_million"] = t2 - t1
    return pd.DataFrame(out)


def contribution(m):
    """Economic contribution of each industry's existing output (Watson et al., 2007): the industry's own sales to
    itself and to its customers are not counted again, by zeroing its row in the coefficient matrix.

    Each measure is split into direct (the industry itself), indirect (local suppliers and their suppliers: Type I
    total minus direct) and induced (local household spending of the labor income earned: Type II minus Type I);
    direct + indirect + induced = the total."""
    n = len(m["A"])
    rows = []
    A2 = type2(m)
    A1 = m["A"]
    for j in range(n):
        if m["x"][j] <= 0:
            rows.append({k: 0.0 for k in ("output", "jobs", "labor_income", "value_added", "state_taxes", "local_taxes",
                                          *(f"{e}_{x}" for e in EFFECTS for x in SPLIT))})
            continue
        a1, a2 = A1.copy(), A2.copy()
        a1[j, :], a2[j, :n] = 0, 0
        v1 = leontief(a1)[:, j] * m["x"][j]
        v2 = leontief(a2)[:n, j] * m["x"][j]
        st_, lo = taxes(m, v2)
        d = np.zeros(n)
        d[j] = m["x"][j]
        dst, dlo = taxes(m, d)
        s1, l1 = taxes(m, v1)
        row = {"output": v2.sum(), "jobs": m["e"] @ v2, "labor_income": m["w"] @ v2, "value_added": m["v"] @ v2,
               "typeI_output": v1.sum(), "state_taxes": st_, "local_taxes": lo}
        for e, vec in (("direct", d), ("indirect", v1 - d), ("induced", v2 - v1)):
            row.update({f"{e}_output": vec.sum(), f"{e}_jobs": m["e"] @ vec, f"{e}_labor_income": m["w"] @ vec,
                        f"{e}_value_added": m["v"] @ vec})
        row["direct_taxes"], row["indirect_taxes"], row["induced_taxes"] = dst + dlo, s1 + l1 - dst - dlo, st_ + lo - s1 - l1
        rows.append(row)
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ StateIO cross-check
EFFECTS = ("direct", "indirect", "induced")
SPLIT = ("output", "jobs", "labor_income", "value_added", "taxes")


def stateio_multipliers(codes):
    s = stateio()
    du, mk, xo = s["DomesticUse"], s["Make"], s["IndustryOutput"]
    nd = [f"{c}/US-ND" for c in codes]
    U = du.reindex(index=nd, columns=nd).fillna(0).values
    M = mk.reindex(index=nd, columns=nd).fillna(0).values
    xs = xo.to_series() if hasattr(xo, "to_series") else xo.iloc[:, 0]
    x = xs.reindex(nd).fillna(0).values
    q = M.sum(axis=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        B = np.where(x[None, :] > 0, U / x[None, :], 0)
        D = np.where(q[None, :] > 0, M / q[None, :], 0)
    A = D @ B
    return leontief(A).sum(axis=0), x


def calibrate(nat, spend, sio, weights):
    rows = []
    for d in DELTA_GRID:
        m = regional(nat, "ND", d, spend)
        mult = leontief(m["A"]).sum(axis=0)
        ok = (sio > 1) & (weights > 0)
        err = np.average(mult[ok] - sio[ok], weights=weights[ok])
        mae = np.average(np.abs(mult[ok] - sio[ok]), weights=weights[ok])
        rows.append({"delta": d, "ND weighted mean Type I output multiplier": np.average(mult[ok], weights=weights[ok]),
                     "StateIO weighted mean": np.average(sio[ok], weights=weights[ok]), "mean difference": err,
                     "mean absolute difference": mae, "correlation": np.corrcoef(mult[ok], sio[ok])[0, 1]})
    t = pd.DataFrame(rows)
    best = float(t.loc[t["mean difference"].abs().idxmin(), "delta"])
    return best, t


def implan_benchmark(mult):
    """Private check against the user's own IMPLAN multipliers. IMPLAN results are licensed and never published: the
    comparison is written to outputs/private/, which no dashboard page reads. Expected file (see docs/io_model_method.md):
    data/raw/implan/multipliers.csv with columns place, code, output_type1, output_type2, jobs_type2."""
    f = OUT.parent / "data" / "raw" / "implan" / "multipliers.csv"
    if not f.exists():
        return
    im = pd.read_csv(f, dtype={"code": str})
    cols = [c for c in ("output_type1", "output_type2", "jobs_type2") if c in im]
    cmp_ = mult.merge(im[["place", "code"] + cols], on=["place", "code"], suffixes=("_ipba", "_implan"))
    priv = OUT / "private"
    priv.mkdir(exist_ok=True)
    cmp_.to_csv(priv / "implan_compare.csv", index=False)
    print(f"    private IMPLAN benchmark: {len(cmp_)} industry-place pairs compared (not published)")


# ------------------------------------------------------------------ main
def places():
    return ["ND"] + list(REGIONS)


# Uncertainty range: the two settings the results are most sensitive to, moved within plausible bounds together.
#  - delta (regional purchase adjustment, FLQ): calibrated value +/- DELTA_STEP (never below 0). Flegg & Tohmo (2013)
#    report region-specific deltas spread around their calibrated values by about this much.
#  - household spending per $ of labor income: +/- SPEND_RANGE (consumer saving and out-of-state spending vary).
# Low = less local buying and spending (higher delta, lower spending); high = the opposite.
DELTA_STEP = 0.1
SPEND_RANGE = 0.10


def build_models(nat, delta, spend):
    state = regional(nat, "ND", delta, spend)
    return {p: (state if p == "ND" else regional(nat, p, delta, spend, cap=state)) for p in places()}


def ranges(nat, delta, spend):
    lo = build_models(nat, delta + DELTA_STEP, spend * (1 - SPEND_RANGE))
    hi = build_models(nat, max(delta - DELTA_STEP, 0.0), spend * (1 + SPEND_RANGE))
    return lo, hi


def main():
    nat = national()
    spend = household_spend_ratio()
    codes = nat["codes"]
    sio, sio_x = stateio_multipliers(codes)
    nd0 = regional(nat, "ND", DELTA_DEFAULT, spend)
    delta, cal = calibrate(nat, spend, sio, nd0["x"])
    models = build_models(nat, delta, spend)
    lo_models, hi_models = ranges(nat, delta, spend)
    ratios = pd.read_csv(OUT / "io_tax_ratios.csv")
    tli, tva, tsev = tax_rates(ratios, codes, models["ND"]["x"])
    for mm_ in (models, lo_models, hi_models):
        for m in mm_.values():
            m["tli"], m["tva"], m["tsev"] = tli, tva, tsev
    # multipliers
    frames = []
    for p, m in models.items():
        mm = multipliers(m)
        mm.insert(0, "code", codes)
        mm.insert(1, "name", nat["names"])
        mm.insert(0, "place", p)
        mm["jobs"], mm["output_musd"] = m["jobs"], m["x"]
        frames.append(mm)
    mult = pd.concat(frames, ignore_index=True)
    mult.to_csv(OUT / "io_multipliers.csv", index=False)
    # contribution
    frames = []
    for p, m in models.items():
        c = contribution(m)
        lo, hi = contribution(lo_models[p]), contribution(hi_models[p])
        for k in ("jobs", "labor_income", "value_added", "output", "state_taxes", "local_taxes"):
            c[f"{k}_low"], c[f"{k}_high"] = lo[k].values, hi[k].values
        c.insert(0, "code", codes)
        c.insert(1, "name", nat["names"])
        c.insert(0, "place", p)
        frames.append(c)
    pd.concat(frames, ignore_index=True).to_csv(OUT / "io_contribution.csv", index=False)
    # validation
    nd_m = mult[mult.place == "ND"].set_index("code").output_type1
    us_mult = leontief(nat["A"]).sum(axis=0)
    val = []
    w = models["ND"]["x"]
    ok = (sio > 1) & (w > 0)
    val.append({"check": "ND Type I output multipliers vs EPA StateIO (output-weighted mean)",
                "IPBA": np.average(nd_m.values[ok], weights=w[ok]), "benchmark": np.average(sio[ok], weights=w[ok]),
                "note": f"delta calibrated to {delta}; correlation across industries "
                        f"{np.corrcoef(nd_m.values[ok], sio[ok])[0, 1]:.2f}"})
    for d in (0.2, DELTA_DEFAULT, 0.4):
        m = regional(nat, "ND", d, spend)
        val.append({"check": f"ND Type I output multiplier with delta = {d} (sensitivity)",
                    "IPBA": np.average(leontief(m["A"]).sum(axis=0)[ok], weights=w[ok]), "benchmark": np.nan,
                    "note": "higher delta = more import leakage, smaller multipliers"})
    m = regional(nat, "ND", 0.0, spend)
    val.append({"check": "ND Type I output multiplier with simple LQ (no FLQ size adjustment)",
                "IPBA": np.average(leontief(m["A"]).sum(axis=0)[ok], weights=w[ok]), "benchmark": np.nan,
                "note": "simple LQ is known to overstate regional multipliers (Flegg & Tohmo, 2013)"})
    val.append({"check": "US Type I output multiplier (national ceiling)", "IPBA": np.average(us_mult[ok], weights=w[ok]),
                "benchmark": np.nan, "note": "regional multipliers must be below the national ones"})
    bad = int((nd_m.values > us_mult + 1e-9).sum())
    val.append({"check": "Industries where ND multiplier exceeds the US multiplier", "IPBA": bad, "benchmark": 0, "note": ""})
    reg_bad = sum(int((mult[mult.place == r].output_type1.values > nd_m.values + 1e-9).sum()) for r in REGIONS)
    val.append({"check": "Industry-region pairs where a region exceeds the state multiplier", "IPBA": reg_bad, "benchmark": 0,
                "note": "regional coefficients are capped at the state's"})
    # taxes: rates applied to the whole ND economy should give back actual collections (labor income in the model is
    # QCEW-based compensation, not all personal income, so a gap is expected)
    x = models["ND"]["x"]
    st_all, lo_all = taxes(models["ND"], x)
    act = ratios.groupby("level").amount_musd.sum()
    val.append({"check": "State taxes implied for the whole ND economy vs actual collections ($ millions)",
                "IPBA": st_all, "benchmark": act["state"],
                "note": "Census state tax collections, FY2023. Lower because BEA's oil and gas output for ND is below the "
                        "value of production, and income not paid as wages is not modelled"})
    val.append({"check": "Local taxes implied for the whole ND economy vs actual collections ($ millions)",
                "IPBA": lo_all, "benchmark": act["local"], "note": "Census state and local government finances, local taxes"})
    pd.DataFrame(val).to_csv(OUT / "io_validation.csv", index=False)
    cal.to_csv(OUT / "io_calibration.csv", index=False)
    pd.DataFrame({"code": codes, "name": nat["names"], "IPBA": nd_m.values, "StateIO": sio, "US": us_mult,
                  "ND_output_musd": w}).to_csv(OUT / "io_stateio_compare.csv", index=False)
    implan_benchmark(mult)
    # matrices for the dashboard's what-if page
    arrays = {"codes": np.array(codes), "names": np.array(nat["names"]), "places": np.array(places())}
    for pre, mm_ in (("", models), ("lo_", lo_models), ("hi_", hi_models)):
        for i, (p, m) in enumerate(mm_.items()):
            for k in ("A", "e", "w", "v", "c", "x", "tli", "tva", "tsev"):
                arrays[f"{pre}{i}_{k}"] = m[k]
    np.savez_compressed(OUT / "io_model.npz", **arrays)
    params = {"year": io_data.IO_YEAR, "delta": delta, "delta_default": DELTA_DEFAULT, "household_spend_ratio": spend,
              "range": {"delta_low_case": delta + DELTA_STEP, "delta_high_case": max(delta - DELTA_STEP, 0.0),
                        "spend_low_case": spend * (1 - SPEND_RANGE), "spend_high_case": spend * (1 + SPEND_RANGE)},
              "lambda": {p: m["lambda"] for p, m in models.items()}, "size": {p: m["size"] for p, m in models.items()},
              "tax_per_labor_income": {"state": tli[0], "local": tli[1]},
              "tax_per_value_added": {"state": tva[0], "local": tva[1]},
              "severance_per_dollar_oil_gas_sales": float(tsev[codes.index("211")])}
    (OUT / "io_params.json").write_text(json.dumps(params, indent=1))
    print(f"    IO model {io_data.IO_YEAR}: delta {delta} (calibrated to StateIO), household spending {spend:.3f} per $ of labor "
          f"income; ND mean Type I output multiplier {val[0]['IPBA']:.3f} vs StateIO {val[0]['benchmark']:.3f}")
    return {}


if __name__ == "__main__":
    main()
