"""Impact model pages: economic contribution of industries, what-if impacts, and the model's method and checks.
The model is built in src/io_model.py; these pages read its outputs and run small matrix calculations."""
import json
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import lib
from io_model import effects
from lib import OUT

MEASURES = {"jobs": ("Jobs", "{:,.0f}"), "labor_income": ("Labor income ($ millions)", "${:,.1f}M"),
            "value_added": ("Value added, GDP ($ millions)", "${:,.1f}M"), "output": ("Output, sales ($ millions)", "${:,.1f}M"),
            "taxes": ("State and local taxes ($ millions)", "${:,.2f}M")}
EFFECT_COLORS = {"Direct": lib.UND_GREEN, "Indirect": "#E5734B", "Induced": "#C9B37E"}
LIMITS = [
    "Fixed recipes: each industry is assumed to buy the same mix of inputs per dollar of sales, at fixed prices. "
    "The model has no supply limits, capacity constraints, crowding out or migration, so results are upper-bound "
    "estimates of how spending ripples through the economy.",
    "Local purchases are estimated with Flegg's location quotient method from national tables, not from a survey of "
    "North Dakota businesses. Results for small regions are less certain.",
    "Jobs are wage and salary jobs as counted by BLS QCEW; business owners and most farm operators are not included. "
    "Values are 2023 dollars.",
    "Taxes use North Dakota's average effective tax rates (Census tax collections divided by personal income, GDP or "
    "the value of oil production), not the tax rules of a specific business. Exemptions, incentives and timing are "
    "not modelled. Because BEA values North Dakota's oil and gas output below the value of production, the oil "
    "industry's total footprint, including severance taxes, is understated on the contribution page.",
    "State taxes are all taxes the state collects, whatever fund receives them; they are not general fund revenue. "
    "By the state constitution, 30% of oil and gas tax collections go to the Legacy Fund (N.D. Const. art. X, § 26), "
    "and part of the gross production tax is shared with counties, cities and school districts. The model's average "
    "oil and gas severance rate (collections / value of production) is 9.6%, close to the 10% statutory total of the "
    "5% gross production and 5% extraction taxes, less exemptions.",
]
REFS = ["flegg_webber1997", "flegg_tohmo2013", "miller_blair2022", "watson2007"]


def ready():
    if not (OUT / "io_model.npz").exists():
        st.info("The impact model has not been built yet. Run `py -3.15 src/run_all.py`.")
        return False
    return True


KEYS = ("A", "e", "w", "v", "c", "x", "tli", "tva", "tsev")


@st.cache_data(show_spinner=False)
def _model(stamp, prefix=""):
    z = np.load(OUT / "io_model.npz")
    places = [str(p) for p in z["places"]]
    if prefix and f"{prefix}0_A" not in z:
        return None
    models = {p: {k: z[f"{prefix}{i}_{k}"] for k in KEYS} for i, p in enumerate(places)}
    return [str(c) for c in z["codes"]], [str(n) for n in z["names"]], places, models


def model():
    return _model(lib._stamp("io_model.npz"))


def range_models():
    """Low and high cases of the model (see src/io_model.py: delta +/- 0.1, household spending +/- 10%), or None."""
    lo, hi = _model(lib._stamp("io_model.npz"), "lo_"), _model(lib._stamp("io_model.npz"), "hi_")
    return (lo[3], hi[3]) if lo and hi else (None, None)


def rng(lo, hi, fmt):
    return f"range {fmt.format(lo)} to {fmt.format(hi)}"


def range_note():
    p = params()
    r = p.get("range", {})
    if not r:
        return ""
    return (f"Ranges move the model's two most uncertain settings together: how much industries buy from local "
            f"suppliers (Flegg's delta, calibrated to {p['delta']:g}, set to {r['delta_low_case']:g} for the low case "
            f"and {r['delta_high_case']:g} for the high case) and how much of each dollar of earnings households spend "
            f"({p['household_spend_ratio'] * 100:.0f} cents, {r['spend_low_case'] * 100:.0f} to "
            f"{r['spend_high_case'] * 100:.0f} cents)."
            + (" A delta of 0 equals simple location quotients, which tend to overstate local buying, so read the "
               "high case as an upper bound." if r["delta_high_case"] == 0 else ""))


