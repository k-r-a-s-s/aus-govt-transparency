# Australian Government Transparency Project

This project aims to improve transparency in Australian politics by collecting, processing, and visualizing parliamentary disclosure data. Members of Parliament (MPs) are required to disclose their financial interests, gifts, and other potential conflicts of interest, and this project makes that information more accessible and understandable to the public.

## Project Structure

The project is divided into two main components:

1. **Backend**: Data processing scripts and API server
   - Located in the root directory
   - Python-based data scraping, processing and API serving
   - SQLite database for storage

2. **Frontend**: Visualization and data exploration interface
   - Located in the `frontend` directory
   - React-based web application
   - Interactive data visualizations

## Backend Features

- **PDF Scraping**: Automated extraction of disclosure data from parliamentary PDFs
- **Data Processing**: Cleaning, standardization, and structuring of disclosure information
- **API Server**: RESTful API for accessing the processed data
- **Rate Limiting**: Intelligent handling of API rate limits when processing data
- **Database Management**: Automated backups and efficient storage of disclosure data
- **Name Standardization**: Algorithms to standardize MP names and electorates

## Frontend Features

- **Dashboard Overview**: Key statistics and recent disclosures at a glance
- **MP Profiles**: Detailed profiles for each MP with disclosure history
- **Disclosure Analytics**: Data visualizations showing disclosure trends and patterns
- **Gift Analysis**: Specialized analysis of gifts received by MPs
- **Entity Explorer**: Network visualization of relationships between MPs and entities
- **Geographic View**: Visualization of disclosures by electorate
- **Export Functionality**: Export data for further analysis

## Getting Started

### Backend Setup

1. Ensure you have Python 3.8+ installed
2. Install required packages:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the setup script to initialize the database:
   ```bash
   ./setup_pipeline.sh
   ```
4. Process parliamentary disclosures:
   ```bash
   python process_parliament_disclosures.py --all --store-in-db --standardize
   ```
5. Start the API server:
   ```bash
   python api_server.py
   ```

### Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Create a `.env` file with your API endpoint:
   ```
   VITE_API_URL=http://localhost:3001/api
   ```
4. Start the development server:
   ```bash
   npm run dev
   ```
5. The application will be available at `http://localhost:5173`

## Technology Stack

### Backend
- Python
- SQLite
- PDF processing libraries (PyPDF2, pdfplumber)
- Google's Gemini API for advanced text processing
- Flask for API serving

### Frontend
- React
- TypeScript
- React Router
- React Query
- Recharts
- Tailwind CSS

## Contributing

Contributions are welcome! See the CONTRIBUTING.md file for guidelines.

## License

This project is part of the g0v (Gov Zero) initiative and is open-sourced under the MIT License.

## Acknowledgements

- Data provided by the Australian Parliament House
- Project inspired by the need for greater transparency in government
- g0v community for support and collaboration 