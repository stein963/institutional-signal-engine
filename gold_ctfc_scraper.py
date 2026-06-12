"""
=============================================================
  CFTC Gold Data Scraper
  Scrapes all major CFTC COT report types filtered for GOLD
  Reports covered:
    1. Legacy Futures Only
    2. Legacy Combined (Futures + Options)
    3. Disaggregated Futures Only
    4. Disaggregated Combined
    5. Traders in Financial Futures (TFF) Futures Only
    6. Traders in Financial Futures (TFF) Combined
    7. Supplemental / CIT (Commodity Index Traders)
    8. Bank Participation Report  (BPR)
  Also fetches SEC 13F / 13G holdings for gold ETFs
  (GLD, IAU, SGOL, GLDM) as proxy for institutional positioning.

  Output: one CSV per report in ./gold_cftc_output/
=============================================================
  USAGE:
    pip install requests pandas tqdm
    python gold_cftc_scraper.py

  OPTIONAL FLAGS (edit CONFIG below):
    YEARS_BACK   – how many years of history to pull  (default 5)
    SAVE_DIR     – folder to write CSVs               (default ./gold_cftc_output)
    SEC_ETFS     – list of gold ETF tickers for 13F/13G scraping
=============================================================
"""

import os
import time
import json
import logging
import requests
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from tqdm import tqdm

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────
CONFIG = {
    "YEARS_BACK": 5,                        # history depth
    "SAVE_DIR": "./gold_cftc_output",       # output folder
    "SLEEP_BETWEEN_CALLS": 0.5,            # seconds between API calls (be polite)
    "SEC_ETFS": ["GLD", "IAU", "SGOL", "GLDM"],  # gold ETFs for 13F/13G
    "SEC_CIK_MAP": {                        # known CIKs for gold ETFs
        "GLD":  "0001222333",
        "IAU":  "0001334635",
        "SGOL": "0001471978",
        "GLDM": "0001718819",
    },
}

# ─────────────────────────────────────────────────────────────
# CFTC Socrata dataset IDs
# ─────────────────────────────────────────────────────────────
CFTC_BASE = "https://publicreporting.cftc.gov/resource"

DATASETS = {
    "legacy_futures_only":        "6dca-aqww",
    "legacy_combined":            "jun7-fc8e",
    "disaggregated_futures_only": "72hh-3qpy",
    "disaggregated_combined":     "kh3c-gbw2",
    "tff_futures_only":           "gpe5-46if",
    "tff_combined":               "yw9f-hn96",
    "supplemental_cit":           "4zgm-a668",
}

# Gold futures contract market code on COMEX
GOLD_CODE = "088691"
# Gold appears with various names across datasets – filter broadly
GOLD_KEYWORDS = ["GOLD", "gold"]

# ─────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("gold_cftc")


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────
def make_save_dir(path: str) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def safe_get(url: str, params: dict = None, retries: int = 3) -> requests.Response | None:
    """GET with retry/back-off."""
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, params=params, timeout=30)
            r.raise_for_status()
            return r
        except requests.HTTPError as e:
            log.warning(f"HTTP {e.response.status_code} on attempt {attempt}: {url}")
        except requests.RequestException as e:
            log.warning(f"Request error on attempt {attempt}: {e}")
        time.sleep(2 ** attempt)
    log.error(f"All {retries} attempts failed for {url}")
    return None


def iso_date(years_back: int) -> str:
    dt = datetime.utcnow() - timedelta(days=365 * years_back)
    return dt.strftime("%Y-%m-%dT00:00:00")


# ─────────────────────────────────────────────────────────────
# 1.  CFTC COT scraper via Socrata API
# ─────────────────────────────────────────────────────────────
def fetch_cot_dataset(dataset_id: str, report_name: str, years_back: int) -> pd.DataFrame:
    """
    Pull all Gold rows from a CFTC Socrata dataset.
    Uses SoQL $where + $limit/$offset pagination.
    """
    url = f"{CFTC_BASE}/{dataset_id}.json"
    since = iso_date(years_back)
    limit = 1000
    offset = 0
    all_rows = []

    # Build the gold filter – CFTC uses 'contract_market_name' or 'market_and_exchange_names'
    gold_filter = (
        f"(cftc_contract_market_code='{GOLD_CODE}' OR "
        f"UPPER(contract_market_name) LIKE '%GOLD%' OR "
        f"UPPER(market_and_exchange_names) LIKE '%GOLD%')"
    )
    date_filter = f"report_date_as_yyyy_mm_dd >= '{since}'"
    where_clause = f"{gold_filter} AND {date_filter}"

    log.info(f"Fetching [{report_name}] from {since[:10]} …")

    with tqdm(desc=f"  {report_name}", unit=" rows", leave=False) as bar:
        while True:
            params = {
                "$where":  where_clause,
                "$limit":  limit,
                "$offset": offset,
                "$order":  "report_date_as_yyyy_mm_dd DESC",
            }
            resp = safe_get(url, params=params)
            if resp is None:
                break

            batch = resp.json()
            if not batch:
                break

            all_rows.extend(batch)
            bar.update(len(batch))
            offset += limit

            if len(batch) < limit:
                break   # last page

            time.sleep(CONFIG["SLEEP_BETWEEN_CALLS"])

    if not all_rows:
        log.warning(f"  No Gold data returned for [{report_name}]")
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)
    log.info(f"  ✓ {len(df)} rows fetched for [{report_name}]")
    return df