def params():
    return json.loads((OUT / "io_params.json").read_text())


def tr_share():
    return float(lib.table("io_tax_ratios.csv").household_sales_share.iloc[0])


WARN_SHARE, MAX_SHARE = 0.05, 0.25   # input-output results hold only for changes small relative to the economy


def shock_share(m, j, output):
    """Size of a new activity relative to the place's economy: its direct jobs as a share of all jobs in the model
    (or its sales as a share of all output when the industry has no job counts)."""
    jobs = float(np.sum(m["e"] * m["x"]))
    if m["e"][j] > 0 and jobs > 0:
        return output * m["e"][j] / jobs, jobs
    return output / float(np.sum(m["x"])), jobs


def place_label(p):
    return "North Dakota (statewide)" if p == "ND" else p


def short(name, n=38):
    return name if len(name) <= n else name[:n - 1] + "…"


# ------------------------------------------------------------------ contribution
def contribution_page():
    lib.header("Economic contribution", "How much each North Dakota industry supports across the economy: its own jobs "
               "and sales, plus the suppliers it buys from and the household spending of the people it employs.",
               "model", note="IPBA input-output model built from BEA, BLS and Census data (2023).")
    if not ready():
        return
    c = lib.table("io_contribution.csv", dtype={"code": str})
    places = list(dict.fromkeys(c.place))
    k = st.columns([2, 2])
    place = k[0].selectbox("Place", places, format_func=place_label, key="ct_place")
    lab = k[1].selectbox("Measure", [v[0] for v in MEASURES.values()], key="ct_measure")
    meas = {v[0]: key for key, v in MEASURES.items()}[lab]
    d = c[(c.place == place) & (c.direct_output > 0)].copy()
    d["taxes"] = d.state_taxes + d.local_taxes
    d["direct"] = {"jobs": d.direct_jobs, "output": d.direct_output, "labor_income": d.direct_labor_income,
                   "value_added": d.direct_value_added, "taxes": d.direct_taxes}[meas].fillna(0)
    d["spillover"] = (d[meas] - d.direct).clip(lower=0)
    top = d.sort_values(meas, ascending=False).head(15).iloc[::-1]
    fig = go.Figure()
    fig.add_bar(y=top.name.map(short), x=top.direct, name="In the industry itself", orientation="h",
                marker=dict(color=lib.UND_GREEN, line=dict(width=0)), hovertemplate="%{x:,.1f}")
    fig.add_bar(y=top.name.map(short), x=top.spillover, name="Supported in suppliers and by household spending",
                orientation="h", marker=dict(color="#E5734B", line=dict(width=0)), hovertemplate="%{x:,.1f}")
    has_range = f"{meas}_low" in top or (meas == "taxes" and "state_taxes_low" in top)
    if has_range:
        low = top[f"{meas}_low"] if meas != "taxes" else top.state_taxes_low + top.local_taxes_low
        high = top[f"{meas}_high"] if meas != "taxes" else top.state_taxes_high + top.local_taxes_high
        fig.add_trace(go.Scatter(y=top.name.map(short), x=top[meas], mode="markers", name="Range (low to high case)",
                                 marker=dict(color="rgba(0,0,0,0)", size=1),
                                 error_x=dict(type="data", array=(high - top[meas]).clip(lower=0),
                                              arrayminus=(top[meas] - low).clip(lower=0), color="#BBBBBB", thickness=1.5),
                                 customdata=np.c_[low, high], hovertemplate="range %{customdata[0]:,.1f} to "
                                                                            "%{customdata[1]:,.1f}<extra></extra>"))
    fig.update_layout(barmode="stack", hovermode="y unified")
    lib.show(lib.layout(fig, 560), "ct_chart", title=f"Top 15 industries by {lab.lower()} supported, {place_label(place)}")
    st.caption("Each bar is one industry's total footprint. The orange part is activity in other industries that depends "
               "on it. Footprints overlap (a supplier appears in several), so they must not be added together."
               + (" Gray lines show the low-to-high range. " + range_note() if has_range else ""))
    cols = ["name", "direct_jobs", "jobs", "labor_income", "value_added", "output", "state_taxes", "local_taxes"]
    if "jobs_low" in d:
        cols[3:3] = ["jobs_low", "jobs_high"]
    t = d.sort_values(meas, ascending=False)[cols]
    t = t.rename(columns={"name": "Industry", "direct_jobs": "Jobs in the industry", "jobs": "Total jobs supported",
                          "jobs_low": "Total jobs, low case", "jobs_high": "Total jobs, high case",
                          "labor_income": "Labor income supported ($M)", "value_added": "Value added supported ($M)",
                          "output": "Output supported ($M)", "state_taxes": "State taxes supported ($M)",
                          "local_taxes": "Local taxes supported ($M)"}).round(1)
    lib.data_table(t, "All industries (table)", key=f"contribution_{place}")
    lib.method_panel(["Contribution of an existing industry (Watson et al., 2007): its output in the place, plus the "
                      "output of local suppliers and of businesses serving its workers' household spending. The "
                      "industry's own sales are not counted twice.", *LIMITS], REFS)
    lib.source_line("bea_io", "qcew", "bea", "stateio", "taxes")


