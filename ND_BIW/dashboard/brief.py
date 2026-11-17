"""Market brief: one county and one type of business, assembled from the dashboard's own county tables.

build(county, kind) returns a plain dict (people, market, retail, dynamics, findings, sources, caveats) that both the
Market brief page and the PDF render, so the two always match. Public, aggregated data only; the brief describes a
market, it does not recommend opening (or not opening) any business.
"""
import re
from datetime import date
import pandas as pd
import lib
from lib import OUT

# business type -> (NAICS sector used for establishments, jobs, survival and owners; Economic Census store type or None)
KINDS = {
    "Grocery and food stores": ("44-45", "445"),
    "Restaurants and bars": ("72", "722"),
    "General merchandise stores": ("44-45", "455"),
    "Building material and garden stores": ("44-45", "444"),
    "Motor vehicle and parts dealers": ("44-45", "441"),
    "Furniture, electronics and appliance stores": ("44-45", "449"),
    "Health and personal care stores": ("44-45", "456"),
    "Gas stations and fuel dealers": ("44-45", "457"),
    "Clothing and accessories stores": ("44-45", "458"),
    "Sporting goods, hobby, book and other stores": ("44-45", "459"),
    "Construction contractors": ("23", None),
    "Manufacturing": ("31-33", None),
    "Trucking, transportation and warehousing": ("48-49", None),
    "Professional, scientific and technical services": ("54", None),
    "Administrative, cleaning and support services": ("56", None),
    "Health care and social assistance": ("62", None),
    "Arts, entertainment and recreation": ("71", None),
    "Repair, personal care and other services": ("81", None),
    "Real estate, rental and leasing": ("53", None),
    "Agriculture, forestry and fishing services": ("11", None),
}
SECTOR_NAME = {"44-45": "retail trade", "72": "accommodation and food services", "23": "construction",
               "31-33": "manufacturing", "48-49": "transportation and warehousing",
               "54": "professional, scientific and technical services",
               "56": "administrative and support services", "62": "health care and social assistance",
               "71": "arts, entertainment and recreation", "81": "other services", "53": "real estate",
               "11": "agriculture, forestry and fishing"}


def _row(label, county, state, fmt, note=""):
    f = lambda v: "-" if v is None or pd.isna(v) else fmt.format(v)
    return {"measure": label, "county": f(county), "state": f(state), "note": note}


def _compare(c, s, more="more", less="fewer", tol=.15):
    if c is None or s is None or pd.isna(c) or pd.isna(s) or s == 0:
        return None
    r = c / s - 1
    return "about the same as" if abs(r) < tol else (f"{abs(r) * 100:.0f}% {more} than" if r > 0 else
                                                    f"{abs(r) * 100:.0f}% {less} than")


def people(county):
    a = lib.table("acs_places.csv")
    c = a[(a.level == "county") & (a.county == county)].iloc[0]
    s = a[a.level == "state"].iloc[0]
    rows = [_row("Residents", c.population, s.population, "{:,.0f}"),
            _row("Median household income", c.median_household_income, s.median_household_income, "${:,.0f}",
                 f"± ${c.median_household_income_moe:,.0f}" if pd.notna(c.median_household_income_moe) else ""),
            _row("Median age", c.median_age, s.median_age, "{:.1f}"),
            _row("Median home value", c.median_home_value, s.median_home_value, "${:,.0f}")]
    l = lib.table("laus_monthly.csv", parse_dates=["month"])
    lc = l[(l.level == "county") & (l.place == county)].sort_values("month").tail(12)
    ls = l[l.level == "state"].sort_values("month").tail(12)
    if len(lc) == 12:
        rows.append(_row(f"Unemployment rate, 12 months to {lc.month.max():%b %Y}", lc.rate.mean(), ls.rate.mean(),
                         "{:.1f}%"))
    return rows, c


