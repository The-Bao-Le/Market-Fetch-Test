from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf


# ------------------------------------------------------------
# Cache setup
# ------------------------------------------------------------
CACHE_DIR = Path(".cache/yfinance")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
yf.set_tz_cache_location(str(CACHE_DIR))


# ------------------------------------------------------------
# Time setup
# ------------------------------------------------------------
EASTERN_TZ = ZoneInfo("America/New_York")


# ------------------------------------------------------------
# Ticker set
# ------------------------------------------------------------
TICKERS = {
    "SPY": {
        "asset_name": "S&P 500 proxy",
        "asset_group": "Index proxy",
    },
    "QQQ": {
        "asset_name": "Nasdaq 100 proxy",
        "asset_group": "Index proxy",
    },
    "IWM": {
        "asset_name": "Russell 2000 proxy",
        "asset_group": "Index proxy",
    },
    "XLK": {
        "asset_name": "Technology sector proxy",
        "asset_group": "Sector proxy",
    },
    "XLF": {
        "asset_name": "Financials sector proxy",
        "asset_group": "Sector proxy",
    },
    "XLE": {
        "asset_name": "Energy sector proxy",
        "asset_group": "Sector proxy",
    },
}


# ------------------------------------------------------------
# Output paths
# ------------------------------------------------------------
OUTPUT_DIR = Path("data")
ARCHIVE_DIR = OUTPUT_DIR / "archive"

SUMMARY_CSV_OUTPUT = OUTPUT_DIR / "friday_close_market_snapshot.csv"
SUMMARY_JSON_OUTPUT = OUTPUT_DIR / "friday_close_market_snapshot.json"

FIVE_DAY_CSV_OUTPUT = OUTPUT_DIR / "friday_close_5d_prices.csv"
FIVE_DAY_JSON_OUTPUT = OUTPUT_DIR / "friday_close_5d_prices.json"


def calculate_return_pct(series: pd.Series, days: int) -> float | None:
    """
    Calculates return from the latest close compared with the close
    from N trading sessions ago.
    """
    clean_series = series.dropna()

    if len(clean_series) <= days:
        return None

    latest_price = clean_series.iloc[-1]
    previous_price = clean_series.iloc[-(days + 1)]

    return round(((latest_price / previous_price) - 1) * 100, 2)


def calculate_window_return_pct(series: pd.Series) -> float | None:
    """
    Calculates return across the exported 5-row window.
    Example: first close in the 5D window to last close in the 5D window.
    """
    clean_series = series.dropna()

    if len(clean_series) < 2:
        return None

    first_price = clean_series.iloc[0]
    latest_price = clean_series.iloc[-1]

    return round(((latest_price / first_price) - 1) * 100, 2)


def classify_signal(five_day_return: float | None, above_20d_average: bool | None) -> str:
    """
    Simple explainable signal logic.
    """
    if five_day_return is None or above_20d_average is None:
        return "Insufficient data"

    if five_day_return > 0 and above_20d_average:
        return "Bullish"

    if five_day_return < 0 and not above_20d_average:
        return "Bearish"

    return "Mixed / Neutral"


def empty_summary_row(
    ticker: str,
    metadata: dict,
    reason: str,
    run_timestamp_utc: str,
    run_timestamp_et: str,
) -> dict:
    return {
        "ticker": ticker,
        "asset_name": metadata["asset_name"],
        "asset_group": metadata["asset_group"],
        "latest_date": None,
        "latest_close": None,
        "five_day_return_pct": None,
        "last_5_close_return_pct": None,
        "twenty_day_return_pct": None,
        "sma_20": None,
        "above_20d_average": None,
        "last_5_window_start": None,
        "last_5_window_end": None,
        "signal": reason,
        "run_timestamp_utc": run_timestamp_utc,
        "run_timestamp_et": run_timestamp_et,
    }


def fetch_one_ticker(ticker: str) -> pd.Series:
    """
    Fetch one ticker at a time.

    Using Ticker().history() avoids the multi-index issue that appeared earlier
    with yf.download() on some systems.
    """
    data = yf.Ticker(ticker).history(
        period="2mo",
        interval="1d",
        auto_adjust=True,
    )

    if data.empty:
        return pd.Series(dtype="float64")

    if "Close" not in data.columns:
        return pd.Series(dtype="float64")

    return data["Close"].dropna()


