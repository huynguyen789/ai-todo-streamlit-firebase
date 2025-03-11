# AI Todo List with Google Sheets

## Project Architecture
```ascii
+------------------+     +------------------+     +------------------+
|   Streamlit UI   | --> | Python Backend   | --> |  Google Sheets   |
| - Todo List View |     | - CRUD Logic     |     | - Data Storage   |
| - Add/Edit/Del   |     | - Sheet API      |     | - Persistence    |
+------------------+     +------------------+     +------------------+
```

## Core Components
1. Frontend (Streamlit)
   - Todo list display
   - Add new todo form
   - Edit/Delete functionality
   - Status updates

2. Backend (Python)
   - Google Sheets integration
   - Data manipulation logic
   - Cache management

3. Database (Google Sheets)
   - Schema: id, task, status, created_at, updated_at
   - Single worksheet design for simplicity

## Design Decisions
1. Using Google Sheets as DB for:
   - Simple setup
   - Easy visualization
   - No complex DB management
   - Real-time collaboration

2. Caching Strategy:
   - 10 min TTL to balance freshness and performance
   - Manual refresh option available

## Known Issues/Limitations
- Sheet operations may be slower than traditional DB
- Limited concurrent user support
- Basic CRUD operations only

## Future Improvements
- Add due dates
- Priority levels
- Categories/Tags
- Multi-user support 