def market(county, sector, pop, pop_state):
    b = lib.table("county_business.csv", dtype={"sector": str})
    d = b[b.sector == sector]
    c = d[d.county == county]
    c = c.iloc[0] if len(c) else None
    st = d[["employer_estabs", "employees", "payroll_k", "nonemployers"]].sum(min_count=1)
    per = lambda v, p: None if v is None or pd.isna(v) else v / p * 1000
    rows, vals = [], {}
    if c is not None:
        vals = {"estabs": c.employer_estabs, "nonemp": c.nonemployers,
                "estabs_pk": per(c.employer_estabs, pop), "estabs_pk_state": per(st.employer_estabs, pop_state),
                "nonemp_pk": per(c.nonemployers, pop), "nonemp_pk_state": per(st.nonemployers, pop_state)}
        pay = c.payroll_k * 1000 / c.employees if pd.notna(c.payroll_k) and c.employees else None
        pay_st = st.payroll_k * 1000 / st.employees if st.employees else None
        vals.update(pay=pay, pay_state=pay_st)
        rows += [_row(f"Employer establishments, all {SECTOR_NAME[sector]}", c.employer_estabs, st.employer_estabs, "{:,.0f}"),
                 _row("  per 1,000 residents", vals["estabs_pk"], vals["estabs_pk_state"], "{:.1f}"),
                 _row("Businesses without employees", c.nonemployers, st.nonemployers, "{:,.0f}"),
                 _row("  per 1,000 residents", vals["nonemp_pk"], vals["nonemp_pk_state"], "{:.1f}"),
                 _row("Employees of employer establishments", c.employees, st.employees, "{:,.0f}"),
                 _row(f"Annual payroll per employee, all {SECTOR_NAME[sector]}", pay, pay_st, "${:,.0f}")]
    z = lib.table("cbp_sizes.csv", dtype={"sector": str})
    z = z[(z.county == county) & (z.sector == sector)]
    if z.estabs.sum() > 0:
        small = z[z.order <= 1].estabs.sum() / z.estabs.sum() * 100
        vals["small_share"] = small
        rows.append(_row(f"Establishments with fewer than 10 employees, all {SECTOR_NAME[sector]}", small, None, "{:.0f}%"))
    return rows, vals


def retail(county, naics):
    r = lib.table("retail_gap.csv")
    r = r[(r.level == "county") & (r.place == county) & (r.naics == naics)]
    if not len(r):
        return None, {}
    x = r.iloc[0]
    gap = x.expected_k - x.sales_k
    vals = {"pf": x.pull_factor, "gap_m": gap / 1000, "estimated": bool(x.estimated), "store_type": x.store_type,
            "sales_m": x.sales_k / 1000, "expected_m": x.expected_k / 1000, "estab": x.estab}
    if pd.isna(x.sales_k):
        none = pd.isna(x.estab) or x.estab == 0
        vals["status"] = "none" if none else "withheld"
        return [_row(f"Stores of this type ({x.store_type.lower()}), 2022", 0 if none else x.estab, None, "{:,.0f}",
                     "none listed" if none else "sales withheld by Census"),
                _row("Sales county income would predict", x.expected_k / 1000, None, "${:,.1f} million")], vals
    rows = [_row(f"Sales of {x.store_type.lower()}, 2022", x.sales_k / 1000, None, "${:,.1f} million"),
            _row("Sales county income would predict", x.expected_k / 1000, None, "${:,.1f} million"),
            _row("Pull factor (1 = sales match local income)", x.pull_factor, 1.0, "{:.2f}",
                 "estimated: Census withheld this county" if x.estimated else "")]
    return rows, vals


def dynamics(county, sector):
    rows, vals = [], {}
    b = lib.table("bds_counties.csv")
    bc = b[b.county == county].sort_values("year")
    bs = lib.table("bds_states.csv")
    bs = bs[bs.geo == "ND"].set_index("year")
    if len(bc):
        y = int(bc.year.max())
        last3 = bc[bc.year > y - 3]
        rows += [_row(f"Business opening rate, all industries, {y - 2}-{y} average", last3.estabs_entry_rate.mean(),
                      bs.loc[y - 2:y, "estabs_entry_rate"].mean(), "{:.1f}%"),
                 _row(f"Business closing rate, all industries, {y - 2}-{y} average", last3.estabs_exit_rate.mean(),
                      bs.loc[y - 2:y, "estabs_exit_rate"].mean(), "{:.1f}%")]
    t = lib.table("taxable_sales_county.csv", parse_dates=["quarter"])
    tc = t[t.county == county].sort_values("quarter")
    if len(tc) >= 8:
        now, before = tc.value.tail(4).sum(), tc.value.iloc[-8:-4].sum()
        q = tc.quarter.max()
        vals["tax_change"] = (now / before - 1) * 100
        rows.append(_row("Taxable sales and purchases, change over a year", vals["tax_change"], None, "{:+.1f}%",
                         f"to {q.year} Q{q.quarter}, current $"))
    s = lib.table("survival_sector.csv", dtype={"sector": str})
    s = s[(s.geo == "ND") & (s.sector == sector)].set_index("horizon").survival
    for k in (1, 5):
        if k in s.index and pd.notna(s[k]):
            vals[f"surv{k}"] = s[k]
            rows.append(_row(f"New firms in {SECTOR_NAME[sector]} still open after {k} year{'s' if k > 1 else ''} (ND)",
                             None, s[k], "{:.0f}%", "statewide"))
    o = lib.table("owners_55plus.csv", dtype={"sector": str})
    o = o[(o.geo == "ND") & (o.sector == sector)]
    if len(o):
        o = o[o.year == o.year.max()].iloc[0]
        if o.owners_55plus > 0:
            vals["owners55"], vals["owners55_moe"] = o.share_55plus, o.share_55plus_moe90
            rows.append(_row(f"Owners aged 55 or older, {SECTOR_NAME[sector]} (ND, {int(o.year)})", None, o.share_55plus,
                             "{:.0f}%", f"± {o.share_55plus_moe90:.0f} points"))
    return rows, vals


