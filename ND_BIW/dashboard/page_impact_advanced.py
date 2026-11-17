"""Impact model: advanced analysis (key sectors, hypothetical extraction, net impact and job paths, Monte Carlo
uncertainty). Calculations are in src/io_advanced.py; the net impact and paths are computed live on the page."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import lib
from io_advanced import net_effects, structural_paths
from io_model import effects
from lib import OUT
from page_impact import EFFECT_COLORS, EFFECT_NAMES, LIMITS, model, place_label, ready, short

REFS = ["rasmussen1956", "hirschman1958", "dietzenbacher1997", "miller_lahr2001", "dietzenbacher_lahr2013",
        "bess_ambargis2011", "defourny_thorbecke1984", "tenraa_steel1994", "lenzen_wood_wiedmann2010",
        "miller_blair2022"]
TYPE_COLORS = {"Key sector": lib.UND_GREEN, "Strong buyer (backward)": "#E5734B", "Strong supplier (forward)": "#C9B37E",
               "Weakly linked": lib.UND_GRAY}
MC_MEASURES = {"Output multiplier, Type II": "output_type2", "Output multiplier, Type I": "output_type1",
               "Jobs per $1 million of sales": "jobs_per_million_type2",
               "Labor income per $1 of sales": "labor_income_per_million_type2",
               "Value added per $1 of sales": "value_added_per_million_type2"}


def tables_ready():
    if not all((OUT / f).exists() for f in ("io_linkages.csv", "io_uncertainty.csv")):
        st.info("The advanced tables have not been built yet. Run `py -3.15 src/run_all.py`.")
        return False
    return True


# ------------------------------------------------------------------ 1. key sectors
def key_sectors(lk, place):
    d = lk[(lk.place == place) & lk.backward_index.notna()].copy()
    fig = go.Figure()
    for t, color in TYPE_COLORS.items():
        s = d[d.linkage_type == t]
        fig.add_scatter(x=s.backward_index, y=s.forward_index, mode="markers", name=f"{t} ({len(s)})", text=s.name,
                        marker=dict(size=np.sqrt(s.output.clip(lower=0)) / 4 + 6, color=color, opacity=.8,
                                    line=dict(color=lib.PANEL, width=1)),
                        hovertemplate="%{text}<br>backward %{x:.2f}, forward %{y:.2f}<extra></extra>")
    for v, axis in ((1, "x"), (1, "y")):
        (fig.add_vline if axis == "x" else fig.add_hline)(v, line_color=lib.MUTED, line_dash="dot")
    lib.layout(fig, 500, "Forward linkage (as a supplier)", title=f"Key sectors, {place_label(place)}")
    fig.update_xaxes(title="Backward linkage (as a buyer)")
    fig.update_layout(legend=dict(orientation="h", x=0, xanchor="left", y=-0.2, yanchor="top"),
                      margin=dict(b=110))                 # four groups: legend under the chart, clear of the title
    lib.show(fig, "adv_link")
    st.caption("1 = the average industry. Backward linkage: how much the industry buys from local suppliers, and they "
               "from theirs, per dollar of its sales. Forward linkage: how much local production relies on the industry "
               "as a supplier. Key sectors are above average on both. Dot size = the industry's output. The indexes "
               "are per dollar; the extraction tab shows size.")
    t = d.sort_values(["linkage_type", "backward_index"], ascending=[True, False])[
        ["name", "linkage_type", "backward_index", "forward_index", "jobs"]]
    lib.data_table(t.rename(columns={"name": "Industry", "linkage_type": "Type", "backward_index": "Backward linkage",
                                     "forward_index": "Forward linkage", "jobs": "Jobs"}).round(2),
                   "Linkages (table)", key=f"adv_link_t_{place}")


# ------------------------------------------------------------------ 2. extraction
def extraction(lk, place):
    d = lk[(lk.place == place) & lk.hem_jobs.notna()].copy()
    top = d.sort_values("hem_jobs", ascending=False).head(15).iloc[::-1]
    fig = go.Figure()
    fig.add_bar(y=top.name.map(short), x=top.jobs, name="Jobs in the industry", orientation="h",
                marker=dict(color=lib.UND_GREEN, line=dict(width=0)))
    fig.add_bar(y=top.name.map(short), x=(top.hem_jobs - top.jobs).clip(lower=0), name="Other jobs lost with it",
                orientation="h", marker=dict(color="#E5734B", line=dict(width=0)))
    fig.update_layout(barmode="stack", hovermode="y unified")
    lib.show(lib.layout(fig, 520), "adv_hem", title=f"Jobs lost if the industry disappeared, {place_label(place)}")
    st.caption("Hypothetical extraction: the industry's own sales vanish and it neither buys from nor sells to local "
               "businesses; the rest of the economy is recalculated (Type II, households included). This is the total "
               "linkage measure of an industry's importance, a stricter alternative to the contribution footprint.")
    t = d.sort_values("hem_jobs", ascending=False)[["name", "jobs", "hem_jobs", "hem_jobs_share", "hem_value_added",
                                                     "backward_jobs", "forward_jobs"]]
    lib.data_table(t.rename(columns={
        "name": "Industry", "jobs": "Jobs in the industry", "hem_jobs": "Jobs lost if it disappeared",
        "hem_jobs_share": "% of the place's jobs", "hem_value_added": "Value added lost ($M)",
        "backward_jobs": "Jobs lost if it bought nothing locally", "forward_jobs": "Jobs lost if no one bought from it locally"}
    ).round(1), "Extraction results (table)", key=f"adv_hem_t_{place}")
    st.caption("Backward and forward columns separate the two ways an industry ties into the local economy: as a buyer "
               "from local suppliers (backward, Leontief) and as a supplier to local industries (forward, Ghosh "
               "supply-side model). Losses overlap across industries and must not be added together.")


# ------------------------------------------------------------------ 3. net impact and paths
def net_and_paths(place):
    codes, names, places, models = model()
    m = models[place]
    order = sorted(range(len(names)), key=lambda i: names[i])
    k = st.columns([2, 1])
    pick = k[0].selectbox("Industry of the new activity", [names[i] for i in order], key="adv_ind",
                          index=[names[i] for i in order].index("Food and beverage and tobacco products"))
    j = names.index(pick)
    per_job = 1 / m["e"][j] if m["e"][j] > 0 else np.nan
    if np.isfinite(per_job):
        jobs = k[1].number_input("New jobs", min_value=1, max_value=20000, value=100, step=10, key="adv_jobs")
        output = jobs * per_job
    else:
        output = k[1].number_input("New annual sales ($ millions)", min_value=0.1, value=10.0, key="adv_sales")
    k = st.columns(2)
    disp = k[0].slider("Share of sales taken from existing local businesses (displacement)", 0, 90, 0, 5,
                       key="adv_disp", format="%d%%") / 100
    res_ = k[1].slider("Share of new workers who live in the place", 10, 100, 100, 5, key="adv_res", format="%d%%") / 100
    st.caption("Guide: an export-oriented plant selling outside the place displaces little (0-10%); a new store, "
               "restaurant or service that mainly serves local customers can take half or more of its sales from "
               "existing businesses. Workers who commute in spend most of their pay where they live.")
    gross, _ = effects(m, j, output)
    net = net_effects(gross, disp, res_)
    cols = ["jobs", "labor_income", "value_added", "output"]
    lab = {"jobs": "Jobs", "labor_income": "Labor income ($M)", "value_added": "Value added ($M)", "output": "Output ($M)"}
    c = st.columns(4)
    for col, kk in zip(c, cols):
        g, nn = gross[kk].sum(), net[kk].sum()
        col.metric(f"{lab[kk]}, net", f"{nn:,.0f}" if kk == "jobs" else f"${nn:,.1f}M",
                   f"gross {g:,.0f}" if kk == "jobs" else f"gross ${g:,.1f}M", delta_color="off", delta_arrow="off")
    t = pd.concat({"Gross": gross[cols], "Net": net[cols]}, axis=1)
    t.index = [EFFECT_NAMES[i] for i in t.index]
    t.loc["Total"] = t.sum()
    t.columns = [f"{a}: {lab[b]}" for a, b in t.columns]
    lib.data_table(t.round(1).reset_index().rename(columns={"index": "Effect"}), "Gross and net effects (table)",
                   key="adv_net_t")
    st.subheader("Where the jobs come from: structural paths")
    paths, total = structural_paths(m, j, output, names=names)
    if paths.empty or total <= 0:
        st.info("No job paths for this industry in this place.")
        return
    p = paths.iloc[::-1]
    fig = go.Figure(go.Bar(y=[short(x, 70) for x in p.path], x=p.jobs, orientation="h",
                           marker=dict(color=[EFFECT_COLORS["Direct" if s == 0 else ("Induced" if "Household" in x
                                                                                      else "Indirect")]
                                              for s, x in zip(p.steps, p.path)], line=dict(width=0)),
                           customdata=p.share * 100, hovertemplate="%{y}<br>%{x:,.1f} jobs (%{customdata:.1f}%)"
                                                                   "<extra></extra>"))
    lib.show(lib.layout(fig, max(320, 30 * len(p) + 80), legend=False), "adv_spa",
             title=f"Largest job paths, gross ({paths.share.sum():.0%} of {total:,.0f} jobs)")
    st.caption("Each bar is one chain: the new activity buys from an industry, which buys from another, and so on; the "
               "jobs are counted where the chain ends. Green = the activity itself, orange = supplier chains, tan = "
               "chains through household spending. The rest of the jobs are spread over many small paths.")
    lib.data_table(paths.assign(share=paths.share * 100).round(2).rename(columns={
        "path": "Path", "steps": "Steps", "jobs": "Jobs", "share": "% of total jobs"}), "Paths (table)", key="adv_spa_t")


# ------------------------------------------------------------------ 4. uncertainty
def uncertainty(un, place):
    lab = st.selectbox("Multiplier", list(MC_MEASURES), key="adv_mc")
    d = un[(un.place == place) & (un.measure == MC_MEASURES[lab])].sort_values("central", ascending=False)
    top = d.head(20).iloc[::-1]
    fig = go.Figure(go.Scatter(x=top.central, y=top.name.map(short), mode="markers", name="Central (published)",
                               marker=dict(color=lib.UND_GREEN, size=9),
                               error_x=dict(type="data", array=top.p95 - top.central,
                                            arrayminus=(top.central - top.p05), color="#BBBBBB", thickness=1.5),
                               customdata=np.c_[top.p05, top.p95],
                               hovertemplate="%{y}: %{x:.2f} (90%: %{customdata[0]:.2f} to %{customdata[1]:.2f})"
                                             "<extra></extra>"))
    lib.show(lib.layout(fig, 560, legend=False), "adv_mc_fig", title=f"{lab}: 90% intervals, {place_label(place)}")
    w = (d.p95 - d.p05) / d.central.where(d.central != 0)
    st.caption(f"Monte Carlo with 500 draws: each draw varies the local-buying setting (FLQ delta), household spending, "
               f"and every input coefficient by about ±20% at random. Bars show the 5th to 95th percentile. Median "
               f"width: {np.nanmedian(w) * 100:.0f}% of the central value. This is a fuller picture than the two-case "
               f"range on the other pages, which moves only the two main settings.")
    lib.data_table(d[["name", "central", "p05", "p50", "p95"]].rename(columns={
        "name": "Industry", "central": "Central", "p05": "5th percentile", "p50": "Median", "p95": "95th percentile"}
    ).round(3), "All industries (table)", key=f"adv_mc_t_{place}")


def page():
    lib.header("Advanced impact analysis", "Four further, peer-reviewed ways to read the impact model: which industries "
               "anchor the local economy, what would be lost without each one, net rather than gross impacts with the "
               "chains that carry them, and how certain the multipliers are.", "model",
               note="IPBA input-output model built from BEA, BLS and Census data (2023).")
    if not (ready() and tables_ready()):
        return
    lk = lib.table("io_linkages.csv", dtype={"code": str})
    un = lib.table("io_uncertainty.csv", dtype={"code": str})
    place = st.selectbox("Place", list(dict.fromkeys(lk.place)), format_func=place_label, key="adv_place")
    tabs = st.tabs(["Key sectors", "If an industry disappeared", "Net impact and job paths", "How certain"])
    with tabs[0]:
        key_sectors(lk, place)
    with tabs[1]:
        extraction(lk, place)
    with tabs[2]:
        net_and_paths(place)
    with tabs[3]:
        uncertainty(un, place)
    lib.method_panel([
        "Key sectors: backward linkage = Rasmussen's normalized column sums of the Leontief inverse (Rasmussen, 1956; "
        "Hirschman, 1958); forward linkage = normalized row sums of the Ghosh inverse, read as a supply or price model "
        "(Dietzenbacher, 1997). Indexes cover industries with output in the place.",
        "Hypothetical extraction (Miller & Lahr, 2001; Dietzenbacher & Lahr, 2013): total = output lost when the "
        "industry's final demand and its local purchases and sales are removed (Type II, households included); "
        "backward = its column removed (Leontief, Type I); forward = its row removed in the Ghosh model (Type I).",
        "Net impact: gross effects scaled by the share of sales that is new to the place (1 - displacement), with "
        "induced effects also scaled by the share of new workers living in the place. Input-output results are gross "
        "unless displacement and commuting are taken into account (Bess & Ambargis, 2011).",
        "Structural path analysis (Defourny & Thorbecke, 1984; Miller & Blair, 2022): the Type II inverse is expanded "
        "as a sum of chains (I + A + A^2 + ...); paths up to 5 steps carrying at least 0.01% of the new output are kept, "
        "and the largest are shown.",
        "Monte Carlo: 500 draws; delta uniform within ±0.1 of the calibrated value, household spending within ±10%, "
        "and each regional coefficient times an independent lognormal factor with sd 0.20 (columns capped so the model "
        "stays productive); regions are capped at the state's coefficients in every draw (ten Raa & Steel, 1994; Lenzen, "
        "Wood & Wiedmann, 2010).", *LIMITS], REFS)
    lib.source_line("bea_io", "qcew", "bea", "stateio")


if __name__ == "__main__":
    page()
