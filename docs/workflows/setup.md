# Setup and Installation Guide

This guide will walk you through the process of setting up the Australian Government Transparency Project for local development.

## Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3.9+**: Required for the backend and data processing scripts
- **Node.js 18+**: Required for the frontend
- **npm or yarn**: Package manager for Node.js
- **Git**: Version control system

## Environment Setup

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/aus-govt-transparency.git
cd aus-govt-transparency
```

### 2. Set Up Python Environment

It's recommended to use a virtual environment to manage Python dependencies:

```bash
# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a `.env.local` file in the project root for backend configuration:

```bash
cp .env.example .env.local
```

Open `.env.local` in a text editor and add your Google API key:

```
GOOGLE_API_KEY=your_google_api_key_here
```

### 4. Set Up API Server

Create a `.env` file in the `api/` directory:

```bash
cp api/.env.example api/.env
```

Open `api/.env` in a text editor and configure as needed:

```
DB_PATH=/path/to/disclosures.db
PORT=3001
DEBUG=True
```

### 5. Set Up Frontend

```bash
# Navigate to the frontend directory
cd aus-govt-transparency-viz/frontend

# Install dependencies
npm install

# Create .env file
cp .env.example .env
```

Open `.env` in a text editor and configure as needed:

```
VITE_API_URL=http://localhost:3001/api
```

## Database Setup

### 1. Initialize the Database

The system will automatically create a new SQLite database file if one doesn't exist:

```bash
# From the project root directory
python reset_db.py
```

### 2. Download and Process Sample Data (Optional)

To download and process a sample of parliamentary disclosures:

```bash
# Download PDFs from the latest parliament
python scrape_parliament.py --limit 5

# Process the downloaded PDFs and store in database
python process_parliament_disclosures.py --store-in-db --limit 5
```

## Running the Application

### 1. Start the API Server

```bash
# From the project root directory
cd api
python app.py
```

The API server will start at `http://localhost:3001`.

### 2. Start the Frontend Development Server

```bash
# From the project root directory
cd aus-govt-transparency-viz/frontend
npm run dev
```

The frontend development server will start at `http://localhost:5173`.

## Verifying Installation

To verify that everything is working correctly:

1. Open your browser and navigate to `http://localhost:5173`
2. You should see the home page of the application
3. Check the API is working by visiting `http://localhost:3001/api/stats`

## Common Issues and Solutions

### Google API Key Issues

If you encounter errors related to the Google API:

1. Verify your API key is correct in `.env.local`
2. Ensure the Gemini API is enabled for your Google Cloud project
3. Check if you've hit rate limits (15 requests per minute, 1,500 requests per day)

### Database Connection Issues

If the API can't connect to the database:

1. Check the `DB_PATH` in `api/.env`
2. Ensure the database file exists and has proper permissions
3. Try running `python reset_db.py` to initialize the database

### Frontend API Connection Issues

If the frontend can't connect to the API:

1. Verify the API server is running
2. Check that `VITE_API_URL` in the frontend `.env` file is correct
3. Ensure CORS is properly configured in the API server

## Next Steps

Once the system is set up, you can:

1. **Download more data**: Modify the limits or remove them in the scraping and processing scripts
2. **Run standardization**: Execute `python standardize_data.py` to clean the data
3. **Run recategorization**: Execute `python recategorize_all.py` to improve categorization

Continue to the [Development Workflow](./development.md) guide for information on how to contribute to the project.

## Advanced Configuration

### Processing Multiple Parliaments

To process disclosures from multiple parliaments:

```bash
# Download PDFs from all parliaments
python scrape_parliament.py --all

# Process all downloaded PDFs
python process_parliament_disclosures.py --all --store-in-db
```

### Configuring Rate Limits

To adjust rate limits for the Gemini API:

```bash
python process_parliament_disclosures.py --rpm 10 --rpd 1400
```

### Database Backup

It's a good practice to create database backups before running major operations:

```bash
# Create a backup
python -c "from db_handler import DatabaseHandler; db = DatabaseHandler('disclosures.db'); db.create_backup('disclosures_backup.db')"
```

### Running with Docker (Optional)

If you prefer using Docker, you can use the following setup (Note: Docker configuration files are not included by default):

Create a `Dockerfile` for the API server:

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 3001

CMD ["python", "api/app.py"]
```

Create a `docker-compose.yml` file:

```yaml
version: '3'

services:
  api:
    build: .
    ports:
      - "3001:3001"
    volumes:
      - ./disclosures.db:/app/disclosures.db
    env_file:
      - .env.local
      - api/.env

  frontend:
    build:
      context: ./aus-govt-transparency-viz/frontend
    ports:
      - "5173:5173"
    depends_on:
      - api
```

Build and run with Docker Compose:

```bash
docker-compose up -d
``` 