def peers(county):
    p = lib.table("county_peers.csv")
    p = p[p.county == county].sort_values("rank")
    return p.peer.tolist()


def build(county, kind):
    sector, naics = KINDS[kind]
    prow, c = people(county)
    a = lib.table("acs_places.csv")
    pop_state = a[a.level == "state"].population.iloc[0]
    mrow, mv = market(county, sector, c.population, pop_state)
    rrow, rv = retail(county, naics) if naics else (None, {})
    drow, dv = dynamics(county, sector)
    f = []
    cmp = _compare(mv.get("estabs_pk"), mv.get("estabs_pk_state"))
    if cmp:
        f.append(f"{county} County has {mv['estabs']:,.0f} employer establishments in {SECTOR_NAME[sector]} and "
                 f"{mv['nonemp']:,.0f} businesses without employees: per resident, {cmp} the state for employer "
                 "establishments.")
    if rv.get("status") == "none":
        f.append(f"The 2022 Economic Census lists no {rv['store_type'].lower()} in the county: residents buy these "
                 f"goods elsewhere or online. County income would predict about ${rv['expected_m']:,.1f} million a "
                 "year of such sales (a rough guide to local spending, not to what one store could capture).")
    elif rv.get("status") == "withheld":
        f.append(f"The county has {rv['estab']:,.0f} {rv['store_type'].lower()}, but the Census Bureau withheld their "
                 "2022 sales to protect individual stores, so local sales cannot be compared with local income.")
    elif rv:
        gap = rv["gap_m"]
        if rv["pf"] < 0.9:
            f.append(f"Local sales of {rv['store_type'].lower()} were about ${abs(gap):,.1f} million below what county "
                     f"income would predict in 2022 (pull factor {rv['pf']:.2f}): residents likely buy part of this "
                     "elsewhere, online or in a nearby hub.")
        elif rv["pf"] > 1.1:
            f.append(f"Local sales of {rv['store_type'].lower()} were about ${abs(gap):,.1f} million above what county "
                     f"income would predict in 2022 (pull factor {rv['pf']:.2f}): the county draws shoppers from "
                     "outside.")
        else:
            f.append(f"Local sales of {rv['store_type'].lower()} were close to what county income would predict in "
                     f"2022 (pull factor {rv['pf']:.2f}).")
    pc = _compare(mv.get("pay"), mv.get("pay_state"), "higher", "lower", .1)
    if pc:
        f.append(f"Annual payroll per employee in {SECTOR_NAME[sector]} in the county is {pc} the state average ({lib.money(mv['pay'])} "
                 f"against {lib.money(mv['pay_state'])}).")
    if "surv5" in dv:
        f.append(f"Across North Dakota, about {dv['surv5']:.0f}% of new firms in {SECTOR_NAME[sector]} are still "
                 f"open five years after starting" + (f" ({dv['surv1']:.0f}% after one year)." if "surv1" in dv else "."))
    if "owners55" in dv:
        f.append(f"About {dv['owners55']:.0f}% of North Dakota business owners in {SECTOR_NAME[sector]} are 55 or older (± "
                 f"{dv['owners55_moe']:.0f} points): some existing businesses may change hands in coming years.")
    if "tax_change" in dv:
        f.append(f"County taxable sales and purchases changed {dv['tax_change']:+.1f}% over the latest year (all "
                 "industries, current dollars).")
    sources = ["Census Bureau: American Community Survey 5-year (people, income), County Business Patterns and "
               "Nonemployer Statistics (businesses), Business Dynamics Statistics (openings, closings, survival), "
               "Annual Business Survey (owners)" + (", Economic Census 2022 (retail sales)" if naics else ""),
               "BLS: Local Area Unemployment Statistics", "ND Office of State Tax Commissioner: taxable sales",
               "IPBA calculations (per-resident figures, pull factor, survival, peer counties)"]
    caveats = ["Figures describe the whole county market, not any single business or site. Small counties have "
               "wide margins of error, and agencies withhold or add noise to small cells.",
               "Retail sales and pull factors are for 2022 (Economic Census); spending may have shifted since.",
               "Survival and owner age are statewide for the sector: county figures are too small to publish.",
               "This brief describes conditions; it is not advice to open, buy or close a business."]
    return {"county": county, "kind": kind, "sector": sector, "naics": naics, "region": c.region,
            "people": prow, "market": mrow, "retail": rrow, "dynamics": drow, "peers": peers(county),
            "findings": f, "sources": sources, "caveats": caveats, "made": date.today().strftime("%B %d, %Y")}


