import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import re
import time
import logging
from typing import Dict, List, Tuple, Optional
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
RETRY_DELAY = 1
REFERENCE_DOMAIN = "lolcfinance.com"
GREEN_COLOR = {"red": 183/255, "green": 215/255, "blue": 168/255}
YELLOW_COLOR = {"red": 255/255, "green": 235/255, "blue": 156/255}

@st.cache_data(ttl=3600)
def check_ranking(api_key: str, keyword: str, target_urls: List[str]) -> Dict[str, Tuple[Optional[int], str]]:
    """Check rankings with improved error handling."""
    url = "https://google.serper.dev/search"
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    payload = {"q": keyword, "gl": "LK", "hl": "en", "num": 100}
    
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            rankings = data.get("organic", [])

            results = {}
            for target_url in target_urls:
                position = next((res["position"] for res in rankings if target_url in res["link"]), None)
                if position:
                    page_number = ((position - 1) // 10) + 1
                    position_in_page = ((position - 1) % 10) + 1
                    results[target_url] = (position, f"Page {page_number} Rank {position_in_page}")
                else:
                    results[target_url] = (None, "Not Ranked")
            
            return results
        except requests.exceptions.RequestException as e:
            logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
            else:
                logger.error(f"All attempts failed for keyword: {keyword}")
                return {url: (None, "Error") for url in target_urls}

class RankTracker:
    def __init__(self):
        """Initialize the RankTracker with proper error handling."""
        try:
            self.setup_credentials()
            self.setup_google_sheets()
            self.setup_serper_api()
            self.initialization_successful = True
        except Exception as e:
            logger.error(f"Initialization error: {str(e)}")
            self.initialization_successful = False
            self.error_message = str(e)

    def setup_credentials(self):
        """Set up Google Sheets credentials with error checking."""
        service_account_path = Path("service_account.json")
        if not service_account_path.exists():
            raise FileNotFoundError("service_account.json not found. Please ensure it's in the same directory as this script.")
        
        try:
            self.creds = ServiceAccountCredentials.from_json_keyfile_name(str(service_account_path), SCOPE)
            self.client = gspread.authorize(self.creds)
        except Exception as e:
            raise Exception(f"Failed to set up Google credentials: {str(e)}")

    def setup_google_sheets(self):
        """Set up Google Sheets connection with proper error handling."""
        try:
            sheet_id = st.secrets.get("settings", {}).get("SHEET_ID")
            if not sheet_id:
                raise ValueError("SHEET_ID not found in Streamlit secrets")
            
            sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit?gid=0"
            self.sheet = self.client.open_by_url(sheet_url).sheet1
        except Exception as e:
            raise Exception(f"Failed to connect to Google Sheet: {str(e)}")

    def setup_serper_api(self):
        """Set up Serper API with validation."""
        self.api_key = st.secrets.get("settings", {}).get("SERPER_API_KEY")
        if not self.api_key:
            raise ValueError("SERPER_API_KEY not found in Streamlit secrets")

    def clear_cell_formatting(self):
        """Clear cell formatting with error handling."""
        try:
            self.sheet.spreadsheet.batch_update({
                "requests": [{
                    "updateCells": {
                        "range": {"sheetId": 0},
                        "fields": "userEnteredFormat.backgroundColor"
                    }
                }]
            })
        except Exception as e:
            logger.error(f"Failed to clear cell formatting: {str(e)}")
            raise

    def apply_cell_formatting(self, cells_to_format: List[Dict]):
        """Apply cell formatting with validation."""
        if not cells_to_format:
            return

        try:
            batch_requests = {"requests": []}
            for cell in cells_to_format:
                row, col = cell["row"], cell["col"]
                batch_requests['requests'].append({
                    "repeatCell": {
                        "range": {
                            "sheetId": 0,
                            "startRowIndex": row,
                            "endRowIndex": row + 1,
                            "startColumnIndex": col,
                            "endColumnIndex": col + 1
                        },
                        "cell": {"userEnteredFormat": {"backgroundColor": cell["color"]}},
                        "fields": "userEnteredFormat.backgroundColor"
                    }
                })
            self.sheet.spreadsheet.batch_update(batch_requests)
        except Exception as e:
            logger.error(f"Failed to apply cell formatting: {str(e)}")
            raise

    def update_google_sheet(self):
        """Update Google Sheet with comprehensive error handling."""
        try:
            data = self.sheet.get_all_values()
            if not data:
                st.warning("No data found in the Google Sheet")
                return

            headers = data[0]
            keywords = [row[0] for row in data[1:]]
            domains = headers[1:]
            
            if REFERENCE_DOMAIN not in domains:
                st.error(f"Reference domain '{REFERENCE_DOMAIN}' not found in sheet headers")
                return
                
            reference_domain_index = domains.index(REFERENCE_DOMAIN)
            previous_data = {row[0]: row[1:] for row in data[1:]}
            new_data, cells_to_format = [], []
            
            self.clear_cell_formatting()

            progress_bar = st.progress(0)
            status_text = st.empty()

            for i, keyword in enumerate(keywords):
                status_text.text(f"Processing keyword: {keyword}")
                progress_bar.progress((i + 1) / len(keywords))
                
                rankings = check_ranking(self.api_key, keyword, domains)
                row_data = [keyword]
                ref_position, ref_rank_text = rankings.get(REFERENCE_DOMAIN, (None, "Not Ranked"))
                ref_position = ref_position or float('inf')
                old_ref_rank_text = previous_data.get(keyword, [])[reference_domain_index] if keyword in previous_data else ""
                
                for j, domain in enumerate(domains):
                    new_position, new_rank_text = rankings.get(domain, (None, "Not Ranked"))
                    
                    if domain == REFERENCE_DOMAIN:
                        if old_ref_rank_text and "Rank" in old_ref_rank_text:
                            old_rank_match = re.search(r'Rank (\d+)', old_ref_rank_text)
                            if old_rank_match and new_position:
                                old_rank = int(old_rank_match.group(1))
                                if new_position < old_rank:
                                    new_rank_text = f"{new_rank_text} ↑"
                        
                        if all(new_position <= (rankings[d][0] or float('inf')) for d in domains if d != REFERENCE_DOMAIN):
                            cells_to_format.append({"row": i + 1, "col": j + 1, "color": GREEN_COLOR})
                        else:
                            cells_to_format.append({"row": i + 1, "col": j + 1, "color": YELLOW_COLOR})
                    elif new_position and new_position < ref_position:
                        cells_to_format.append({"row": i + 1, "col": j + 1, "color": GREEN_COLOR})
                    
                    row_data.append(new_rank_text)
                
                new_data.append(row_data)
            
            self.sheet.update(values=new_data, range_name="A2")
            self.apply_cell_formatting(cells_to_format)
            
            progress_bar.empty()
            status_text.empty()
            st.success("Rankings updated successfully!")
            
        except Exception as e:
            logger.error(f"Failed to update Google Sheet: {str(e)}")
            st.error(f"Failed to update rankings: {str(e)}")
            raise

def main():
    st.title("📊 LOLC Rank Tracker")
    
    # Check for required secrets
    if not st.secrets.get("settings"):
        st.error("Missing 'settings' in Streamlit secrets")
        st.info("Please configure the following in your .streamlit/secrets.toml file:")
        st.code("""
[settings]
SERPER_API_KEY = "your_serper_api_key"
SHEET_ID = "your_google_sheet_id"
        """)
        return

    try:
        tracker = RankTracker()
        if not tracker.initialization_successful:
            st.error(f"Initialization failed: {tracker.error_message}")
            return
            
        if st.button("🔄 Update Rankings in Google Sheet"):
            with st.spinner("Updating rankings..."):
                tracker.update_google_sheet()
                
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        logger.exception("Application error")

if __name__ == "__main__":
    main()