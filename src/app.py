import dash
from dash import dcc, html, Input, Output, State, no_update
import time
from dotenv import load_dotenv
import os 


# 1. Setup the App
load_dotenv()  # Load environment variables
app = dash.Dash(__name__)

# 2. Define the correct password
CORRECT_PASSWORD = os.environ.get("DASH_PASSWORD")
if not CORRECT_PASSWORD:
    print("WARNING: No DASH_PASSWORD set. Login will fail.")
    exit()

# 3. Define the Layout
app.layout = html.Div([
    
    # --- SECTION A: LOGIN SCREEN ---
    html.Div(id='login-container', style={'textAlign': 'center', 'marginTop': '100px'}, children=[
        html.H2("Restricted Access"),
        html.P("Please enter the password to view the dashboard."),
        
        # Password Input
        dcc.Input(
            id='password-input',
            type='password',
            placeholder='Enter Password',
            n_submit=0,  # Allows hitting "Enter" to submit
            style={'padding': '10px', 'fontSize': '16px'}
        ),
        
        html.Br(), html.Br(),
        
        # Submit Button
        html.Button('Login', id='login-button', n_clicks=0, style={'fontSize': '16px', 'padding': '5px 15px'}),
        
        html.Br(), html.Br(),
        
        # Loading Component (shows spinner during the 3s penalty)
        dcc.Loading(
            id="loading-spinner",
            type="default",
            children=html.Div(id='login-alert', style={'color': 'red', 'fontWeight': 'bold'})
        )
    ]),

    # --- SECTION B: THE DASHBOARD (Initially Hidden) ---
    html.Div(id='dashboard-container', style={'display': 'none'}, children=[
        html.Div([
            html.H1("Welcome to the Dashboard"),
            html.Hr(),
            html.P("Here is your secure data."),
            # Example Graph
            dcc.Graph(
                id='example-graph',
                figure={
                    'data': [{'x': [1, 2, 3], 'y': [4, 1, 2], 'type': 'bar', 'name': 'SF'}],
                    'layout': {'title': 'Secure Data Visualization'}
                }
            )
        ], style={'padding': '50px'})
    ])
])

# 4. The Callback logic
@app.callback(
    [Output('login-container', 'style'),      # Controls visibility of Login
     Output('dashboard-container', 'style'),  # Controls visibility of Dashboard
     Output('login-alert', 'children')],      # Controls error message
    [Input('login-button', 'n_clicks'),
     Input('password-input', 'n_submit')],    # Listens to Button OR Enter key
    [State('password-input', 'value')],       # Reads the password box
    prevent_initial_call=True
)
def verify_password(n_clicks, n_submit, password):
    # Check if input is empty
    if not password:
        return no_update, no_update, "Please enter a password."

    # Verify Password
    if password == CORRECT_PASSWORD:
        # SUCCESS: Hide login, Show dashboard, Clear errors
        return {'display': 'none'}, {'display': 'block'}, ""
    else:
        # FAILURE: Artificial Delay
        time.sleep(3) 
        # Keep login visible, Keep dashboard hidden, Show error
        return {'display': 'block'}, {'display': 'none'}, "Incorrect Password. Please wait..."

# 5. Run the App
if __name__ == '__main__':
    app.run(debug=True, port=8050)