LATIN = str.maketrans({"–": "-", "—": "-", "’": "'", "‘": "'", "“": '"', "”": '"', "±": "+/-", "≥": ">=",
                       "≤": "<=", "·": "-", "…": "..."})


def _t(s):
    """Text for the PDF's built-in fonts (Latin-1)."""
    return str(s).translate(LATIN).encode("latin-1", "replace").decode("latin-1")


def pdf(b):
    """The brief as PDF bytes (fpdf2, built-in Helvetica so it works without system fonts)."""
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos
    green, gray = (0, 154, 68), (90, 90, 90)
    doc = FPDF(format="Letter")
    doc.set_auto_page_break(True, margin=16)
    doc.set_margins(16, 14, 16)
    doc.set_title(_t(f"Market brief: {b['kind']}, {b['county']} County"))
    doc.set_author("Institute of Policy and Business Analytics, University of North Dakota")
    doc.add_page()
    w = doc.w - doc.l_margin - doc.r_margin

    def heading(text, size=12):
        doc.ln(2)
        doc.set_font("Helvetica", "B", size)
        doc.set_text_color(*green)
        doc.cell(w, 7, _t(text), align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        doc.set_text_color(0, 0, 0)

    def table(rows, county_label):
        widths = (w * .52, w * .16, w * .14, w * .18)
        doc.set_font("Helvetica", "B", 8.5)
        doc.set_fill_color(230, 243, 235)
        for txt, cw in zip(("Measure", county_label, "North Dakota", "Note"), widths):
            doc.cell(cw, 6, _t(txt), border="B", fill=True)
        doc.ln()
        doc.set_font("Helvetica", "", 8.5)
        for r in rows:
            for key, cw in zip(("measure", "county", "state", "note"), widths):
                doc.cell(cw, 5.4, _t(r[key])[:70])
            doc.ln()

    doc.set_font("Helvetica", "B", 8)
    doc.set_text_color(*gray)
    doc.cell(w, 5, _t("ND BUSINESS AND INNOVATION WATCH - MARKET BRIEF"), align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    doc.set_font("Helvetica", "B", 18)
    doc.set_text_color(*green)
    doc.multi_cell(w, 8, _t(f"{b['kind']}: {b['county']} County, North Dakota"), align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    doc.set_font("Helvetica", "", 9)
    doc.set_text_color(*gray)
    doc.cell(w, 5, _t(f"{b['region']} - prepared {b['made']} from public data"), align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    doc.set_text_color(0, 0, 0)
    heading("What the data show")
    doc.set_font("Helvetica", "", 9.5)
    for x in b["findings"]:
        doc.multi_cell(w, 5, _t("- " + x), align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    label = f"{b['county']} County"
    heading("People and income")
    table(b["people"], label)
    heading("Businesses in this field")
    table(b["market"], label)
    if b["retail"]:
        heading("Retail sales against local income (2022)")
        table(b["retail"], label)
    heading("Openings, closings, survival and owners")
    table(b["dynamics"], label)
    if b["peers"]:
        heading("Similar counties elsewhere in the US", 11)
        doc.set_font("Helvetica", "", 9)
        doc.multi_cell(w, 5, _t(", ".join(b["peers"]) + " (matched on size, density, age and industry mix; useful for "
                                "comparing results)."), align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    heading("Read with care", 11)
    doc.set_font("Helvetica", "", 8.5)
    for x in b["caveats"]:
        doc.multi_cell(w, 4.5, _t("- " + x), align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    heading("Sources", 11)
    doc.set_font("Helvetica", "", 8.5)
    for x in b["sources"]:
        doc.multi_cell(w, 4.5, _t("- " + x), align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    doc.ln(2)
    doc.set_font("Helvetica", "I", 8)
    doc.set_text_color(*gray)
    contact = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", lib.contact_line())      # markdown links -> text (url)
    doc.multi_cell(w, 4.2, _t(lib.DISCLAIMER + " " + contact), align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    return bytes(doc.output())


def ready():
    need = ["acs_places.csv", "laus_monthly.csv", "county_business.csv", "cbp_sizes.csv", "retail_gap.csv",
            "bds_counties.csv", "bds_states.csv", "taxable_sales_county.csv", "survival_sector.csv",
            "owners_55plus.csv", "county_peers.csv"]
    return [f for f in need if not (OUT / f).exists()]
