# Keyword Ranking Checker

A Streamlit app to check keyword rankings of specified URLs on Google.lk using the Serper API. View rankings in an interactive table and export results to CSV.

## Features

* Check rankings of multiple URLs for specified keywords on Google.lk
* Real-time progress tracking during ranking checks  
* Interactive results table showing URL rankings per keyword
* Export functionality to download ranking data as CSV

## Prerequisites

* Streamlit account for cloud deployment
* Serper API key for search results access
* API key must be stored in Streamlit Secrets Manager

## Setup

1. Install required dependencies:
```bash
pip install streamlit requests pandas
```

2. Configure Serper API key in `.streamlit/secrets.toml`:
```toml
[settings]
SERPER_API_KEY = "your_serper_api_key"
```

## Usage

1. Launch the app:
```bash
streamlit run app.py
```

2. Using the interface:
   * Enter comma-separated keywords to check
   * Enter comma-separated target URLs
   * Click "Start Ranking Check" to begin analysis

3. View the results table showing rankings for each URL/keyword combination

4. Download results as CSV using the Download button

## Code Structure

### Key Functions

`check_ranking(keyword, target_urls)`
* Queries Serper API for keyword search results
* Identifies ranking positions for target URLs

`generate_csv(data, target_urls)` 
* Creates downloadable CSV from ranking data

### User Interface

Built with Streamlit components for:
* Keyword/URL input fields
* Progress tracking
* Results display
* CSV download functionality

## License

This project is licensed under the MIT License. See the LICENSE file for details.