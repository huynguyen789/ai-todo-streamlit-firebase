# Google Sheets Streamlit Demo

A simple Streamlit application that demonstrates connection to Google Sheets.

## Setup

1. Create and activate virtual environment:
```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment (Mac/Linux)
source .venv/bin/activate

# Activate virtual environment (Windows)
.venv\Scripts\activate
```

2. Install uv package manager:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env  # Add uv to PATH
```

3. Install dependencies using uv:
```bash
uv pip install -r requirements.txt
```

4. Make sure your Google Sheet is shared with the service account email:
```
ai-todo-list@sample-firebase-ai-app-f63fd.iam.gserviceaccount.com
```

5. Run the Streamlit app:
```bash
streamlit run app.py
```

## Features

- Connects to Google Sheets using service account authentication
- Displays sheet data in a Streamlit dataframe
- Shows basic statistics about the data
- Handles errors gracefully

## Configuration

The app uses Streamlit's secrets management to store:
- Google Sheets credentials
- Spreadsheet URL

These are stored in `.streamlit/secrets.toml` (not committed to version control) 