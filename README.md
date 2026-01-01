# General
```
my-aws-project/
├── .devcontainer/              # VS Code Dev Container Config
│   ├── devcontainer.json       # VS Code settings & extensions
│   ├── docker-compose.yml      # Orchestrates the dev environment
│   └── Dockerfile.dev          # Dev-specific image (heavy, with tools)
├── src/                        # Source Code
│   ├── main.py                 # Entry point
│   └── __init__.py
├── .dockerignore               # Filters files for the Production build
├── .env                        # Local secrets (DO NOT COMMIT)
├── .gitignore                  # Standard git exclusions
├── Dockerfile                  # PRODUCTION Image (Multi-stage, Lean)
├── pyproject.toml              # Poetry Dependencies: poetry creates this automatically 
├── poetry.lock                 # Version lock file: poetry creates this automatically 
└── README.md
```

# Poetry Set up
## Initialize the Project
(If you haven't already done poetry init)

In your VS Code terminal (which is now inside Linux), run:
```Bash
poetry init -n
```
The -n flag accepts all default answers (Project name, description, etc.) to save time.

This creates a pyproject.toml file.

## Install a Library
```Bash
poetry add requests
```
This creates a poetry.lock file automatically.

# Python Debug Set
## Select the Correct Python Interpreter
VS Code needs to know where your requests library lives.
Open src/main.py.

Look at the bottom-right corner of the VS Code window. It probably says 3.11.x 64-bit.

Click that version number (or press Ctrl+Shift+P and type "Python: Select Interpreter").

Look for an option that mentions "Poetry" or ".venv".

If you don't see it: Run poetry env info --path in your terminal. Copy that path, select "Enter interpreter path..." in the menu, and paste it.

Select it.

## Create a Debug Configuration
This saves your settings so you can just press F5 later.

Click the Run and Debug icon on the left sidebar (the play button with a bug).

Click "create a launch.json file".

Select Python Debugger.

Select Python File.

It will create a .vscode/launch.json file. It should look like this (default is usually fine):
```Json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: Current File",
            "type": "debugpy",
            "request": "launch",
            "program": "${file}",
            "console": "integratedTerminal",
            "justMyCode": true
        }
    ]
}
```