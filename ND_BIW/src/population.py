"""Step: resident population by year for ND, peer states and the US (Census Population Estimates Program, no key).

Per-resident rates over time need the population of each year, not one fixed figure: ND grew about 15% between 2010
and 2025, so a fixed denominator would understate rates in the early 2010s and bias trends.
 - 2000-2009: intercensal estimates (st-est00int-alldata.csv, totals rows).
 - 2010-2019: vintage 2020 estimates (nst-est2020-alldata.csv).
 - 2020-2025: vintage 2025 estimates (NST-EST2025-ALLDATA.csv).
Years after the latest estimate use the latest estimate. Files are fixed releases, kept in data/raw/popest.
Writes outputs/population_annual.csv (geo, year, population).
"""
import pandas as pd
from config import OUT, PEERS, RAW
from fetch import get, is_csv

BASE = "https://www2.census.gov/programs-surveys/popest/datasets/"
FILES = {"2000": ("2000-2010/intercensal/state/", "st-est00int-alldata.csv"),
         "2010": ("2010-2020/state/totals/", "nst-est2020-alldata.csv"),
         "2020": ("2020-2025/state/totals/", "NST-EST2025-ALLDATA.csv")}
NAMES = {"United States": "US", "North Dakota": "ND", "Minnesota": "MN", "Montana": "MT", "South Dakota": "SD",
         "Wyoming": "WY"}


def read(key):
    path, name = FILES[key]
    d = pd.read_csv(get(BASE + path + name, RAW / "popest" / name, check=is_csv, timeout=300), dtype=str, encoding="latin1")
    if key == "2000":                       # detailed file: keep the all-sexes, all-origins, all-races, all-ages rows
        d = d[(d.SEX == "0") & (d.ORIGIN == "0") & (d.RACE == "0") & (d.AGEGRP == "0")]
    d = d[d.NAME.isin(NAMES)]
    first, last = {"2000": (2000, 2009), "2010": (2010, 2019), "2020": (2020, 2100)}[key]
    rows = []
    for c in d.columns:
        if c.startswith("POPESTIMATE") and c[11:].isdigit() and first <= int(c[11:]) <= last:
            rows += [{"geo": NAMES[n], "year": int(c[11:]), "population": float(v)} for n, v in zip(d.NAME, d[c])]
    return pd.DataFrame(rows)


def build():
    t = pd.concat([read(k) for k in FILES], ignore_index=True).sort_values(["geo", "year"])
    assert set(t.geo) == set(PEERS) | {"US"}
    return t


def population(t=None):
    """Lookup: (geo, year) -> population; years beyond the latest estimate use the latest."""
    t = pd.read_csv(OUT / "population_annual.csv") if t is None else t
    s = t.set_index(["geo", "year"]).population
    last = t.groupby("geo").year.max()

    def get_(geo, year):
        y = min(int(year), int(last.get(geo, year)))
        return s.get((geo, y), float("nan"))
    return get_


def main():
    t = build()
    t.to_csv(OUT / "population_annual.csv", index=False)
    nd = t[t.geo == "ND"].set_index("year").population
    print(f"    Population: {t.year.min()}-{t.year.max()}; ND {nd.loc[2010]:,.0f} (2010) -> {nd.iloc[-1]:,.0f} ({nd.index[-1]})")
    return {"popest": {"name": "Population estimates (intercensal 2000-2009, vintage 2020, vintage 2025)",
                       "publisher": "U.S. Census Bureau", "url": "https://www.census.gov/programs-surveys/popest.html",
                       "period": f"{t.year.min()} to {t.year.max()}", "latest": str(t.year.max())}}


if __name__ == "__main__":
    main()
