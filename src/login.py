import time
from dash import html, dcc, Input, Output, State, no_update
from app import app
from dotenv import load_dotenv
import os
import logging


# Configuration
load_dotenv()  # Load environment variables
CORRECT_PASSWORD = os.environ.get("DASH_PASSWORD")
if not CORRECT_PASSWORD:
    logging.error("ERROR: No DASH_PASSWORD set. Login will fail.")
    exit()


layout = html.Div(
    id="login-container",
    children=[
        html.H2("Restricted Access"),
        html.P("Please enter the password to view the dashboard."),
        dcc.Input(
            id="password-input",
            type="password",
            placeholder="Enter Password",
            n_submit=0,
        ),
        html.Button("Login", id="login-button", n_clicks=0),
        dcc.Loading(
            id="loading-spinner", 
            type="default", 
            children=html.Div(id="login-alert", style={"color": "red", "marginTop": "10px"})
        ),
    ],
    style={"textAlign": "center", "marginTop": "100px"} 
)


@app.callback(
    [
        Output("url", "pathname"),         # Target 1: The URL component in main.py
        Output("login-alert", "children"), # Target 2: The error message
    ],
    [
        Input("login-button", "n_clicks"), 
        Input("password-input", "n_submit")
    ],
    [State("password-input", "value")],
    prevent_initial_call=True,
)
def verify_password(n_clicks, n_submit, password):
    # Check if triggered by actual user interaction
    if not password:
        return no_update, "Please enter a password."

    if password == CORRECT_PASSWORD:
        # SUCCESS:
        # Change the URL to '/dashboard'. 
        # The callback in main.py will detect this and swap the layout.
        return "/dashboard", ""
    else:
        # FAILURE:
        time.sleep(2)  # Delay to slow down brute-force attacks
        # Do NOT update the URL (no_update), just show the error.
        return no_update, "Incorrect Password. Please try again."