# ─────────────────────────────────────────────────────────────
# 2.  CFTC Bank Participation Report (BPR) – CSV download
# ─────────────────────────────────────────────────────────────
BPR_BASE = "https://www.cftc.gov/files/dea/history"

def fetch_bank_participation_gold(years_back: int) -> pd.DataFrame:
    """
    BPR is published as compressed TXT files per year.
    We download each year's file and filter for gold.
    """
    current_year = datetime.utcnow().year
    start_year   = current_year - years_back
    frames = []

    log.info("Fetching Bank Participation Reports (BPR) …")

    for year in range(start_year, current_year + 1):
        url = f"{BPR_BASE}/bpr_{year}.txt"
        resp = safe_get(url)
        if resp is None:
            continue

        try:
            from io import StringIO
            # BPR files are fixed-width; attempt to parse
            lines = resp.text.splitlines()
            gold_lines = [l for l in lines if "GOLD" in l.upper()]
            if not gold_lines:
                continue
            # Convert to a simple DataFrame
            df = pd.DataFrame({"raw_line": gold_lines, "year": year})
            frames.append(df)
            log.info(f"  BPR {year}: {len(gold_lines)} gold lines")
        except Exception as e:
            log.warning(f"  BPR {year} parse error: {e}")

        time.sleep(CONFIG["SLEEP_BETWEEN_CALLS"])

    if not frames:
        log.warning("  No BPR data found")
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    return combined


# ─────────────────────────────────────────────────────────────
# 3.  SEC 13F / 13G  – EDGAR full-text search
# ─────────────────────────────────────────────────────────────
SEC_EDGAR_SEARCH = "https://efts.sec.gov/LATEST/search-index?q=%22{}%22&dateRange=custom&startdt={}&enddt={}&forms={}"
SEC_SUBMISSIONS  = "https://data.sec.gov/submissions/CIK{}.json"
SEC_HEADERS = {"User-Agent": "GoldDataScraper research@example.com"}   # required by SEC

def fetch_sec_filings(form_type: str, ticker: str, cik: str, years_back: int) -> pd.DataFrame:
    """
    Use SEC EDGAR to get 13F or 13G filing metadata for a gold ETF.
    Returns a DataFrame of filing dates and accession numbers.
    """
    end_dt   = datetime.utcnow().strftime("%Y-%m-%d")
    start_dt = (datetime.utcnow() - timedelta(days=365 * years_back)).strftime("%Y-%m-%d")

    log.info(f"Fetching SEC {form_type} filings for {ticker} (CIK {cik}) …")

    # Use the submissions endpoint for reliable data
    url = SEC_SUBMISSIONS.format(cik.lstrip("0"))
    resp = safe_get(url, retries=3)
    if resp is None:
        return pd.DataFrame()

    data = resp.json()
    filings = data.get("filings", {}).get("recent", {})

    if not filings:
        return pd.DataFrame()

    df = pd.DataFrame({
        "accessionNumber": filings.get("accessionNumber", []),
        "filingDate":      filings.get("filingDate", []),
        "form":            filings.get("form", []),
        "reportDate":      filings.get("reportDate", []),
        "primaryDocument": filings.get("primaryDocument", []),
    })

    # Filter for the requested form type
    target_forms = [form_type, form_type + "/A"]   # include amendments
    df = df[df["form"].isin(target_forms)].copy()

    # Filter by date range
    df["filingDate"] = pd.to_datetime(df["filingDate"], errors="coerce")
    df = df[df["filingDate"] >= start_dt]

    df["ticker"] = ticker
    df["cik"]    = cik
    df["form_type"] = form_type

    # Build direct EDGAR URL for each filing
    df["edgar_url"] = df.apply(
        lambda r: (
            f"https://www.sec.gov/Archives/edgar/full-index/"
            f"{r['filingDate'].year}/{_quarter(r['filingDate'])}/"
        ),
        axis=1,
    )

    log.info(f"  ✓ {len(df)} {form_type} filings for {ticker}")
    return df


def _quarter(dt) -> str:
    q = (dt.month - 1) // 3 + 1
    return f"QTR{q}"