# ------------------------------------------------------------------ what-if
def whatif_page():
    lib.header("What-if impact", "Estimate the ripple effects of a new or expanding business: pick a place and an "
               "industry, and enter new jobs or new annual sales.", "model",
               note="IPBA input-output model built from BEA, BLS and Census data (2023). Estimates, not forecasts.")
    if not ready():
        return
    codes, names, places, models = model()
    k = st.columns([1.3, 2])
    place = k[0].selectbox("Place", places, format_func=place_label, key="wi_place")
    order = sorted(range(len(names)), key=lambda i: names[i])
    pick = k[1].selectbox("Industry", [names[i] for i in order], key="wi_industry",
                          index=[names[i] for i in order].index("Food and beverage and tobacco products"))
    j = names.index(pick)
    m = models[place]
    k = st.columns([1.3, 2])
    kind = k[0].radio("Change", ["New jobs", "New annual sales ($ millions)"], key="wi_kind")
    per_job = 1 / m["e"][j] if m["e"][j] > 0 else np.nan
    if kind == "New jobs":
        if not np.isfinite(per_job):
            st.warning("This industry has no job counts in the data; enter sales instead.")
            return
        amount = k[1].number_input("Number of new jobs", min_value=1, max_value=20000, value=100, step=10, key="wi_jobs")
        output = amount * per_job
    else:
        amount = k[1].number_input("New annual sales, $ millions", min_value=0.1, max_value=50000.0, value=25.0,
                                   step=5.0, key="wi_sales")
        output = float(amount)
    share, place_jobs = shock_share(m, j, output)
    size = (f"This change equals {share:.0%} of the roughly {lib.num(round(place_jobs, -2))} jobs in "
            f"{place_label(place)}.")
    if share > MAX_SHARE:
        st.error(f"{size} The model cannot estimate a change this large: input-output results assume the change is "
                 "small next to the economy, with no limits on workers, housing or suppliers (Miller & Blair, 2022). "
                 f"Enter a change under {MAX_SHARE:.0%} of the place's jobs, or choose a larger place.",
                 icon=":material/block:")
        return
    if share > WARN_SHARE:
        st.warning(f"{size} For a change this large, the results are likely too high: the model assumes enough "
                   "workers, housing and suppliers are available at today's prices.", icon=":material/warning:")
    res, vec = effects(m, j, output)
    res["taxes"] = res.state_taxes + res.local_taxes
    tot = res.sum()
    lo_m, hi_m = range_models()
    lo = hi = None
    if lo_m:
        lo = effects(lo_m[place], j, output)[0].sum()
        hi = effects(hi_m[place], j, output)[0].sum()
        for x in (lo, hi):
            x["taxes"] = x.state_taxes + x.local_taxes
    st.caption(f"Direct change: {lib.num(res.loc['Direct', 'jobs'])} jobs and ${output:,.1f} million of yearly sales "
               f"in {pick.lower()} ({'about $' + format(per_job * 1e3, ',.0f') + 'k of sales per job' if np.isfinite(per_job) else 'no job data'}).")
    jr = (lambda v: round(v, -1) if v >= 100 else v)
    r_ = (lambda k, f: rng(lo[k], hi[k], f) if lo is not None else None)
    c = st.columns(4)
    c[0].metric("Total jobs", lib.num(jr(tot.jobs)),
                r_("jobs", "{:,.0f}") if lo is not None else (f"{tot.jobs / max(res.loc['Direct', 'jobs'], 1e-9):.2f} per "
                                                              "direct job" if res.loc["Direct", "jobs"] > 0 else None),
                delta_color="off", delta_arrow="off")
    c[1].metric("Labor income", f"${tot.labor_income:,.1f}M", r_("labor_income", "${:,.1f}M"), delta_color="off",
                delta_arrow="off")
    c[2].metric("Value added (GDP)", f"${tot.value_added:,.1f}M", r_("value_added", "${:,.1f}M"), delta_color="off",
                delta_arrow="off")
    c[3].metric("Output (sales)", f"${tot.output:,.1f}M", r_("output", "${:,.1f}M") or
                f"{tot.output / output:.2f} per $1 of new sales", delta_color="off", delta_arrow="off")
    c = st.columns(4)
    c[0].metric("State and local taxes", f"${tot.state_taxes + tot.local_taxes:,.2f}M", r_("taxes", "${:,.2f}M"),
                delta_color="off", delta_arrow="off")
    c[1].metric("State taxes", f"${tot.state_taxes:,.2f}M", r_("state_taxes", "${:,.2f}M"), delta_color="off",
                delta_arrow="off")
    c[2].metric("Local taxes", f"${tot.local_taxes:,.2f}M", "mostly property and city sales taxes", delta_color="off",
                delta_arrow="off")
    c[3].metric("Multipliers", f"{tot.output / output:.2f} output", (f"{tot.jobs / res.loc['Direct', 'jobs']:.2f} jobs "
                "per direct job" if res.loc["Direct", "jobs"] > 0 else None), delta_color="off", delta_arrow="off")
    if lo is not None:
        st.caption("Central estimate, with a low-to-high range under each figure. " + range_note())
    fig = go.Figure()
    for eff in ("Direct", "Indirect", "Induced"):
        fig.add_bar(x=[MEASURES[k_][0].split(" (")[0] for k_ in MEASURES], y=[res.loc[eff, k_] / tot[k_] * 100 for k_ in MEASURES],
                    name={"Direct": "Direct", "Indirect": "Indirect (suppliers)", "Induced": "Induced (household spending)"}[eff],
                    marker=dict(color=EFFECT_COLORS[eff], line=dict(width=0)),
                    customdata=[res.loc[eff, k_] for k_ in MEASURES], hovertemplate="%{y:.0f}% (%{customdata:,.1f})")
    fig.update_layout(barmode="stack")
    fig.update_yaxes(ticksuffix="%")
    cols = st.columns([1.1, 1])
    with cols[0]:
        lib.show(lib.layout(fig, 380, "% of total effect"), "wi_split", title="Where the effects come from")
    with cols[1]:
        jobs_by = m["e"] * vec
        top = pd.DataFrame({"name": names, "jobs": jobs_by}).sort_values("jobs", ascending=False).head(10).iloc[::-1]
        f2 = go.Figure(go.Bar(y=top.name.map(short), x=top.jobs, orientation="h", marker=dict(color=lib.UND_GREEN, line=dict(width=0)),
                              hovertemplate="%{y}: %{x:,.1f} jobs<extra></extra>"))
        lib.show(lib.layout(f2, 380, legend=False), "wi_top", title="Industries where the jobs are")
    t = res.copy()
    t.loc["Total"] = tot
    if lo is not None:
        t.loc["Total, low case"] = lo[t.columns]
        t.loc["Total, high case"] = hi[t.columns]
    t = t.reset_index().rename(columns={"index": "Effect", "output": "Output ($M)", "jobs": "Jobs",
                                        "labor_income": "Labor income ($M)", "value_added": "Value added ($M)",
                                        "state_taxes": "State taxes ($M)", "local_taxes": "Local taxes ($M)",
                                        "taxes": "State and local taxes ($M)"})
    lib.data_table(t.round(2), "Results (table)", key="whatif_results")
    st.caption("Direct = the new activity itself. Indirect = purchases from local suppliers, and their suppliers. "
               "Induced = local spending of the wages earned. Results are rounded estimates for one year of operation "
               "at full scale.")
    lib.method_panel(["Effects = (I - A)^-1 x new final demand, with A the regional coefficient matrix. Type II adds "
                      "households (labor income in, consumer spending out).",
                      "New jobs are converted to sales with the industry's output per job in North Dakota.",
                      "Ranges: " + range_note(), *LIMITS], REFS)
    lib.source_line("bea_io", "qcew", "bea", "stateio", "taxes")


