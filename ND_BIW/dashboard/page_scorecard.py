"""Peer scorecard: North Dakota against Minnesota, Montana, South Dakota, Wyoming and the US on ten measures."""
import pandas as pd
import streamlit as st
import lib
from lib import PEER_NAMES

STATES = ["ND", "MN", "MT", "SD", "WY"]


def fmt(v, f):
    return "–" if pd.isna(v) else f.format(v)


def page():
    lib.header("Peer scorecard", "North Dakota next to its neighbors and the nation on new businesses, jobs, pay, "
               "output and income.", "official", "estimate",
               note="Census Bureau, BLS and BEA. Rates, growth and ranks: IPBA calculations.")
    if not lib.ready():
        return
    t = lib.table("scorecard.csv")
    top = (t.nd_rank <= 2).sum()
    st.markdown(f"North Dakota ranks first or second among the five states on **{top} of {len(t)}** measures. "
                "Rank 1 is the highest value, except for unemployment, where rank 1 is the lowest.")
    rows = []
    for _, r in t.iterrows():
        sig_rank = int(r.get("nd_rank_significant", r.nd_rank))
        rank = (f"{int(r.nd_rank)} (statistically {sig_rank})" if bool(r.get("sampling_error", False))
                and sig_rank != int(r.nd_rank) else str(int(r.nd_rank)))
        row = {"Measure": r.measure, "ND rank (of 5)": rank}
        for g in STATES + ["US"]:
            v = fmt(r[g], r.format)
            if g in STATES[1:] and bool(r.get("sampling_error", False)) and not bool(r.get(f"{g}_significant", True)):
                v += " ≈"                                # not significantly different from ND
            row[g] = v
        row["Period"] = r.period
        row["Source"] = r.source
        rows.append(row)
    view = pd.DataFrame(rows)
    st.dataframe(view, hide_index=True, width="stretch", column_config={
        "Measure": st.column_config.TextColumn(width="large"),
        **{g: st.column_config.TextColumn(PEER_NAMES[g] if g != "US" else "US", width="small") for g in STATES + ["US"]}})
    st.download_button("Download (CSV)", t.drop(columns=["format"]).to_csv(index=False).encode(), "nd_peer_scorecard.csv",
                       "text/csv", icon=":material/download:", key="dl_scorecard")
    st.caption("≈ marks a state whose survey (ACS) value is not significantly different from North Dakota's at the 90% "
               "level, given sampling error; the rank in brackets counts only states significantly better than ND. "
               "Ranks compare the five states only; the US column is for reference. Wyoming's business application "
               "counts are inflated by companies based elsewhere that register there. Measures cover different "
               "periods because each source is released on its own schedule; ACS values are 5-year averages.")
    lib.method_panel([
        "Each measure is computed the same way for every state from the same source and period.",
        "Growth rates are compound yearly averages over five years. Ranks compare ND, MN, MT, SD and WY only."],
        ["porter2003"])
    lib.source_line("bfs", "bds", "qcew", "bea", "acs")


if __name__ == "__main__":
    page()
