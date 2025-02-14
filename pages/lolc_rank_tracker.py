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
import json

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
        """Set up Google Sheets credentials using secrets.toml configuration."""
        try:
            # Get service account info from secrets
            service_account_info = {
                "type": st.secrets["gcp_service_account"]["type"],
                "project_id": st.secrets["gcp_service_account"]["project_id"],
                "private_key_id": st.secrets["gcp_service_account"]["private_key_id"],
                "private_key": st.secrets["gcp_service_account"]["private_key"],
                "client_email": st.secrets["gcp_service_account"]["client_email"],
                "client_id": st.secrets["gcp_service_account"]["client_id"],
                "auth_uri": st.secrets["gcp_service_account"]["auth_uri"],
                "token_uri": st.secrets["gcp_service_account"]["token_uri"],
                "auth_provider_x509_cert_url": st.secrets["gcp_service_account"]["auth_provider_x509_cert_url"],
                "client_x509_cert_url": st.secrets["gcp_service_account"]["client_x509_cert_url"],
                "universe_domain": st.secrets["gcp_service_account"]["universe_domain"]
            }
            
            self.creds = ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, SCOPE)
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
                
                # Find the best ranking position
                best_position = float('inf')
                best_domain_index = None
                
                for j, domain in enumerate(domains):
                    position, _ = rankings.get(domain, (None, "Not Ranked"))
                    if position and position < best_position:
                        best_position = position
                        best_domain_index = j
                
                # Process each domain
                for j, domain in enumerate(domains):
                    new_position, new_rank_text = rankings.get(domain, (None, "Not Ranked"))
                    
                    if domain == REFERENCE_DOMAIN:
                        # Get old reference rank for comparison
                        old_ref_rank_text = previous_data.get(keyword, [])[reference_domain_index] if keyword in previous_data else ""
                        if old_ref_rank_text and "Rank" in old_ref_rank_text:
                            old_rank_match = re.search(r'Rank (\d+)', old_ref_rank_text)
                            if old_rank_match and new_position:
                                old_rank = int(old_rank_match.group(1))
                                if new_position < old_rank:
                                    new_rank_text = f"{new_rank_text} ↑"
                        
                        # Color reference domain yellow by default
                        cells_to_format.append({"row": i + 1, "col": j + 1, "color": YELLOW_COLOR})
                        
                        # If reference domain is the best, change to green
                        if j == best_domain_index:
                            cells_to_format[-1]["color"] = GREEN_COLOR
                    
                    # Color the best ranking domain in green (if it's not the reference domain)
                    elif j == best_domain_index:
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
    if not st.secrets.get("settings") or not st.secrets.get("gcp_service_account"):
        st.error("Missing required configurations in Streamlit secrets")
        st.info("Please ensure both 'settings' and 'gcp_service_account' sections are configured in your .streamlit/secrets.toml file")
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