# Todo List App with Streamlit and Firestore

A simple, elegant todo list application built with Streamlit and Firebase Firestore.

## Features

- Create, read, update, and delete todo items
- Assign priority levels (High, Medium-High, Medium, Low)
- Mark tasks as completed
- Visual indicators for priority levels
- Statistics dashboard with progress tracking
- Responsive card-based UI

## Setup Instructions

### Prerequisites

- Python 3.8 or higher
- Firebase project with Firestore database

### Step 1: Clone the repository

```bash
git clone <repository-url>
cd ai-todo-streamlit-gsheet
```

### Step 2: Set up Firebase

1. Create a Firebase project at [Firebase Console](https://console.firebase.google.com/)
2. Set up a Firestore database in your project
3. Generate a service account key:
   - Go to Project Settings > Service Accounts
   - Click "Generate New Private Key"
   - Save the JSON file as `firebase.json` in the `data` directory

### Step 3: Install dependencies

```bash
pip install -r requirements.txt
```

Or with uv:

```bash
uv pip install -r requirements.txt
```

### Step 4: Run the application

```bash
streamlit run app.py
```

## Project Structure

- `app.py`: Main application file with Streamlit UI and Firestore logic
- `data/firebase.json`: Firebase service account credentials
- `document.md`: Project documentation and architecture
- `requirements.txt`: Python dependencies

## How It Works

The application uses:
- Streamlit for the user interface
- Firebase Admin SDK to connect to Firestore
- Firestore for storing todo items
- Caching to improve performance

See `document.md` for detailed architecture and design decisions.

## License

MIT 