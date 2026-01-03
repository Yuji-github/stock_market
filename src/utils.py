import pandas as pd
import yfinance as yf
from dotenv import load_dotenv
import os
import requests
from typing import Tuple, Dict, List, Any, Optional
import logging
import time
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from google import genai
from dash import dcc


# Configuration
load_dotenv()  # Load environment variables
JQUANTS_API = os.environ.get("JQUANTS_API")
GEMINI_API = os.environ.get("GEMINI_API")
if not JQUANTS_API:
    logging.error("ERROR: No JQUANTS_API set.")
    exit()

if not GEMINI_API:
    logging.warning("Warning: No GEMINI_API set. Disable to analysis using Gemini")

API_URL = "https://api.jquants.com/v2"
sleep_time = 3


def create_company_list() -> None:
    """
    Reads the EDINET code list CSV, generates yfinance-compatible ticker symbols,
    and saves the processed DataFrame to a Parquet file.

    The function performs the following steps:
    1. Reads 'EdinetcodeDlInfo.csv' (CP932 encoding).
    2. Extracts the '証券コード' (Securities Code).
    3. Converts valid codes to yfinance format (e.g., '13760' -> '1376.T').
    4. Saves the result to 'company_list.parquet'.

    Input Path: /workspace/src/edinet_company_list/EdinetcodeDlInfo.csv
    Output Path: /workspace/src/edinet_company_list/company_list.parquet

    Raises:
        FileNotFoundError: If the input CSV does not exist.
        Exception: For other processing errors.
    """

    # Inner helper function to keep logic encapsulated
    def convert_to_ticker(code_val: Any) -> Optional[str]:
        """
        Converts EDINET securities code to yfinance ticker format.

        Args:
            code_val: The raw value from the CSV (int, float, or str).

        Returns:
            str: Ticker in 'XXXX.T' format (e.g., '1376.T'), or None if invalid.
        """
        if pd.isna(code_val):
            return None  # Company is not listed or code is missing

        # Clean the input to a string
        code_str = str(code_val).strip()

        # Handle cases where pandas reads integers as floats (e.g., '13760.0')
        if code_str.endswith(".0"):
            code_str = code_str[:-2]

        # EDINET codes are typically 5 digits (e.g., 13760).
        # yfinance expects 4 digits + .T (e.g., 1376.T).
        # We take the first 4 characters.
        if len(code_str) >= 4:
            return f"{code_str[:4]}.T"

        return None

    try:
        # Load the EDINET CSV
        # cp932 is the standard encoding for Japanese government CSVs
        df = pd.read_csv(
            "/workspace/src/edinet_company_list/EdinetcodeDlInfo.csv",
            encoding="cp932",
            skiprows=1,
        )

        if "証券コード" not in df.columns:
            print("Error: Column '証券コード' not found in input CSV.")
            return

        # Apply the conversion logic
        df["yfinance_ticker"] = df["証券コード"].apply(convert_to_ticker)

        # Save to Parquet
        df.to_parquet(
            "/workspace/src/edinet_company_list/company_list.parquet", index=False
        )
        logging.info("Successfully created company_list.parquet")

    except FileNotFoundError:
        logging.error(
            "Error: Input file '/workspace/src/edinet_company_list/EdinetcodeDlInfo.csv' not found."
        )
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")


