# Keyword Ranking Checker & Multi-Domain Rank Tracker
A Streamlit application that provides three functionalities:
1. Check keyword rankings of specified URLs on Google.lk using the Serper API with CSV export
2. Track and automatically update keyword rankings for LOLC in Google Sheets with color-coded performance indicators
3. Track and automatically update keyword rankings for multiple domains in Google Sheets with an easy domain selection interface

## Features

### Keyword Ranking Checker
* Check rankings of multiple URLs for specified keywords on Google.lk
* Real-time progress tracking during ranking checks  
* Interactive results table showing URL rankings per keyword
* Export functionality to download ranking data as CSV to local device

### LOLC and ABM Rank Tracker
* Automatic updates to Google Sheets with ranking data
* Color-coded visualization of ranking performance
* Reference domain comparison with improvement indicators
* Real-time progress tracking during updates

### Multi-Domain Rank Tracker
* Support for tracking multiple domains (including Alliance Finance, Anthoneys, and more)
* Dropdown selection interface for quick domain changes
* Domain-specific sheet tracking within a single Google Spreadsheet
* Automatic updates to Google Sheets with ranking data
* Reference domain comparison with improvement indicators
* Real-time progress tracking during updates
* Easy configuration for adding new domains

## Prerequisites
* Streamlit account for cloud deployment
* Serper API key for search results access
* Google Cloud Service Account (for LOLC and Multi-Domain Rank Tracker functionalities)
* Google Sheet with appropriate structure (for LOLC and Multi-Domain Rank Tracker functionalities)

## Setup
1. Install required dependencies:
```bash
pip install streamlit requests pandas gspread oauth2client
```

2. Configure your `.streamlit/secrets.toml`:

For basic keyword checking:
```toml
[settings]
SERPER_API_KEY = "your_serper_api_key"
```

For LOLC and Multi-Domain Rank Tracker functionality, add:
```toml
SHEET_ID = "your_google_sheet_id"

[gcp_service_account]
type = "service_account"
project_id = "your_project_id"
private_key_id = "your_private_key_id"
private_key = "your_private_key"
client_email = "your_client_email"
client_id = "your_client_id"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "your_client_x509_cert_url"
universe_domain = "googleapis.com"
```

3. For LOLC Rank Tracker: Prepare your Google Sheet:
   * First column should contain keywords
   * Subsequent columns should contain domain names
   * Include your reference domain (default: "lolcfinance.com")

4. For Multi-Domain Rank Tracker: Prepare your Google Sheets:
   * Create separate worksheets in the same spreadsheet for each domain
   * First column in each worksheet should contain keywords
   * Include a column with the domain name as its header
   * Note the GID of each worksheet for configuration

## Usage

### Keyword Ranking Checker
1. Enter comma-separated keywords to check
2. Enter comma-separated target URLs
3. Click "Start Ranking Check" to begin analysis
4. View the results table showing rankings for each URL/keyword combination
5. Download results as CSV using the Download button

### LOLC Rank Tracker
1. Click "Update Rankings in Google Sheet" to start the process
2. Monitor real-time progress with the progress bar
3. View success/error messages for operation status

### Multi-Domain Rank Tracker
1. Select the domain you want to track from the dropdown menu
2. Click "Start Update" to begin the ranking update process
3. Monitor real-time progress with the progress bar
4. View success/error messages for operation status
5. Switch domains using the dropdown to work with different tracking sheets

## Adding New Domains
To add a new domain to track:
1. Create a new worksheet in your Google Spreadsheet
2. Note the GID of the new worksheet
3. Update the `DOMAIN_CONFIG` dictionary in the code:
```python
DOMAIN_CONFIG = {
    # Existing domains...
    "your-new-domain.com": {
        "sheet_gid": 1234567890,  # The new worksheet GID
        "display_name": "Your New Domain"  # Display name for the dropdown
    }
}
```

## Code Structure

### Keyword Ranking Checker
`check_ranking(keyword, target_urls)`
* Queries Serper API for keyword search results
* Identifies ranking positions for target URLs

`generate_csv(data, target_urls)` 
* Creates downloadable CSV from ranking data

### LOLC Rank Tracker
#### RankTracker Class
* `setup_credentials()`: Initializes Google Sheets authentication
* `setup_google_sheets()`: Establishes connection to the specified sheet
* `setup_serper_api()`: Configures Serper API access
* `update_google_sheet()`: Main function for updating rankings

### Multi-Domain Rank Tracker
#### RankTracker Class (Enhanced)
* `__init__(selected_domain)`: Initializes tracking for the selected domain
* `setup_credentials()`: Initializes Google Sheets authentication
* `setup_google_sheets()`: Establishes connection to the domain's sheet
* `setup_serper_api()`: Configures Serper API access
* `update_google_sheet()`: Main function for updating rankings for selected domain
* `get_domain_stats()`: Retrieves statistics for the selected domain

### Visual Indicators
* Green: Best ranking domain for a keyword
* Yellow: Reference domain
* Up arrow (↑): Improved ranking from previous check

### Domain Configuration
* Centralized configuration dictionary for easy domain management
* GID-based worksheet selection for each domain
* Display names for user-friendly domain selection
* Extensible design for adding new domains

### Error Handling
* Comprehensive exception handling
* Detailed logging
* User-friendly error messages
* Automatic retries for API failures

## Configuration Constants
* `REFERENCE_DOMAIN`: Domain to track for improvements (LOLC tracker)
* `DOMAIN_CONFIG`: Dictionary of domains and their configurations (Multi-domain tracker)
* `REQUEST_TIMEOUT`: API request timeout (seconds)
* `MAX_RETRIES`: Number of API retry attempts
* `RETRY_DELAY`: Delay between retries (seconds)
* `SCOPE`: Google Sheets API scope
* `SHEET_ID`: Google Spreadsheet identifier

## Notes
* Rankings are cached for 1 hour to minimize API usage
* Supports up to 100 search results per keyword
* Color coding is automatically applied to the Google Sheet
* All operations are logged for debugging purposes
* Single spreadsheet with multiple worksheets for different domains

## Best Practices
* Regularly monitor API usage
* Keep keywords list manageable for API limits
* Backup Google Sheet before major updates
* Check logs for any recurring issues
* Use consistent column structure across domain worksheets

## User Interface
Built with Streamlit components for:
* Domain selection dropdown (Multi-domain tracker)
* Keyword/URL input fields (Keyword checker)
* Progress tracking
* Results display
* CSV download functionality (Keyword checker)
* Google Sheets update functionality

For more information about the APIs used:
* [Serper API Documentation](https://serper.dev/documentation)
* [Google Sheets API Documentation](https://developers.google.com/sheets/api)
* [Streamlit Documentation](https://docs.streamlit.io)

## License

This project is licensed under the MIT License. See the LICENSE file for details.