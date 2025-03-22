# API Server Architecture

The API server provides a RESTful interface for accessing the structured disclosure data stored in the SQLite database. It serves as the bridge between the database and the frontend visualization application.

## Technology Stack

- **Flask**: Lightweight web framework for Python
- **Flask-CORS**: Extension for handling Cross-Origin Resource Sharing
- **SQLite**: Database engine

## Core Architecture

The API server is implemented as a Flask application in `api/app.py`. It follows a straightforward architecture:

1. **Route Handlers**: Define API endpoints and their functionality
2. **Database Connection**: Connect to SQLite database and execute queries
3. **Response Formatting**: Format query results as JSON responses

## Request/Response Flow

```
+----------------+            +----------------+            +----------------+
| HTTP Request   |            | Flask Route    |            | SQLite Query   |
| (Frontend)     | ---------> | Handler        | ---------> | Execution      |
+----------------+            +----------------+            +----------------+
                                                                    |
                                                                    v
+----------------+            +----------------+            +----------------+
| HTTP Response  |            | JSON Response  |            | Query Results  |
| (To Frontend)  | <--------- | Formatting     | <--------- | Processing     |
+----------------+            +----------------+            +----------------+
```

## Key Components

### Route Handlers

The API defines several route handlers for different data access patterns:

**Main Endpoints:**
- `/api/disclosures`: Get disclosures with filtering options
- `/api/stats`: Get statistics about disclosures, MPs, and entities
- `/api/mps`: Get list of MPs with filtering options
- `/api/entities`: Get list of entities mentioned in disclosures
- `/api/network`: Get network data for entity explorer
- `/api/mp/<name>`: Get details for a specific MP

**Utility Endpoints:**
- `/api/pdf/<filename>`: Serve PDF files
- `/api/pdf-info/<mp_name>`: Get PDF info for an MP

### Database Connection

The API server connects to the SQLite database using the `get_db_connection()` function:

```python
def get_db_connection():
    """Create a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
```

### Response Formatting

Query results are converted to JSON format using Flask's `jsonify()` function:

```python
result = [dict(row) for row in query_results]
return jsonify(result)
```

## Authentication & Security

The current implementation does not include authentication. For production use, consider implementing:

- API key authentication
- Rate limiting
- Input validation

## Error Handling

The API server includes basic error handling for common scenarios:

- Invalid query parameters
- Database connection errors
- Resource not found

Error responses follow a standard format:

```json
{
  "error": "Error message",
  "status": 400
}
```

## Configuration

The API server is configured through environment variables:

- `DB_PATH`: Path to the SQLite database file
- `PDF_DIR`: Path to the directory containing PDF files
- `PORT`: Port number for the API server (default: 3001)
- `DEBUG`: Enable debug mode (default: false)

These can be set in a `.env` file in the `api/` directory.

## Deployment

The API server can be deployed as a standalone Flask application or behind a production-grade WSGI server like Gunicorn.

**Development:**
```bash
cd api
python app.py
```

**Production:**
```bash
cd api
gunicorn --bind 0.0.0.0:3001 app:app
```

## Next Steps

- [API Endpoints Reference](../api/endpoints.md)
- [API Data Models](../api/data_models.md) 