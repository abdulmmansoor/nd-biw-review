"""Business survey: what North Dakota businesses report each quarter (IPBA North Dakota Business Survey). Weighting,
margins and suppression are in src/survey.py; this page only displays the combined results. Until the survey is
fielded the tables hold made-up test data, and the page says so at the top and on every chart."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import lib
from lib import OUT

GROUPS = {"All of North Dakota": "state", "By size": "size", "By industry": "industry", "East and West": "area"}
TOPIC_Q = {1: "Workforce and hiring plans", 2: "Ownership and succession", 3: "Trade, tariffs and supply chains",
           4: "Energy, investment and the year ahead"}
HEADLINE = [("A1_a", "Sales"), ("A1_b", "Employees"), ("A1_c", "Prices charged"), ("A1_d", "Prices paid for inputs")]
REGION_MEASURES = {
    "Sales, last 3 months (net balance)": ("Last 3 months", "A1_a"),
    "Employees, last 3 months (net balance)": ("Last 3 months", "A1_b"),
    "Outlook for the business (index)": ("Outlook", "A3"),
    "Finding qualified workers a significant problem (%)": ("Constraints", "B1_a"),
    "Housing for workers a significant problem (%)": ("Constraints", "B1_l"),
    "Uses AI to produce goods or services (%)": ("Technology: use now", "C2_a"),
    "Internet service not fully adequate (%)": ("Internet", "C5"),
}
WITHHELD = "withheld (fewer than 30 answers)"


def ready():
    if not all((OUT / f).exists() for f in ("survey_results.csv", "survey_fielding.csv")):
        st.info("The survey tables have not been built yet. Run `py -3.15 src/run_all.py`.")
        return False
    return True


def qlabel(q):
    return lib.quarter_label(q)


def test_build():
    """True when the survey tables hold made-up test data (or are missing), for the menu label."""
    f = OUT / "survey_results.csv"
    if not f.exists():
        return True
    return is_test(pd.read_csv(f, usecols=["test_data"], nrows=5))


def is_test(r):
    return r.test_data.astype(str).isin(["True", "true", "1"]).any()


def mark(fig, test):
    """Stamp a chart built from test data, so a screenshot cannot pass for real results."""
    if test:
        fig.add_annotation(text="TEST DATA – NOT REAL", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
                           font=dict(size=34, color="rgba(242,138,69,0.35)"), textangle=-12)
    return fig


def sel(r, q, dt, dom, section=None):
    """Results for one quarter and group (the jobs-weighted check rows, stat *_emp, are left out)."""
    d = r[(r.quarter == q) & (r.domain_type == dt) & (r.domain == dom) & ~r.stat.str.endswith("_emp")]
    return d if section is None else d[d.section == section]


def pick_group(r, key):
    c = st.columns([1, 2])
    t = c[0].selectbox("Businesses", list(GROUPS), key=f"{key}_t")
    dt = GROUPS[t]
    if dt == "state":
        return "state", "North Dakota"
    opts = list(dict.fromkeys(r[r.domain_type == dt].domain))
    return dt, c[1].selectbox("Group", opts, key=f"{key}_g")


def fmt(v, moe, stat="share"):
    if pd.isna(v):
        return WITHHELD
    s = f"{v:+.0f}" if stat in ("net", "index") else f"{v:.0f}%"
    return s + (f" ± {moe:.0f}" if pd.notna(moe) else "")


def bars(d, value_name, key, title, test, h=None, color=lib.ACCENT, extra=None):
    """Horizontal bars with 90% margins as error bars; withheld rows listed under the chart."""
    d = d.sort_values("value", na_position="first")
    fig = go.Figure(go.Bar(y=d.label, x=d.value, orientation="h", name=value_name,
                           marker=dict(color=color, line=dict(width=0)),
                           error_x=dict(type="data", array=d.moe, color=lib.INK, thickness=1.2, width=3),
                           hovertemplate="%{y}: %{x:.0f} ± %{error_x.array:.0f}<extra></extra>"))
    if extra is not None:
        ename, e = extra
        e = e.set_index("label").reindex(d.label)
        fig.add_trace(go.Bar(y=e.index, x=e.value, orientation="h", name=ename,
                             marker=dict(color=lib.UND_GRAY, line=dict(width=0)), opacity=0.6,
                             hovertemplate="%{y}: %{x:.0f}<extra></extra>"))
        fig.update_layout(barmode="overlay")
    lib.layout(fig, h or max(260, 34 * len(d) + 80), legend=extra is not None)
    fig.update_xaxes(title=value_name)
    lib.show(mark(fig, test), key, title=title)
    gone = d[d.value.isna()].label.tolist()
    if gone:
        st.caption("Withheld (fewer than 30 answers, or one business would carry most of the weight): " + ", ".join(gone))


def table_of(d, key, label="Chart data (accessible table)"):
    t = d[["label", "value", "moe", "n"]].rename(columns={"label": "Measure", "value": "Estimate", "moe": "± (90%)",
                                                          "n": "Businesses answering"})
    lib.data_table(t, label, key=key)


# ------------------------------------------------------------------ sections
def conditions(r, q, test):
    st.subheader("Business conditions")
    st.caption("Net balance = percent of businesses reporting an increase minus percent reporting a decrease, from "
               "-100 to +100. Above zero, more businesses report increases than decreases. ± is the 90% margin of error.")
    year_ago = q - pd.DateOffset(years=1)
    cols = st.columns(len(HEADLINE))
    for c, (code, name) in zip(cols, HEADLINE):
        now = sel(r, q, "state", "North Dakota", "Last 3 months")
        now = now[now.measure == code]
        prev = sel(r, year_ago, "state", "North Dakota", "Last 3 months")
        prev = prev[prev.measure == code]
        v, m = (now.value.iloc[0], now.moe.iloc[0]) if len(now) else (float("nan"), float("nan"))
        delta = (f"{v - prev.value.iloc[0]:+.0f} points vs {qlabel(year_ago)}"
                 if len(prev) and pd.notna(v) and pd.notna(prev.value.iloc[0]) else None)
        c.metric(f"{name}, last 3 months", "–" if pd.isna(v) else f"{v:+.0f} ± {m:.0f}", delta, delta_color="off",
                 help="Net balance, all of North Dakota. The change from a year earlier is compared with the same "
                      "quarter, because the survey is not yet seasonally adjusted.")
    dt, dom = pick_group(r, "sv_cond")
    last, nxt = sel(r, q, dt, dom, "Last 3 months"), sel(r, q, dt, dom, "Next 3 months")
    if last.empty:
        st.info("No results for this group in this quarter.")
    else:
        d = last.merge(nxt[["measure", "label", "value", "moe"]].assign(measure=lambda x: x.measure.str.replace("A2", "A1")),
                       on=["measure", "label"], suffixes=("", "_next"))
        fig = go.Figure()
        for col, name, color in (("", "Last 3 months", lib.ACCENT), ("_next", "Expected, next 3 months", lib.SECOND)):
            fig.add_trace(go.Bar(y=d.label, x=d["value" + col], orientation="h", name=name,
                                 marker=dict(color=color, line=dict(width=0)),
                                 error_x=dict(type="data", array=d["moe" + col], color=lib.INK, thickness=1.2, width=3),
                                 hovertemplate=name + ", %{y}: %{x:+.0f}<extra></extra>"))
        lib.layout(fig, 380).update_layout(barmode="group", yaxis=dict(autorange="reversed"))
        fig.update_xaxes(title="Net balance", range=[-100, 100], zeroline=True, zerolinecolor=lib.MUTED)
        lib.show(mark(fig, test), "sv_cond_bar", title=f"Change at the business, {dom}, {qlabel(q)}")
        t = d[["label", "value", "moe", "value_next", "moe_next", "n"]].rename(columns={
            "label": "Item", "value": "Last 3 months", "moe": "± (90%)", "value_next": "Next 3 months (expected)",
            "moe_next": "± (90%) next", "n": "Businesses answering"})
        lib.data_table(t, key="sv_cond_tab")
    trend(r, test)


def band(fig, d, name, color, dash="solid"):
    d = d.dropna(subset=["value"]).sort_values("quarter")
    if d.empty:
        return
    x = [qlabel(v) for v in d.quarter]
    fig.add_scatter(x=x + x[::-1], y=list(d.value + d.moe) + list((d.value - d.moe)[::-1]), fill="toself",
                    fillcolor=color + "2E",
                    line=dict(width=0), hoverinfo="skip", showlegend=False)
    fig.add_scatter(x=x, y=d.value, name=name, mode="lines+markers", line=dict(color=color, dash=dash, width=2.4),
                    hovertemplate=name + ", %{x}: %{y:+.0f}<extra></extra>")


def trend(r, test):
    s = r[(r.domain_type == "state") & (r.domain == "North Dakota")]
    items = list(dict.fromkeys(s[s.section == "Last 3 months"].label))
    c = st.columns([2, 3])
    item = c[0].selectbox("Trend for", items + ["Outlook for the next 12 months"], key="sv_trend")
    fig = go.Figure()
    if item.startswith("Outlook"):
        o = s[s.section == "Outlook"]
        band(fig, o[o.measure == "A3"], "Outlook for the business", lib.ACCENT)
        band(fig, o[o.measure == "A4"], "Outlook for the ND economy", lib.SECOND, "dash")
        rows, ytitle = o, "Index (-100 to +100)"
    else:
        a = s[(s.label == item) & (s.section.isin(["Last 3 months", "Next 3 months"]))]
        band(fig, a[(a.section == "Last 3 months") & (a.stat == "net")], "Last 3 months", lib.ACCENT)
        band(fig, a[(a.section == "Next 3 months") & (a.stat == "net")], "Expected, next 3 months", lib.SECOND, "dash")
        e = a[(a.section == "Last 3 months") & (a.stat == "net_emp")].sort_values("quarter")
        fig.add_scatter(x=[qlabel(v) for v in e.quarter], y=e.value, name="Last 3 months, weighted by jobs",
                        mode="lines", line=dict(color=lib.UND_GRAY, dash="dot", width=1.6),
                        hovertemplate="Weighted by jobs, %{x}: %{y:+.0f}<extra></extra>")
        rows, ytitle = a, "Net balance"
    lib.layout(fig, 360, ytitle=ytitle)
    fig.update_yaxes(zeroline=True, zerolinecolor=lib.MUTED)
    lib.show(mark(fig, test), "sv_trend_fig", title=f"{item}, North Dakota")
    t = rows.assign(Quarter=[qlabel(v) for v in rows.quarter])[["Quarter", "section", "label", "stat", "value", "moe", "n"]]
    lib.data_table(t.rename(columns={"section": "Question", "label": "Item", "stat": "Measure", "value": "Estimate",
                                     "moe": "± (90%)", "n": "Businesses answering"}), key="sv_trend_tab")
    st.caption("Shaded bands are 90% margins of error. The dotted line weights each answer by the business's jobs, a "
               "check on whether larger employers see things differently. Not seasonally adjusted: compare a quarter "
               "with the same quarter a year earlier.")


def constraints(r, q, test):
    st.subheader("What is holding businesses back")
    dt, dom = pick_group(r, "sv_con")
    sig, anyp = sel(r, q, dt, dom, "Constraints"), sel(r, q, dt, dom, "Constraints (any)")
    if sig.empty:
        st.info("No results for this group in this quarter.")
        return
    bars(sig, "% of businesses: significantly", "sv_con_fig", f"Problems that limited the business, {dom}, {qlabel(q)}",
         test, extra=("Somewhat or significantly", anyp[["label", "value"]]))
    table_of(sig, "sv_con_tab")
    c = st.columns(2)
    with c[0]:
        st.markdown("**The single biggest problem** (% of businesses)")
        b = sel(r, q, dt, dom, "Biggest problem").sort_values("value", ascending=False).head(6)
        st.dataframe(pd.DataFrame({"Problem": b.label, "Share": [fmt(v, m) for v, m in zip(b.value, b.moe)]}),
                     hide_index=True, width="stretch")
    with c[1]:
        st.markdown("**Financing and hiring** (% of businesses)")
        fi = pd.concat([sel(r, q, dt, dom, "Financing"), sel(r, q, dt, dom, "Hiring")])
        st.dataframe(pd.DataFrame({"Measure": fi.label, "Share": [fmt(v, m) for v, m in zip(fi.value, fi.moe)]}),
                     hide_index=True, width="stretch")
        st.caption("Approved and turned down are shares of businesses that applied.")
    jobs = sel(r, q, dt, dom, "Hardest jobs to fill")
    if not jobs.empty:
        bars(jobs, "% of businesses hiring or short of workers", "sv_jobs_fig", f"Hardest jobs to fill, {dom}", test,
             color=lib.SECOND)
        table_of(jobs, "sv_jobs_tab")


def innovation(r, q, test):
    st.subheader("Innovation and technology")
    dt, dom = pick_group(r, "sv_inn")
    inn = sel(r, q, dt, dom, "Innovation")
    if inn.empty:
        st.info("No results for this group in this quarter.")
        return
    c = st.columns(2)
    with c[0]:
        bars(inn, "% of businesses, last 12 months", "sv_inn_fig", f"New products, processes and R&D, {dom}", test, h=330)
    with c[1]:
        use, plan = sel(r, q, dt, dom, "Technology: use now"), sel(r, q, dt, dom, "Technology: plan in 6 months")
        extra = use[["label"]].merge(plan[["label", "value"]], how="left")
        extra["value"] = extra.value.fillna(0) + use.value.values
        bars(use, "% of businesses using now", "sv_tech_fig", f"Technology use, {dom}", test, h=330,
             extra=("Use now or plan to start in 6 months", extra))
    table_of(pd.concat([inn, use.assign(label=use.label + " (use now)"), plan.assign(label=plan.label + " (plan)")]),
             "sv_inn_tab")
    net = sel(r, q, dt, dom, "Internet")
    if len(net):
        st.markdown(f"**Internet service not fully adequate for the business:** {fmt(net.value.iloc[0], net.moe.iloc[0])} "
                    f"of businesses ({dom}).")
    st.caption("Innovation follows the OECD/Eurostat Oslo Manual; AI use follows the Census Business Trends and Outlook "
               "Survey. These complement the state comparisons on [Innovation](innovation).")


def topic(r, q, test):
    name = TOPIC_Q[q.quarter]
    st.subheader(f"Special topic: {name.lower()}")
    d = r[(r.quarter == q) & r.section.str.startswith("Topic")]
    if d.empty:
        st.info(f"No special-topic results for {qlabel(q)}. Each quarter asks about one topic: workforce (Q1), ownership "
                "and succession (Q2), trade and supply chains (Q3), energy and investment (Q4).")
        return
    dt, dom = pick_group(r[r.section.str.startswith("Topic")], "sv_top")
    d = d[(d.domain_type == dt) & (d.domain == dom)]
    bars(d, "% of businesses", "sv_top_fig", f"{name}, {dom}, {qlabel(q)}", test, color=lib.SECOND)
    table_of(d, "sv_top_tab")


def regions(r, q, test):
    st.subheader("Planning regions (last 4 quarters together)")
    d = r[(r.quarter == q) & (r.domain_type == "region_4q")]
    if d.empty:
        st.info("Regional results start once 4 quarters of the survey are available; one quarter has too few answers "
                "per region.")
        return
    m = st.selectbox("Measure", list(REGION_MEASURES), key="sv_reg_m")
    sec, code = REGION_MEASURES[m]
    x = d[(d.section == sec) & (d.measure == code)].assign(label=lambda t: t.domain)
    bars(x, m, "sv_reg_fig", f"{m} by planning region, 4 quarters to {qlabel(q)}", test, h=360)
    table_of(x, "sv_reg_tab")
    st.caption("Each region pools its answers from the last 4 quarters, so a region's margin of error stays near ±10 "
               "points for a net balance. A business that answered in several quarters is counted once in the margin.")


def fielding(f, test):
    st.subheader("Who answered")
    t = f.sort_values("quarter", ascending=False)
    st.dataframe(pd.DataFrame({
        "Quarter": [qlabel(v) for v in t.quarter], "Invited": t.invited, "Responses": t.responses,
        "Answered before (panel)": t.panel_responses, "New": t.new_responses,
        "Response rate": [f"{v:.0f}%" for v in t.response_rate]}), hide_index=True, width="stretch")
    st.caption("Response rate = responses / (invitations - businesses found closed or out of scope), in the spirit of "
               "AAPOR's RR3. Each business is asked for up to 4 quarters in a row, then replaced."
               + (" These counts are made up, like the rest of the page." if test else ""))


def page():
    lib.header("Business survey", "What North Dakota businesses report each quarter about their sales, jobs, prices, "
               "problems and use of technology, from IPBA's survey of business locations with employees.", "estimate",
               note="IPBA survey, weighted to Census County Business Patterns counts; 90% margins of error.")
    if not ready():
        return
    r = lib.table("survey_results.csv", parse_dates=["quarter"])
    f = lib.table("survey_fielding.csv", parse_dates=["quarter"])
    test = is_test(r)
    if test:
        st.error("**Test data.** The IPBA North Dakota Business Survey has not been fielded yet. Every number on this "
                 "page is made up, to test the page and its calculations. Do not quote or use these numbers.",
                 icon=":material/science:")
    qs = sorted(r.quarter.unique())[::-1]
    q = pd.Timestamp(st.selectbox("Survey quarter", qs, format_func=qlabel, key="sv_q"))
    n = f[f.quarter == q]
    if len(n):
        st.markdown(f"**{int(n.responses.iloc[0]):,} businesses answered in {qlabel(q)}** "
                    f"({n.response_rate.iloc[0]:.0f}% response rate).")
    conditions(r, q, test)
    st.divider()
    constraints(r, q, test)
    st.divider()
    innovation(r, q, test)
    st.divider()
    topic(r, q, test)
    st.divider()
    regions(r, q, test)
    st.divider()
    fielding(f, test)
    lib.method_panel([
        "Who: North Dakota business locations with at least one employee, in all private industries. Owners without "
        "employees are not in these results.",
        "Sample: stratified random sample by the 8 planning regions and 4 size classes (1-4, 5-19, 20-99, 100+ "
        "employees); every location with 100 or more employees is invited. Each business answers for up to 4 quarters.",
        "Weights: each answer stands for a number of similar locations, so results add up to the Census County Business "
        "Patterns count of locations by region, size and industry group (raking); very large weights are trimmed.",
        "Measures: net balance = % increase - % decrease; outlook index = much better +100, somewhat better +50, same 0, "
        "somewhat worse -50, much worse -100; shares are % of businesses that answered the question.",
        "Margins of error (90%): stratified delete-one jackknife. Results from fewer than 30 businesses, or where one "
        "business would carry more than half the weight, are withheld.",
        "Not seasonally adjusted until about 5 years of data exist; compare with the same quarter a year earlier.",
        "The survey reports what businesses say; it is not an official statistic. Answers are confidential and only "
        "combined results are published."],
        refs=("valliant2018", "oecd2018"))
    lib.source_line("survey", "cbp")


if __name__ == "__main__":
    page()
