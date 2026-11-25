"""BEA input-output tables for the impact model from the BEA Data API (summary level, before redefinitions).

BEA stopped updating its bulk file of input-output tables (AllTablesIO.zip, last changed September 2024, tables
through 2023); the annual update, each late September, is now published through BEA's interactive tables and the
BEA Data API (dataset InputOutput; BEA, Web Service API User Guide, Appendix K). The API needs a free key (UserID,
36 characters: https://apps.bea.gov/API/signup/), read from BEA_API_KEY or the git-ignored .streamlit/secrets.toml
([bea] user_id = "..."); save it with Set_BEA_Key.bat. The key is never written to logs or caches.

 - Table numbers are not fixed in code: they are looked up by title (GetParameterValues), so a renumbering by BEA
   does not break the step.
 - The newest year with both tables is used. Responses are cached in data/live/bea_io/ and refreshed monthly, or on
   every automatic update.
 - The API gives BEA's supply-use tables: Use of commodities by industries at purchasers' prices, and Supply of
   commodities by industries (output, imports, trade and transport margins, product taxes). convert() turns them
   into the make-use shape the model was built on (uses near producers' prices, industry output and value added at
   basic prices, imports as column F050). On the 2023 tables, which exist in both forms, national Type I output
   multipliers differ by a median of about 3.5% from the bulk file's, mostly from BEA's later revisions of 2023.
 - Every row and column the model reads is checked before the tables are used.
Limits (BEA): 100 requests and 100 MB per minute; this step makes about 5 requests.
"""
import json
import os
import time
import tomllib
from pathlib import Path
import pandas as pd
import requests
from config import LIVE, USER_AGENT

API = "https://apps.bea.gov/api/data/"
ROOT = Path(__file__).resolve().parents[1]
CACHE = LIVE / "bea_io"


def user_id():
    """First real key from: process environment, the git-ignored secrets file, the Windows user environment."""
    found = [os.environ.get("BEA_API_KEY", "")]
    f = ROOT / ".streamlit" / "secrets.toml"
    if f.exists():
        try:
            found.append(tomllib.loads(f.read_text(encoding="utf-8")).get("bea", {}).get("user_id", ""))
        except tomllib.TOMLDecodeError:
            pass
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as h:
            found.append(str(winreg.QueryValueEx(h, "BEA_API_KEY")[0]))
    except (ImportError, OSError):
        pass
    return next((k.strip() for k in found if k and len(k.strip()) == 36), "")


def flat(res):
    """GetData returns Results as a list of result blocks (one per table); join them into one {'Data': [...]}."""
    if isinstance(res, list):
        out = {k: v for b in res if isinstance(b, dict) for k, v in b.items() if k != "Data"}
        out["Data"] = [d for b in res if isinstance(b, dict) for d in (b.get("Data") or [])]
        return out
    return res


def call(params, timeout=180, tries=3, wait=20):
    """One API request; returns BEAAPI.Results. 'No data' (error 205) raises LookupError; other API errors raise
    RuntimeError. BEA sometimes answers 'UserId is not active' (error 4) for a working key while a new key reaches
    all its servers, so that error is retried."""
    key = user_id()
    if not key:
        raise RuntimeError("no BEA API key (run Set_BEA_Key.bat)")
    for attempt in range(tries):
        r = requests.get(API, params={"UserID": key, "ResultFormat": "JSON", **params},
                         headers={"User-Agent": USER_AGENT}, timeout=timeout)
        r.raise_for_status()
        js = r.json().get("BEAAPI", {})
        res = flat(js.get("Results", {}))
        err = js.get("Error") or (res.get("Error") if isinstance(res, dict) else None)
        if not err:
            return res
        err = err if isinstance(err, dict) else {"APIErrorDescription": str(err)}
        code = str(err.get("APIErrorCode", ""))
        detail = err.get("ErrorDetail", {})
        msg = (f"BEA API error {code}: {err.get('APIErrorDescription', '')} "
               f"{detail.get('Description', '') if isinstance(detail, dict) else ''}").strip()
        if code == "205":
            raise LookupError(msg)
        if code != "4" or attempt == tries - 1:
            raise RuntimeError(msg)
        time.sleep(wait)


