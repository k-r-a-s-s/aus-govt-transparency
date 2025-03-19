# Australian Government Transparency Dashboard Backend

This is the backend API for the Australian Government Transparency Dashboard, which provides access to parliamentary financial disclosure data.

## Tech Stack

- **Node.js**: Runtime environment
- **Express**: Web framework
- **TypeScript**: Programming language
- **SQLite**: Database
- **Vitest**: Testing framework

## API Endpoints

### Disclosures

- `GET /api/disclosures`: Get disclosures with filtering options
  - Query parameters:
    - `mp_name`: Filter by MP name
    - `party`: Filter by political party
    - `electorate`: Filter by electorate
    - `category`: Filter by category (Asset, Gift, etc.)
    - `entity`: Filter by entity name (fuzzy search)
    - `start_date`: Filter by declaration date (ISO-8601)
    - `end_date`: Filter by declaration date (ISO-8601)
    - `limit`: Maximum number of results (default: 100)
    - `offset`: Pagination offset (default: 0)

- `GET /api/disclosures/stats`: Get statistics about the disclosure data
  - Returns counts by category, party, year, etc.

## Setup

1. Install dependencies:

```bash
npm install
```

2. Set up environment variables:

Create a `.env` file with the following variables:

```
PORT=3001
NODE_ENV=development
DB_PATH=/path/to/disclosures.db
```

3. Start the server:

```bash
# Development mode
npm run dev

# Production mode
npm run build
npm start
```

## Development

The application is structured as follows:

- `src/index.ts`: Main entry point
- `src/routes/`: API route definitions
- `src/controllers/`: Request handlers
- `src/models/`: Database access
- `src/types/`: TypeScript type definitions
- `src/middleware/`: Express middleware
- `src/config/`: Configuration

## Testing

Run tests with:

```bash
npm test
``` 