def build_market_snapshot() -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_rows = []
    five_day_price_rows = []

    now_utc = datetime.now(timezone.utc)
    now_et = now_utc.astimezone(EASTERN_TZ)

    run_timestamp_utc = now_utc.isoformat()
    run_timestamp_et = now_et.isoformat()

    print("Fetching Friday close market snapshot...")
    print(f"Run timestamp UTC: {run_timestamp_utc}")
    print(f"Run timestamp ET:  {run_timestamp_et}")

    for ticker, metadata in TICKERS.items():
        print(f"Fetching {ticker}...")

        try:
            series = fetch_one_ticker(ticker)
        except Exception as error:
            summary_rows.append(
                empty_summary_row(
                    ticker=ticker,
                    metadata=metadata,
                    reason=f"Fetch error: {type(error).__name__}",
                    run_timestamp_utc=run_timestamp_utc,
                    run_timestamp_et=run_timestamp_et,
                )
            )
            continue

        if series.empty:
            summary_rows.append(
                empty_summary_row(
                    ticker=ticker,
                    metadata=metadata,
                    reason="No price data returned",
                    run_timestamp_utc=run_timestamp_utc,
                    run_timestamp_et=run_timestamp_et,
                )
            )
            continue

        latest_date = series.index[-1].date().isoformat()
        latest_close = round(float(series.iloc[-1]), 2)

        last_5_series = series.tail(5)
        last_5_window_start = last_5_series.index[0].date().isoformat()
        last_5_window_end = last_5_series.index[-1].date().isoformat()

        for sequence_number, (price_date, close_price) in enumerate(last_5_series.items(), start=1):
            five_day_price_rows.append(
                {
                    "ticker": ticker,
                    "asset_name": metadata["asset_name"],
                    "asset_group": metadata["asset_group"],
                    "sequence_in_5d_window": sequence_number,
                    "date": price_date.date().isoformat(),
                    "close": round(float(close_price), 2),
                    "run_timestamp_utc": run_timestamp_utc,
                    "run_timestamp_et": run_timestamp_et,
                }
            )

        five_day_return = calculate_return_pct(series, 5)
        last_5_close_return = calculate_window_return_pct(last_5_series)
        twenty_day_return = calculate_return_pct(series, 20)

        if len(series) >= 20:
            sma_20 = round(float(series.tail(20).mean()), 2)
            above_20d_average = latest_close > sma_20
        else:
            sma_20 = None
            above_20d_average = None

        signal = classify_signal(five_day_return, above_20d_average)

        summary_rows.append(
            {
                "ticker": ticker,
                "asset_name": metadata["asset_name"],
                "asset_group": metadata["asset_group"],
                "latest_date": latest_date,
                "latest_close": latest_close,
                "five_day_return_pct": five_day_return,
                "last_5_close_return_pct": last_5_close_return,
                "twenty_day_return_pct": twenty_day_return,
                "sma_20": sma_20,
                "above_20d_average": above_20d_average,
                "last_5_window_start": last_5_window_start,
                "last_5_window_end": last_5_window_end,
                "signal": signal,
                "run_timestamp_utc": run_timestamp_utc,
                "run_timestamp_et": run_timestamp_et,
            }
        )

    summary_df = pd.DataFrame(summary_rows)
    five_day_prices_df = pd.DataFrame(five_day_price_rows)

    return summary_df, five_day_prices_df


def save_outputs(summary_df: pd.DataFrame, five_day_prices_df: pd.DataFrame) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    summary_df.to_csv(SUMMARY_CSV_OUTPUT, index=False)
    summary_df.to_json(SUMMARY_JSON_OUTPUT, orient="records", indent=2)

    five_day_prices_df.to_csv(FIVE_DAY_CSV_OUTPUT, index=False)
    five_day_prices_df.to_json(FIVE_DAY_JSON_OUTPUT, orient="records", indent=2)

    # Also save date-stamped archive copies.
    if "latest_date" in summary_df.columns and summary_df["latest_date"].notna().any():
        snapshot_date = str(summary_df["latest_date"].dropna().max())
    else:
        snapshot_date = datetime.now(EASTERN_TZ).date().isoformat()

    archive_summary_csv = ARCHIVE_DIR / f"market_snapshot_{snapshot_date}.csv"
    archive_5d_csv = ARCHIVE_DIR / f"market_5d_prices_{snapshot_date}.csv"

    summary_df.to_csv(archive_summary_csv, index=False)
    five_day_prices_df.to_csv(archive_5d_csv, index=False)

    print(f"\nSaved summary CSV: {SUMMARY_CSV_OUTPUT}")
    print(f"Saved summary JSON: {SUMMARY_JSON_OUTPUT}")
    print(f"Saved 5D prices CSV: {FIVE_DAY_CSV_OUTPUT}")
    print(f"Saved 5D prices JSON: {FIVE_DAY_JSON_OUTPUT}")
    print(f"Saved archive summary: {archive_summary_csv}")
    print(f"Saved archive 5D prices: {archive_5d_csv}")


def main() -> None:
    summary_df, five_day_prices_df = build_market_snapshot()
    save_outputs(summary_df, five_day_prices_df)

    print("\nFriday close market snapshot:")
    print(
        summary_df[
            [
                "ticker",
                "latest_date",
                "latest_close",
                "five_day_return_pct",
                "last_5_close_return_pct",
                "twenty_day_return_pct",
                "signal",
            ]
        ]
    )


if __name__ == "__main__":
    main()