def _cached(name, params, max_age_days=30):
    """JSON results cached in data/live/bea_io (no key in the file); fresh copy monthly or on automatic updates."""
    from fetch import _log, _sha, recheck
    f = CACHE / name
    if f.exists() and not recheck() and time.time() - f.stat().st_mtime < max_age_days * 86400:
        return json.loads(f.read_text(encoding="utf-8"))
    try:
        res = call(params)
    except Exception:
        if f.exists():
            return json.loads(f.read_text(encoding="utf-8"))
        raise
    body = json.dumps(res, sort_keys=True)
    url = API + "?" + "&".join(f"{k}={v}" for k, v in params.items())        # for the log: no key
    CACHE.mkdir(parents=True, exist_ok=True)
    if f.exists() and _sha(f.read_bytes()) == _sha(body.encode()):
        os.utime(f)
        _log(f, url, "unchanged", sha=_sha(body.encode()))
    else:
        f.write_text(body, encoding="utf-8")
        _log(f, url, "downloaded", sha=_sha(body.encode()), changed=True)
    return res


def _pv(res):
    rows = res.get("ParamValue", [])
    return rows if isinstance(rows, list) else [rows]


def table_ids():
    """{'use': id, 'make': id} for the summary Use and Make tables, found by title. The API's input-output tables
    are BEA's core (before redefinitions) tables; there the Make table is titled 'The Domestic Supply of Commodities
    by Industries' (in November 2026: Use 259, Make 262). Checked against the bulk file's 2023 tables."""
    vals = _pv(_cached("api_tableids.json", {"method": "GetParameterValues", "DataSetName": "InputOutput",
                                              "ParameterName": "TableID"}))
    def pick(phrase):
        for v in vals:
            d = str(v.get("Desc", "")).lower()
            if (phrase in d and d.rstrip().endswith("summary") and "after redefinitions" not in d
                    and "purchaser" not in d and "requirement" not in d):
                return str(v["Key"])
        raise RuntimeError(f"no summary table '{phrase}' in the BEA API table list")
    return {"use": pick("use of commodities by industries"), "make": pick("supply of commodities by industries")}


def years():
    vals = _pv(_cached("api_years.json", {"method": "GetParameterValues", "DataSetName": "InputOutput",
                                          "ParameterName": "Year"}))
    return sorted({int(str(v.get("Key"))) for v in vals if str(v.get("Key", "")).isdigit()}, reverse=True)


def _field(row, *names):
    low = {k.lower(): v for k, v in row.items()}
    for n in names:
        if n.lower() in low:
            return low[n.lower()]
    return None


def frame(rows):
    """API rows -> (table with BEA codes as row and column labels, {code: description})."""
    recs, names = [], {}
    for r in rows:
        rc, cc = str(_field(r, "RowCode") or "").strip(), str(_field(r, "ColCode") or "").strip()
        names.setdefault(rc, str(_field(r, "RowDescr", "RowDescription") or rc).strip())
        names.setdefault(cc, str(_field(r, "ColDescr", "ColDescription") or cc).strip())
        recs.append((rc, cc, pd.to_numeric(str(_field(r, "DataValue") or "").replace(",", ""), errors="coerce")))
    d = pd.DataFrame(recs, columns=["row", "col", "value"])
    return d.pivot_table(index="row", columns="col", values="value", aggfunc="sum").fillna(0.0), names


def table(tid, year):
    res = _cached(f"api_table_{tid}_{year}.json", {"method": "GetData", "DataSetName": "InputOutput",
                                                   "TableID": tid, "Year": year})
    rows = flat(res).get("Data", [])
    if not rows:
        raise LookupError(f"BEA API: no data for table {tid}, {year}")
    return frame(rows)