def fetch_all_sec(years_back: int) -> pd.DataFrame:
    """Fetch 13F + 13G for all configured gold ETFs."""
    frames = []
    for ticker, cik in CONFIG["SEC_CIK_MAP"].items():
        for form in ["13F-HR", "SC 13G", "SC 13G/A"]:
            df = fetch_sec_filings(form, ticker, cik, years_back)
            if not df.empty:
                frames.append(df)
            time.sleep(CONFIG["SLEEP_BETWEEN_CALLS"])
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


# ─────────────────────────────────────────────────────────────
# 4.  CFTC Cotton on Call / Weekly Swaps (bonus – gold relevant)
# ─────────────────────────────────────────────────────────────
def fetch_weekly_swaps_gold(years_back: int) -> pd.DataFrame:
    """
    CFTC Weekly Swaps report – filter for gold commodity.
    Dataset ID: p98q-3m3m  (swaps data via Socrata)
    """
    dataset_id = "p98q-3m3m"
    url = f"{CFTC_BASE}/{dataset_id}.json"
    since = iso_date(years_back)
    params = {
        "$where": f"UPPER(commodity) LIKE '%GOLD%' AND report_date >= '{since}'",
        "$limit": 5000,
        "$order": "report_date DESC",
    }
    log.info("Fetching Weekly Swaps (Gold) …")
    resp = safe_get(url, params=params)
    if resp is None:
        return pd.DataFrame()
    rows = resp.json()
    if not rows:
        log.warning("  No weekly swap gold data found")
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    log.info(f"  ✓ {len(df)} rows (weekly swaps gold)")
    return df


# ─────────────────────────────────────────────────────────────
# 5.  Save helper
# ─────────────────────────────────────────────────────────────
def save(df: pd.DataFrame, name: str, save_dir: Path) -> None:
    if df.empty:
        log.warning(f"  Skipping save for [{name}] – empty DataFrame")
        return
    fpath = save_dir / f"{name}.csv"
    df.to_csv(fpath, index=False)
    log.info(f"  Saved → {fpath}  ({len(df)} rows, {len(df.columns)} cols)")


# ─────────────────────────────────────────────────────────────
# 6.  Summary report
# ─────────────────────────────────────────────────────────────
def write_summary(results: dict, save_dir: Path) -> None:
    summary = []
    for name, df in results.items():
        summary.append({
            "report":   name,
            "rows":     len(df),
            "columns":  len(df.columns) if not df.empty else 0,
            "date_min": df.get("report_date_as_yyyy_mm_dd", pd.Series()).min() if not df.empty else "–",
            "date_max": df.get("report_date_as_yyyy_mm_dd", pd.Series()).max() if not df.empty else "–",
        })
    df_sum = pd.DataFrame(summary)
    fpath  = save_dir / "_SUMMARY.csv"
    df_sum.to_csv(fpath, index=False)
    log.info(f"\n{'='*60}")
    log.info("SUMMARY")
    log.info('='*60)
    print(df_sum.to_string(index=False))
    log.info(f"\nSummary saved → {fpath}")


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
def main():
    save_dir   = make_save_dir(CONFIG["SAVE_DIR"])
    years_back = CONFIG["YEARS_BACK"]
    results    = {}

    log.info("=" * 60)
    log.info("  CFTC Gold Data Scraper")
    log.info(f"  Coverage: last {years_back} years")
    log.info(f"  Output dir: {save_dir.resolve()}")
    log.info("=" * 60)

    # ── COT Reports (7 datasets) ─────────────────────────────
    for report_name, dataset_id in DATASETS.items():
        df = fetch_cot_dataset(dataset_id, report_name, years_back)
        results[report_name] = df
        save(df, report_name, save_dir)
        time.sleep(CONFIG["SLEEP_BETWEEN_CALLS"])

    # ── Bank Participation Report ────────────────────────────
    bpr_df = fetch_bank_participation_gold(years_back)
    results["bank_participation_report"] = bpr_df
    save(bpr_df, "bank_participation_report", save_dir)

    # ── Weekly Swaps ─────────────────────────────────────────
    swaps_df = fetch_weekly_swaps_gold(years_back)
    results["weekly_swaps_gold"] = swaps_df
    save(swaps_df, "weekly_swaps_gold", save_dir)

    # ── SEC 13F / 13G ─────────────────────────────────────────
    sec_df = fetch_all_sec(years_back)
    results["sec_13f_13g_gold_etfs"] = sec_df
    save(sec_df, "sec_13f_13g_gold_etfs", save_dir)

    # ── Summary ───────────────────────────────────────────────
    write_summary(results, save_dir)

    log.info("\nDone! All files written to: " + str(save_dir.resolve()))


if __name__ == "__main__":
    main()