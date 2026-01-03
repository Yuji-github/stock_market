from dash import html, dcc, callback, Input, Output, State, dash_table
import pandas as pd
from utils import get_pl_bs_cashflow, calculate_valuation_metrics
import plotly.express as px


df = pd.read_parquet('/workspace/src/edinet_company_list/company_list.parquet')
df.dropna(subset=['証券コード'], inplace=True)
data = {
    "industry": df["提出者業種"].to_list(),
    "company_name": df["提出者名"].to_list(),
    'code': df['証券コード'].to_list(),  # e.g., 72030
    'yfinance_ticker': df['yfinance_ticker'].to_list()  # e.g., 7203.T
}
df = pd.DataFrame(data)
industry_options = sorted(df['industry'].unique())


dashboard_layout = html.Div([
    html.H1("Company Analysis Dashboard"),
    html.Hr(),

    html.Div([
        html.Label("1. Select Industry Type(s):"),
        dcc.Dropdown(
            id='type-selector',
            options=[{'label': i, 'value': i} for i in industry_options],
            multi=True,
            placeholder="Select type..."
        ),
    ], style={'width': '45%', 'display': 'inline-block'}),

    html.Div([
        html.Label("2. Select Company Name(s):"),
        dcc.Dropdown(
            id='company-selector',
            options=[], # Empty initially, populated by callback
            multi=True,
            placeholder="Select companies..."
        ),
    ], style={'width': '45%', 'display': 'inline-block', 'marginLeft': '20px'}),

    html.Br(), html.Br(),
    
    html.Button('Search Data', id='search-btn', n_clicks=0, style={'fontSize': '16px'}),

    html.Hr(),

    # Area to display charts/tables later
    html.Div(id='dashboard-content')
])


@callback(
    Output('company-selector', 'options'),
    Input('type-selector', 'value')
)
def set_company_options(selected_types):
    if not selected_types:
        # If nothing selected, you can either return [] or all companies.
        return []
    
    # Filter the dataframe based on selected types
    filtered_df = df[df['industry'].isin(selected_types)]
    
    # Get unique companies from the filtered data
    companies = sorted(filtered_df['company_name'].unique())
    
    return [{'label': c, 'value': c} for c in companies]


@callback(
    Output('dashboard-content', 'children'),
    Input('search-btn', 'n_clicks'),
    State('type-selector', 'value'),
    State('company-selector', 'value'),
    prevent_initial_call=True
)
def execute_search(n_clicks, selected_types, selected_companies):
    if n_clicks is None or n_clicks == 0:
        return ""
        
    if not selected_types and not selected_companies:
        return "Please make a selection and click Search."

    selected_comapnies_df = df[df['company_name'].isin(selected_companies)]
    summary_list = []  # For the main table (Flat data)
    detailed_data = {} # For plotting charts (Complex data)
    
    for _, row in selected_comapnies_df.iterrows():
        ticker = row['yfinance_ticker']
        name = row['company_name']
        
        # Clean ticker for API
        clean_ticker = ticker.split('.')[0]

        pl_data, bs_data, cf_data = get_pl_bs_cashflow(clean_ticker)
        finance_result = {}
        if pl_data and bs_data:
            finance_result = calculate_valuation_metrics(ticker, pl_data, bs_data)
        
        summary_record = {
        'Company Name': name,
        'Code': finance_result.get('Code', 0),
        'Price': finance_result.get('Price', 0), 
        'PER': finance_result.get('PER', 0),
        'PBR': finance_result.get('PBR', 0),
        'ROE': finance_result.get('ROE', 0),
        'ROA': finance_result.get('ROA', 0)
        }   
        summary_list.append(summary_record)

        detailed_data[clean_ticker] = {
        'PL': pl_data if pl_data is not None else [],
        'BS': bs_data if bs_data is not None else [],
        'CF': cf_data if cf_data is not None else []
        }
        
    summary_df = pd.DataFrame(summary_list)
    if summary_df.empty:
        return html.Div("No data found.", style={'padding': '20px'})
    
    data_table = dash_table.DataTable(
        data=summary_df.to_dict('records'),
        columns=[{"name": i, "id": i} for i in summary_df.columns],
        style_table={'overflowX': 'auto'},
        style_cell={'textAlign': 'left', 'padding': '5px', 'fontSize': '12px'},
        style_header={'backgroundColor': 'lightgrey', 'fontWeight': 'bold'},
        page_size=10
    )

    # all_pl_data = []
    # for t, data in detailed_data.items():
    #     all_pl_data.append(data)
    
    # if all_pl_data:
    #     combined_pl = pd.concat(all_pl_data)
    #     # Note: Replace 'date' and 'totalRevenue' with your ACTUAL column names from yfinance/API
    #     # We perform a check to ensure columns exist before plotting
    #     x_col = 'date' if 'date' in combined_pl.columns else combined_pl.columns[0]
    #     y_col = 'totalRevenue' if 'totalRevenue' in combined_pl.columns else combined_pl.columns[1]
        
    #     fig = px.bar(
    #         combined_pl, 
    #         x=x_col, 
    #         y=y_col, 
    #         color='Ticker', 
    #         title="Revenue Composition",
    #         template="plotly_white"
    #     )
    #     fig.update_layout(legend=dict(orientation="h", y=-0.2)) # Move legend to bottom
    # else:
    #     fig = {} # Empty chart if no data

    # graph_component = dcc.Graph(figure=fig, style={'height': '400px'})

    # gemini_mock_text = f"""
    # ### AI Analysis
    # **Selected Companies:** {", ".join(selected_companies)}
    
    # **Observation:**
    # Based on the PER and ROE metrics, {summary_df.iloc[0]['Name'] if not summary_df.empty else 'the company'} appears to be leading in efficiency.
    
    # **Recommendation:**
    # Consider investigating the debt-to-equity ratio in the detailed Balance Sheet (BS) data before making a decision.
    # """

    # --- 5. FINAL LAYOUT (The 3 Columns) ---
    return html.Div([
        
        html.H3("Search Results"),
        
        html.Div([
            # Column 1: Table
            html.Div([
                html.H5("Summary Metrics"),
                data_table
            ], style={'width': '32%', 'display': 'inline-block', 'verticalAlign': 'top', 'paddingRight': '1%'}),

            # Column 2: Plot
            # html.Div([
            #     html.H5("Revenue Trend"),
            #     graph_component
            # ], style={'width': '34%', 'display': 'inline-block', 'verticalAlign': 'top', 'paddingRight': '1%'}),

            # # Column 3: Analysis
            # html.Div([
            #     html.H5("Gemini Insight"),
            #     html.Div(dcc.Markdown(gemini_mock_text), 
            #              style={'backgroundColor': '#f4f6f8', 'padding': '15px', 'borderRadius': '5px'})
            # ], style={'width': '32%', 'display': 'inline-block', 'verticalAlign': 'top'})
            
        ], style={'display': 'flex', 'flexDirection': 'row', 'marginTop': '20px'})
    ])