def convert(U, S):
    """Supply-use tables -> the make-use shape the model reads (io_data.read_bea_table).

    U: Use of commodities by industries (purchasers' prices), commodities x (industries, final uses), with rows
       T018 (industry output, basic prices), V001 (compensation), VABAS and VAPRO (value added at basic and at
       producers' prices). Industry output is moved to producers' prices by adding VAPRO - VABAS (other taxes on
       production less subsidies), so output and value added match the make-use tables' valuation.
    S: Supply of commodities by industries, commodities x (industries, MCIF imports, MADJ, Trade and Trans margins,
       T007 commodity output, T016 total supply at purchasers' prices).
    Trade and transport margins are taken out of each commodity's uses in proportion to its purchasers' value
    (margin / total supply at purchasers' prices, the same rate for every use) and added to the trade and transport
    commodities in proportion to their margin supply; this is the standard proportionality assumption (Miller &
    Blair, 2022, ch. 2) and gives uses close to producers' prices. Imports (MCIF + MADJ) become the negative import
    column F050 of the make-use tables."""
    uses = [c for c in U.columns if not c.startswith("T")]
    tot = S["T016"].reindex(U.index).fillna(0)
    Up = U[uses].copy()
    for col in ("Trade", "Trans"):
        if col not in S:
            continue
        m = S[col].reindex(U.index).fillna(0)       # + on goods (margin added to them), - on the margin services
        rate = (m.clip(lower=0) / tot.where(tot > 0)).fillna(0)             # margin per $ of purchasers' value
        cell = Up.mul(rate, axis=0)                                         # margin inside each use
        Up = Up - cell
        sup = (-m).clip(lower=0)                                            # margin commodities supply the service
        if sup.sum() > 0:
            Up = Up.add(pd.DataFrame(sup.values[:, None] / sup.sum() * cell.sum().values[None, :],
                                     index=sup.index, columns=uses), fill_value=0)
    use = Up.copy()
    use["F050"] = -(S["MCIF"].reindex(use.index).fillna(0) + S.get("MADJ", pd.Series(dtype=float)).reindex(use.index).fillna(0))
    # producers' prices, as in the make-use tables: industry output and value added include other taxes on
    # production less subsidies (property, severance and similar taxes): VAPRO - VABAS
    tax = (U.loc["VAPRO"] - U.loc["VABAS"]).reindex(use.columns).fillna(0)
    use.loc["Total Industry Output"] = U.loc["T018"].reindex(use.columns).fillna(0) + tax
    use.loc["Total Value Added"] = U.loc["VAPRO"].reindex(use.columns).fillna(0)
    inds = [c for c in S.columns if c in U.columns and c in S.index]           # industry columns that are also commodities
    make = S.loc[S.index.intersection(U.index), inds].T.copy()                  # industries x commodities
    make.loc["Total Commodity Output"] = S["T007"].reindex(make.columns).fillna(0)
    return use, make


def tables():
    """(use, make, names, year): the newest year with both tables, converted to the make-use shape and checked for
    every row and column the model reads."""
    ids = table_ids()
    last_err = None
    for y in years()[:3]:
        try:
            U, names = table(ids["use"], y)
            S, _ = table(ids["make"], y)
        except LookupError as e:                  # year listed but not yet published for these tables
            last_err = e
            continue
        need_u = [x for x in ("T018", "VABAS", "VAPRO", "V001") if x not in U.index] + [x for x in ("F010",) if x not in U.columns]
        need_s = [x for x in ("T007", "T016", "MCIF") if x not in S.columns]
        if need_u or need_s:
            raise RuntimeError(f"BEA API tables for {y} lack {', '.join(need_u + need_s)}")
        use, make = convert(U, S)
        names.update({"Total Industry Output": "Total industry output", "Total Value Added": "Value added",
                      "Total Commodity Output": "Total commodity output"})
        return use, make, names, y
    raise RuntimeError(f"BEA API: no year with both tables ({last_err})")
