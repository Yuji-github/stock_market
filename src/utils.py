import pandas as pd
import yfinance as yf
from dotenv import load_dotenv
import os 
import requests
from typing import Tuple, Dict, List, Any, Optional
import logging
import time 


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
            return None # Company is not listed or code is missing
        
        # Clean the input to a string
        code_str = str(code_val).strip()
        
        # Handle cases where pandas reads integers as floats (e.g., '13760.0')
        if code_str.endswith('.0'):
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
            '/workspace/src/edinet_company_list/EdinetcodeDlInfo.csv', 
            encoding='cp932', 
            skiprows=1
        )
        
        if '証券コード' not in df.columns:
            print("Error: Column '証券コード' not found in input CSV.")
            return

        # Apply the conversion logic
        df['yfinance_ticker'] = df['証券コード'].apply(convert_to_ticker)   
        
        # Save to Parquet
        df.to_parquet(
            '/workspace/src/edinet_company_list/company_list.parquet', 
            index=False
        )
        logging.info("Successfully created company_list.parquet")

    except FileNotFoundError:
        logging.error("Error: Input file '/workspace/src/edinet_company_list/EdinetcodeDlInfo.csv' not found.")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")

    
def get_pl_bs_cashflow(code: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
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
    pl_cols = ['Code', 'CurPerEn', 'Sales', 'OP', 'OdP', 'NP', 'EPS', 'DEPS']
    bl_cols = ['Code', 'CurPerEn', 'TA', 'Eq', 'EqAR', 'BPS']
    cf_cols = ['Code', 'CurPerEn', 'CFO', 'CFI', 'CFF', 'CashEq']

    headers = {"x-api-key": JQUANTS_API}
    params = {"code": code}
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            res = requests.get(f"{API_URL}/fins/summary", params=params, headers=headers)
            
            if res.status_code == 200:
                d = res.json()
                data = d.get("data", [])
                
                # Handle Pagination
                while "pagination_key" in d:
                    params["pagination_key"] = d["pagination_key"]
                    res = requests.get(f"{API_URL}/fins/summary", params=params, headers=headers)
                    if res.status_code != 200:
                        break
                    d = res.json()
                    data += d.get("data", [])
                
                df = pd.DataFrame(data)
                
                if df.empty:
                    return [], [], []

                # Filter for Consolidated IFRS/JP GAAP if needed. 
                fy_df = df[df["DocType"] == "FYFinancialStatements_Consolidated_IFRS"]
                
                # If filtering resulted in empty data, return empty lists
                if fy_df.empty:
                    return [], [], []

                pl_df = fy_df[pl_cols]
                bs_df = fy_df[bl_cols]
                cf_df = fy_df[cf_cols]
                
                # Convert to List[Dict] for Dash/JSON compatibility
                # Example: [{'Sales': 100, 'OP': 10}, ...]
                return pl_df.to_dict('records'), bs_df.to_dict('records'), cf_df.to_dict('records')
            
            else:
                logging.error(f"J-Quants API Error: {res.status_code}")
                logging.info(f"Retry in 5 secconds: {attempt+1} / 5")
                time.sleep(5)
                
        except Exception as e:
            logging.error(f"Error fetching data: {e}")
            logging.info(f"Retry in 5 secconds: {attempt+1} / 5")
            time.sleep(5)

    return [], [], []

def calculate_valuation_metrics(
    yf_code: str, 
    pl_data: List[Dict[str, Any]], 
    bs_data: List[Dict[str, Any]]
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
    # 1. Validation:
    if not yf_code or not pl_data or not bs_data:
        return {}
    
    # 2. Re-create DataFrames for easy sorting and type conversion
    try:
        pl_df = pd.DataFrame(pl_data)
        bs_df = pd.DataFrame(bs_data)
        
        # Ensure 'CurPerEn' is available for sorting
        if 'CurPerEn' not in pl_df.columns or 'CurPerEn' not in bs_df.columns:
            return {}

        # Get the latest financial record
        latest_pl = pl_df.sort_values('CurPerEn').iloc[-1]
        latest_bs = bs_df.sort_values('CurPerEn').iloc[-1]

        # Extract values and ensure they are floats (API often returns strings)
        eps = float(latest_pl.get('EPS', 0))
        np_val = float(latest_pl.get('NP', 0))
        
        bps = float(latest_bs.get('BPS', 0))
        equity = float(latest_bs.get('Eq', 0))
        total_assets = float(latest_bs.get('TA', 0))

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
                logging.info(f"Retry in 5 secconds: {attempt+1} / 5")
                time.sleep(5) 
            
            current_price = hist['Close'].iloc[-1]
            
        except Exception as e:
            logging.error(f"yfinance error: {e}")
            logging.info(f"Retry in 5 secconds: {attempt+1} / 5")
            time.sleep(5)
        
        if not hist.empty:
            break 
    
    # Failed to get data
    if hist.empty:
        return {}

    # 4. Calculate Metrics
    metrics = {
        "Code": yf_code.split('.')[0],  #  "Japan Code" (remove .T)
        "Price": round(current_price, 2),
        "PER": round(current_price / eps, 2) if eps != 0 else None,
        "PBR": round(current_price / bps, 2) if bps != 0 else None,
        "ROE": round((np_val / equity) * 100, 2) if equity != 0 else None,
        "ROA": round((np_val / total_assets) * 100, 2) if total_assets != 0 else None
    }

    return metrics


# def gemini_analysis(summary_record: dict, detailed_data:dict) -> Dict[str]:
#     if not summary_record or not detailed_data:
#         return {}
    
#     gemini_mock_text = f"""
#     ### AI Analysis
#     **Selected Companies:** {", ".join(selected_companies)}
    
#     **Observation:**
#     Based on the PER and ROE metrics, {summary_df.iloc[0]['Name'] if not summary_df.empty else 'the company'} appears to be leading in efficiency.
    
#     **Recommendation:**
#     Consider investigating the debt-to-equity ratio in the detailed Balance Sheet (BS) data before making a decision.
#     """

#     return {}