# ------------------------------------------------------------------ method and checks
def checks_page():
    lib.header("Impact model: method and checks", "How IPBA's input-output model is built from public data, how it "
               "compares with an independent model, and what it cannot do.", "model",
               note="Full method: docs/io_model_method.md in the project.")
    if not ready():
        return
    p = params()
    v = lib.table("io_validation.csv")
    cal = lib.table("io_calibration.csv")
    cmp_ = lib.table("io_stateio_compare.csv", dtype={"code": str})
    c = st.columns(4)
    c[0].metric("Model year", str(p["year"]))
    c[1].metric("Industries", "71")
    c[2].metric("FLQ delta (calibrated)", f"{p['delta']:.2f}", f"textbook value {p['delta_default']}", delta_color="off",
                delta_arrow="off")
    c[3].metric("Household spending per $ of labor income", f"{p['household_spend_ratio']:.2f}")
    st.markdown(
        "**How it works.** The model starts from the national Make and Use tables (BEA, 2023), which record what every "
        "industry buys from every other. It then estimates how much of those purchases stay inside North Dakota, or "
        "inside one planning region, using each place's industry mix (Flegg's location quotient method). Smaller and less "
        "specialized places buy more from outside, so their multipliers are lower.")
    cols = st.columns(2)
    with cols[0]:
        fig = go.Figure()
        fig.add_scatter(x=cal.delta, y=cal["ND weighted mean Type I output multiplier"], mode="lines+markers",
                        name="IPBA model, North Dakota", line=dict(color=lib.UND_GREEN, width=2.6))
        fig.add_scatter(x=cal.delta, y=cal["StateIO weighted mean"], mode="lines", name="EPA StateIO",
                        line=dict(color=lib.UND_GRAY, dash="dash", width=2))
        fig.add_vline(x=p["delta"], line_color=lib.MUTED, line_dash="dot")
        fig.update_xaxes(title="FLQ delta")
        lib.show(lib.layout(fig, 380, "Mean Type I output multiplier"), "cal_chart",
                 title="Calibration: choosing delta to match EPA StateIO")
    with cols[1]:
        d = cmp_[(cmp_.StateIO > 1) & (cmp_.ND_output_musd > 0)]
        fig = go.Figure(go.Scatter(x=d.StateIO, y=d.IPBA, mode="markers", text=d.name,
                                   marker=dict(size=np.sqrt(d.ND_output_musd) / 6 + 5, color=lib.UND_GREEN, opacity=.7,
                                               line=dict(color=lib.PANEL, width=1)),
                                   hovertemplate="%{text}<br>StateIO %{x:.2f}<br>IPBA %{y:.2f}<extra></extra>"))
        lo, hi = 1.0, float(max(d.StateIO.max(), d.IPBA.max())) + .05
        fig.add_scatter(x=[lo, hi], y=[lo, hi], mode="lines", line=dict(color=lib.MUTED, dash="dot"), hoverinfo="skip")
        fig.update_xaxes(title="EPA StateIO")
        lib.show(lib.layout(fig, 380, "IPBA model", legend=False), "cmp_chart",
                 title="Type I output multipliers by industry, North Dakota")
    st.caption("Left: the delta that makes the model's average match StateIO is used for the state and all regions. "
               "Right: each dot is an industry (size = ND output); dots on the dotted line agree exactly.")
    st.subheader("Validation table")
    vt = v.rename(columns={"check": "Check", "IPBA": "IPBA model", "benchmark": "Benchmark", "note": "Note"})
    st.dataframe(vt, hide_index=True, width="stretch", column_config={
        "IPBA model": st.column_config.NumberColumn(format="%.3f"), "Benchmark": st.column_config.NumberColumn(format="%.3f")})
    st.markdown("BEA's RIMS II multipliers are sold per region, so they are not used as a published benchmark. "
                "IPBA may check results privately against licensed models; licensed results are never published.")
    st.subheader("Multipliers by industry")
    m = lib.table("io_multipliers.csv", dtype={"code": str})
    pl = st.selectbox("Place", list(dict.fromkeys(m.place)), format_func=place_label, key="mc_place")
    mm = m[m.place == pl][["name", "output_type1", "output_type2", "jobs_type2", "jobs_per_million_type2",
                           "labor_income_type2", "value_added_type2"]].rename(columns={
        "name": "Industry", "output_type1": "Output, Type I", "output_type2": "Output, Type II",
        "jobs_type2": "Jobs per direct job, Type II", "jobs_per_million_type2": "Jobs per $1M of sales, Type II",
        "labor_income_type2": "Labor income, Type II", "value_added_type2": "Value added, Type II"})
    st.dataframe(mm.round(2), hide_index=True, width="stretch", height=360)
    st.caption("Output multipliers: total sales across the economy per $1 of new sales. Jobs per direct job and income "
               "multipliers are ratios of total to direct effects; they are large where direct jobs per dollar are few "
               "(for example farms, where QCEW does not count operators).")
    st.subheader("Tax rates used")
    tr = lib.table("io_tax_ratios.csv")
    tr = tr.assign(rate_pct=tr.rate * 100)[["level", "tax", "amount_musd", "base", "base_musd", "rate_pct", "data_year"]]
    tr["base"] = tr.base.map({"household": "Personal income", "business": "GDP", "severance_oil": "Value of oil production",
                              "severance_other": "Mining output (model)"})
    st.dataframe(tr.rename(columns={"level": "Level", "tax": "Tax", "amount_musd": "Collections ($M)", "base": "Tied to",
                                    "base_musd": "Base ($M)", "rate_pct": "Effective rate (%)", "data_year": "Year"}),
                 hide_index=True, width="stretch", column_config={
                     "Collections ($M)": st.column_config.NumberColumn(format="%.1f"),
                     "Base ($M)": st.column_config.NumberColumn(format="%.0f"),
                     "Effective rate (%)": st.column_config.NumberColumn(format="%.2f")})
    st.caption(f"Sales taxes are split between households ({tr_share():.0%} of the 2023 taxable sales base: retail, "
               "food service, recreation, personal services) and businesses. Household taxes follow labor income, "
               "business taxes follow value added, severance taxes follow oil, gas and mining sales.")
    st.subheader("Limits")
    st.markdown("\n".join(f"- {lib.esc(x)}" for x in LIMITS))
    lib.method_panel(["National coefficients: A = D x Bd from BEA summary Make and Use tables (before redefinitions), "
                      "imports removed commodity by commodity.",
                      "FLQ: r_ij = a_ij x min(1, lambda x SLQ_i / SLQ_j), lambda = [log2(1 + regional jobs / US jobs)]^delta; "
                      "regional coefficients are capped at the state's.",
                      "Type II: households spend (1 - social insurance contributions / compensation) x PCE / personal "
                      "income of each dollar of labor income (NIPA Table 2.1), bought locally in proportion to min(1, SLQ).",
                      "Jobs by place and industry: BLS QCEW 2023; planning regions from QCEW county data and BEA county "
                      "farm employment."], REFS)
    lib.source_line("bea_io", "qcew", "bea", "stateio", "taxes")