def get_pl_bs_cashflow(
    code: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Fetches financial statements (P/L, B/S, C/F) from J-Quants and converts them
    to a JSON-serializable format (List of Dictionaries) compatible with Dash.

    P/L (Profit & Loss) Columns:
        - Sales: Revenue 売上高
        - OP: Operating Profit 営業利益
        - OdP: Ordinary Profit 経常利益
        - NP: Net Profit 当期純利益
        - EPS: Earnings Per Share 1株当たり当期純利益
        - DEPS: Diluted EPS 潜在株式調整後1株利益

    B/S (Balance Sheet) Columns:
        - TA: Total Assets 総資産
        - CashEq: Cash and Equivalents 現金及び現金同等物残高
        - Eq: Equity (Net Assets) 純資産（自己資本）
        - EqAR: Equity Ratio 自己資本比率
        - BPS: Book-value Per Share 1株当たり純資産

    C/F (Cash Flow) Columns:
        - CFO: Operating Cash Flow 営業活動によるCF
        - CFI: Investing Cash Flow 投資活動によるCF
        - CFF: Financing Cash Flow 投資活動によるCF
        - CashEq: Cash and Equivalents 現金及び現金同等物残高

    Args:
        code (str): The securities code (e.g., '7203').

    Returns:
        Tuple[List[Dict], List[Dict], List[Dict]]:
            A tuple containing three lists of dictionaries corresponding to
            (P/L data, B/S data, C/F data).
            Returns ([], [], []) if the API call fails or code is invalid.
    """
    # Return empty lists for consistency with Dash
    if not code:
        return [], [], []

    # Columns to extract
    pl_cols = [
        "Code",
        "DocType",
        "CurPerEn",
        "CurFYEn",
        "Sales",
        "OP",
        "OdP",
        "NP",
        "EPS",
        "DEPS",
    ]  # FEPS always empty, remove
    bl_cols = [
        "Code",
        "DocType",
        "CurPerEn",
        "CurFYEn",
        "TA",
        "CashEq",
        "Eq",
        "EqAR",
        "BPS",
    ]
    cf_cols = ["Code", "DocType", "CurPerEn", "CurFYEn", "CFO", "CFI", "CFF", "CashEq"]
    numeric_cols = [
        "Sales",
        "OP",
        "OdP",
        "NP",
        "EPS",
        "DEPS",
        "TA",
        "CashEq",
        "Eq",
        "EqAR",
        "BPS",
        "CFO",
        "CFI",
        "CFF",
    ]  # to convert

    headers = {"x-api-key": JQUANTS_API}
    params = {"code": code}

    max_retries = 3
    for attempt in range(max_retries):
        try:
            res = requests.get(
                f"{API_URL}/fins/summary", params=params, headers=headers
            )

            if res.status_code == 200:
                d = res.json()
                data = d.get("data", [])

                # Handle Pagination
                while "pagination_key" in d:
                    params["pagination_key"] = d["pagination_key"]
                    res = requests.get(
                        f"{API_URL}/fins/summary", params=params, headers=headers
                    )
                    if res.status_code != 200:
                        break
                    d = res.json()
                    data += d.get("data", [])

                df = pd.DataFrame(data)

                for col in numeric_cols:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

                pl_df = df[pl_cols]
                pl_df["Operating_Margin"] = pl_df["OP"] / pl_df["Sales"]
                bs_df = df[bl_cols]
                bs_df["Liabilities"] = bs_df["TA"] - bs_df["Eq"]
                bs_df["Equity_Ratio"] = bs_df["Eq"] / bs_df["TA"]
                cf_df = df[cf_cols]
                cf_df["Free_Cash_Flow"] = cf_df["CFO"] + cf_df["CFI"]

                # Convert to List[Dict] for Dash/JSON compatibility
                # Example: [{'Sales': 100, 'OP': 10}, ...]
                return (
                    pl_df.to_dict("records"),
                    bs_df.to_dict("records"),
                    cf_df.to_dict("records"),
                )
            else:
                logging.error(f"J-Quants API Error: {res.status_code}")
                logging.warning(f"Retry in {sleep_time} secconds: {attempt+1} / 5")
                time.sleep(sleep_time)

        except Exception as e:
            logging.error(f"Error fetching data: {e}")
            logging.warning(f"Retry in {sleep_time} secconds: {attempt+1} / 5")
            time.sleep(sleep_time)

    return [], [], []


def calculate_valuation_metrics(
    yf_code: str, pl_data: List[Dict[str, Any]], bs_data: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Calculates valuation metrics (PER, PBR, ROE, ROA) combining
    J-Quants financial data (passed as JSON/List[Dict]) and yfinance real-time price.

    Args:
        yf_code (str): The ticker symbol for yfinance (e.g., '7203.T').
        pl_data (List[Dict]): Profit & Loss data list (from get_pl_bs_cashflow).
        bs_data (List[Dict]): Balance Sheet data list (from get_pl_bs_cashflow).

    Returns:
        Dict[str, Any]: A dictionary containing the calculated metrics.
                        Returns empty dict {} on failure.
    """

    def safe_float(val):
        try:
            return float(val) if val not in [None, "", "NaN"] else 0.0
        except:
            return 0.0

    # 1. Validation:
    if not yf_code or not pl_data or not bs_data:
        return {}

    # 2. Re-create DataFrames for easy sorting and type conversion
    try:
        pl_df = pd.DataFrame(pl_data)
        bs_df = pd.DataFrame(bs_data)

        pl_df["CurPerEn"] = pd.to_datetime(pl_df["CurPerEn"])
        bs_df["CurPerEn"] = pd.to_datetime(bs_df["CurPerEn"])

        pl_df = pl_df.sort_values("CurPerEn")
        bs_df = bs_df.sort_values("CurPerEn")

        # To remvoe EarnForecastRevision
        pl_df = pl_df.dropna(subset=["Sales"])
        bs_df = bs_df.dropna(subset=["TA"])

        # To avoid giving wrong data
        is_annual_data = False

        fy_rows_pl = pl_df[
            pl_df["DocType"]
            .astype(str)
            .str.contains("FY|Annual", case=False, regex=True)
        ]
        if not fy_rows_pl.empty:
            latest_pl_annual = fy_rows_pl.iloc[-1]
            is_annual_data = True
        else:
            latest_pl_annual = pl_df.iloc[-1]
            is_annual_data = False

        latest_bs_snapshot = bs_df.iloc[-1]

        # Extract values and ensure they are floats (API often returns strings)
        eps = safe_float(latest_pl_annual.get("EPS"))
        np_val = safe_float(latest_pl_annual.get("NP"))

        bps = safe_float(latest_bs_snapshot.get("BPS"))
        equity_latest = safe_float(latest_bs_snapshot.get("Eq"))
        ta_latest = safe_float(latest_bs_snapshot.get("TA"))

    except (ValueError, KeyError, IndexError) as e:
        logging.error(f"Data processing error: {e}")
        return {}

    # 3. Get Current Price from yfinance
    max_retries = 3
    hist = pd.DataFrame()
    for attempt in range(max_retries):
        try:
            ticker = yf.Ticker(yf_code)
            hist = ticker.history(period="1d")

            if hist.empty:
                logging.warning(f"No price data found for {yf_code}")
                logging.warning(f"Retry in {sleep_time} secconds: {attempt+1} / 5")
                time.sleep(sleep_time)

            current_price = hist["Close"].iloc[-1]

        except Exception as e:
            logging.error(f"yfinance error: {e}")
            logging.warning(f"Retry in {sleep_time} secconds: {attempt+1} / 5")
            time.sleep(sleep_time)

        if not hist.empty:
            break

    # Failed to get data
    if hist.empty:
        return {}

    # 4. Calculate Metrics
    metrics = {
        "Code": yf_code.split(".")[0],
        "Price": current_price,
        "EquityRatio": (
            round((equity_latest / ta_latest) * 100, 1) if ta_latest > 0 else None
        ),
        "PBR": round(current_price / bps, 2) if bps > 0 else None,
    }

    if is_annual_data:
        metrics["PER"] = round(current_price / eps, 2) if eps > 0 else None
        metrics["ROE"] = (
            round((np_val / equity_latest) * 100, 2) if equity_latest > 0 else None
        )
        metrics["ROA"] = round((np_val / ta_latest) * 100, 2) if ta_latest > 0 else None
    else:
        # Handle the missing FY case cleanly
        metrics["PER"] = None
        metrics["ROE"] = None
        metrics["ROA"] = None

    return metrics


def create_plots(
    pl_data: List[Dict[str, Any]],
    bs_data: List[Dict[str, Any]],
    cf_data: List[Dict[str, Any]],
) -> Dict[str, go.Figure]:
    """
    Generates a dictionary of Plotly figures for Profit/Loss, Balance Sheet, and Cash Flow data.

    This function processes raw dictionary lists into Pandas DataFrames, standardizes dates,
    and creates six specific financial analysis charts (Growth, Efficiency, Structure, Safety,
    Truth Check, and Strategy).

    Args:
        pl_data (List[Dict[str, Any]]): List of Profit & Loss records (requires 'Sales', 'OP', 'NP', 'CurPerEn').
        bs_data (List[Dict[str, Any]]): List of Balance Sheet records (requires 'Liabilities', 'Eq', 'CashEq', 'CurPerEn').
        cf_data (List[Dict[str, Any]]): List of Cash Flow records (requires 'CFO', 'CFI', 'CFF', 'CurPerEn').

    Returns:
        Dict[str, go.Figure]: A dictionary where keys are metric identifiers (e.g., 'pl_growth', 'bs_safety')
                              and values are the corresponding Plotly Figure objects ready for rendering.
                              Returns an empty dict if all inputs are empty.
    """
    if not pl_data and not bs_data and not cf_data:
        return {}

    # cash flow uses this
    pl_df = pd.DataFrame(pl_data)
    pl_df["CurPerEn"] = pd.to_datetime(pl_df["CurPerEn"])
    pl_df = pl_df.sort_values("CurPerEn")

    plot_metrics = {}
    if pl_data:
        fig1 = go.Figure()
        fig1.add_trace(
            go.Scatter(
                x=pl_df["CurPerEn"],
                y=pl_df["Sales"],
                mode="lines+markers",
                name="売上高(会社が商品やサービスを売って得たお金)",
            )
        )
        fig1.add_trace(
            go.Scatter(
                x=pl_df["CurPerEn"],
                y=pl_df["OP"],
                mode="lines+markers",
                name="営業利益(本業で稼いだ利益)",
            )
        )
        fig1.add_trace(
            go.Scatter(
                x=pl_df["CurPerEn"],
                y=pl_df["NP"],
                mode="lines+markers",
                name="純利益（当期純利益)",
            )
        )
        fig1.update_layout(title="成長性：売上高と利益の推移", hovermode="x unified")
        plot_metrics["pl_growth"] = fig1

        fig2 = make_subplots(specs=[[{"secondary_y": True}]])
        fig2.add_trace(
            go.Bar(
                x=pl_df["CurPerEn"],
                y=pl_df["Sales"],
                name="売上高(会社が商品やサービスを売って得たお金)",
                opacity=0.5,
            ),
            secondary_y=False,
        )
        # Check if Operating_Margin exists before plotting
        if "Operating_Margin" in pl_df.columns:
            fig2.add_trace(
                go.Scatter(
                    x=pl_df["CurPerEn"],
                    y=pl_df["Operating_Margin"],
                    mode="lines+markers",
                    name="営業利益率(高いほど効率的）",
                    line=dict(color="red", width=2),
                ),
                secondary_y=True,
            )
            fig2.update_yaxes(
                title_text="営業利益率", tickformat=".1%", secondary_y=True
            )

        fig2.update_layout(title="収益性：売上高と利益率の関係", hovermode="x unified")
        plot_metrics["pl_efficiency"] = fig2

    if bs_data:
        bs_df = pd.DataFrame(bs_data)
        bs_df["CurPerEn"] = pd.to_datetime(bs_df["CurPerEn"])
        bs_df = bs_df.sort_values("CurPerEn")

        fig3 = go.Figure()
        fig3.add_trace(
            go.Scatter(
                x=bs_df["CurPerEn"],
                y=bs_df["Liabilities"],
                mode="lines",
                stackgroup="one",
                name="負債",
                line=dict(width=0.5, color="#d62728"),
            )
        )
        fig3.add_trace(
            go.Scatter(
                x=bs_df["CurPerEn"],
                y=bs_df["Eq"],
                mode="lines",
                stackgroup="one",
                name="純資産（自己資本)",
                line=dict(width=0.5, color="#1f77b4"),
            )
        )
        fig3.update_layout(title="資本構成（資産の内訳)", hovermode="x unified")
        plot_metrics["bs_structure"] = fig3

        # 4. Fortress Check (Cash vs Liabilities)
        fig4 = go.Figure()
        fig4.add_trace(
            go.Bar(
                x=bs_df["CurPerEn"],
                y=bs_df["CashEq"],
                name="現金・現金同等物",
                marker_color="green",
            )
        )
        fig4.add_trace(
            go.Bar(
                x=bs_df["CurPerEn"],
                y=bs_df["Liabilities"],
                name="負債",
                marker_color="red",
            )
        )
        fig4.update_layout(
            title="安全性：現金と負債の比較", barmode="group", hovermode="x unified"
        )
        plot_metrics["bs_safety"] = fig4

    if cf_data:
        cf_df = pd.DataFrame(cf_data)
        cf_df["CurPerEn"] = pd.to_datetime(cf_df["CurPerEn"])
        cf_df = cf_df.sort_values("CurPerEn")

        fig5 = go.Figure()
        fig5.add_trace(
            go.Scatter(
                x=pl_df["CurPerEn"],
                y=pl_df["NP"],
                mode="lines+markers",
                name="純利益（会計上,最終的に残った利益)",
                line=dict(dash="dot", color="gray"),
            )
        )
        fig5.add_trace(
            go.Scatter(
                x=cf_df["CurPerEn"],
                y=cf_df["CFO"],
                mode="lines+markers",
                name="営業キャッシュフロー（実際の現金)",
                line=dict(width=3, color="blue"),
            )
        )

        if "Free_Cash_Flow" in cf_df.columns:
            fig5.add_trace(
                go.Scatter(
                    x=cf_df["CurPerEn"],
                    y=cf_df["Free_Cash_Flow"],
                    mode="lines",
                    name="自由にできる現金",
                    line=dict(width=2, color="#2ca02c", dash="dash"),  # Green dashed
                )
            )

        fig5.update_layout(
            title="実態確認：利益とキャッシュフローの比較", hovermode="x unified"
        )
        plot_metrics["cf_truth"] = fig5

        fig6 = make_subplots(specs=[[{"secondary_y": True}]])
        fig6.add_trace(
            go.Bar(
                x=cf_df["CurPerEn"],
                y=cf_df["CFO"],
                name="営業キャッシュフロー",
                marker_color="#1f77b4",
            )
        )
        fig6.add_trace(
            go.Bar(
                x=cf_df["CurPerEn"],
                y=cf_df["CFI"],
                name="投資キャッシュフロー",
                marker_color="#ff7f0e",
            )
        )
        fig6.add_trace(
            go.Bar(
                x=cf_df["CurPerEn"],
                y=cf_df["CFF"],
                name="財務キャッシュフロー",
                marker_color="#2ca02c",
            )
        )
        fig6.add_trace(
            go.Scatter(
                x=cf_df["CurPerEn"],
                y=cf_df["Free_Cash_Flow"],
                mode="lines+markers",
                name="自由にできる現金",
                line=dict(color="green", width=4),
            ),
            secondary_y=False,
        )

        fig6.update_layout(
            title="資金戦略とフリーキャッシュフロー創出力",
            barmode="group",
            hovermode="x unified",
        )
        plot_metrics["cf_strategy"] = fig6

    return plot_metrics


def format_data_for_prompt(
    data_list: List[Dict[str, Any]], columns_to_keep: List[str]
) -> str:
    """
    Formats a list of dictionaries into a clean, whitespace-separated string table
    suitable for passing to an LLM prompt.

    Handles date sorting and formatting automatically if 'CurPerEn' exists.

    Args:
        data_list (List[Dict[str, Any]]): A list of data records (e.g., from an API or DataFrame).
        columns_to_keep (List[str]): A list of column names to include in the output string.

    Returns:
        str: A string representation of the data table (CSV-like but space-aligned),
             or "No Data Available" if the input list is empty.
    """
    if not data_list:
        return "No Data Available"

    df = pd.DataFrame(data_list)

    # Filter for relevant columns only
    available_cols = [c for c in columns_to_keep if c in df.columns]

    # Sort by date if possible
    if "CurPerEn" in df.columns:
        df["CurPerEn"] = pd.to_datetime(df["CurPerEn"])
        df = df.sort_values("CurPerEn")
        # Format date to string YYYY-MM-DD
        df["CurPerEn"] = df["CurPerEn"].dt.strftime("%Y-%m-%d")
        available_cols = ["CurPerEn"] + [c for c in available_cols if c != "CurPerEn"]

    # Convert to string (CSV style is token-efficient)
    text_table = df[available_cols].to_string(index=False)
    return text_table


def gemini_analysis(
    industry: str,
    summary_record: Dict[str, Any],
    pl_data: List[Dict[str, Any]],
    bs_data: List[Dict[str, Any]],
    cf_data: List[Dict[str, Any]],
) -> dcc.Markdown:
    """
    Constructs a prompt with financial data, sends it to the Gemini API,
    and returns the analysis as a Dash Markdown component.

    Args:
        industry (str): The industry sector of the company (e.g., "Manufacturing").
        summary_record (Dict[str, Any]): A dictionary of key metrics (PER, PBR, ROE, etc.).
        pl_data (List[Dict[str, Any]]): Historical Profit & Loss data records.
        bs_data (List[Dict[str, Any]]): Historical Balance Sheet data records.
        cf_data (List[Dict[str, Any]]): Historical Cash Flow data records.

    Returns:
        dcc.Markdown: A Dash component containing the formatted AI analysis
                      or an error message if the API call fails.
    """
    if not summary_record and not pl_data and not bs_data and not cf_data:
        return dcc.Markdown("No Data")

    if not GEMINI_API:
        return dcc.Markdown("No Gemini API Key. No Gemini Analysis Applied")

    pl_text = format_data_for_prompt(
        pl_data,
        ["Sales", "OP", "OdP", "NP", "EPS", "DEPS", "Operating_Margin", "DocType"],
    )
    bs_text = format_data_for_prompt(
        bs_data, ["TA", "Eq", "CashEq", "EqAR", "BPS", "Liabilities", "Equity_Ratio"]
    )
    cf_text = format_data_for_prompt(cf_data, ["CFO", "CFI", "CFF", "Free_Cash_Flow"])

    prompt = f"""
    You are a professional financial analyst for the Japanese stock market.
    Analyze the following financial data for this company(Industry: {industry}).

    ### 1. Profit & Loss Data (Trends)
    {pl_text}

    ### 2. Balance Sheet Data (Safety)
    {bs_text}

    ### 3. Cash Flow Data (Reality)
    {cf_text}

    ### 4. (Current Stock) Price, EquityRatio, PER, PBR, ROE, ROA
    {summary_record}

    ### Instructions:
    Please provide a concise analysis in markdown format with the following sections in Japanese:
    1.  **Growth Verdict:** Is the company growing? Are margins improving?
    2.  **Safety Check:** Is the company financially stable (Cash vs Assets)?
    3.  **Cash Flow Reality:** Is the accounting profit backed by real operating cash flow? (Compare NP and CFO).
    4.  **Metric Evaluation:** Are EquityRatio, PER, PBR, ROE, and ROA healthy?
    5.  **Red Flags/Green Flags:** Any specific positive or negative signs?
    6.  **Summary:** One sentence summary of the investment quality.

    *Keep it objective and professional. Do not give financial advice, just analysis.*
    """

    try:
        client = genai.Client(api_key=GEMINI_API)
        response = client.models.generate_content(
            model="gemini-3-flash-preview", contents=prompt
        )
        ai_text = response.text

        client.close()
        # return the Markdown component directly
        return dcc.Markdown(ai_text, style={"lineHeight": "1.6"})

    except Exception as e:
        return dcc.Markdown(f"**AI Analysis Failed:** {str(e)}")
