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
            id="loading-spinner", type="default", children=html.Div(id="login-alert")
        ),
    ],
)


@app.callback(
    [
        Output("login-container", "style"),
        Output("dashboard-container", "style"),
        Output("login-alert", "children"),
    ],
    [Input("login-button", "n_clicks"), Input("password-input", "n_submit")],
    [State("password-input", "value")],
    prevent_initial_call=True,
)
def verify_password(n_clicks, n_submit, password):
    if not password:
        return no_update, no_update, "Please enter a password."

    if password == CORRECT_PASSWORD:
        # Success: Hide Login, Show Dashboard
        return {"display": "none"}, {"display": "block"}, ""
    else:
        time.sleep(3)  # to avoid million attack from hackers
        # Fail: Keep Login, Ensure Dashboard hidden, Show Error
        return {}, {"display": "none"}, "Incorrect Password. Please wait..."
