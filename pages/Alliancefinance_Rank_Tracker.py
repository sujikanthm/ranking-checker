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
REFERENCE_DOMAIN = "alliancefinance.lk"  # Update with your reference domain
SHEET_GID = 82728278  # Sheet's GID from URL
GREEN_COLOR = {"red": 183/255, "green": 215/255, "blue": 168/255}
YELLOW_COLOR = {"red": 255/255, "green": 235/255, "blue": 156/255}


@st.cache_data(ttl=3600)
def check_ranking(api_key: str, keyword: str, target_urls: List[str]) -> Dict[str, Tuple[Optional[int], str]]:
    """Check rankings with improved error handling."""
    url = "https://google.serper.dev/search"
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    payload = {"q": keyword, "gl": "us", "hl": "en", "num": 100}  # Adjust gl and hl as needed

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
                logger.error(f"⏰ All attempts failed for keyword: {keyword}")
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
            service_account_info = st.secrets["gcp_service_account"]
            self.creds = ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, SCOPE)
            self.client = gspread.authorize(self.creds)
        except Exception as e:
            raise Exception(f"🤯 Failed to set up Google credentials: {str(e)}")

    def setup_google_sheets(self):
        """Set up connection to Sheet."""
        try:
            sheet_id = "1vOo7sD_I7cyAWrRWeDaa8szHi8xEG4WrFwqfpsnhDpQ"  # Sheet ID from URL
            spreadsheet = self.client.open_by_key(sheet_id)
            self.sheet = spreadsheet.get_worksheet_by_id(SHEET_GID)
            if not self.sheet:
                raise ValueError(f"Worksheet with GID {SHEET_GID} not found")
        except Exception as e:
            raise Exception(f"😭 Failed to connect to Google Sheet: {str(e)}")

    def setup_serper_api(self):
        """Set up Serper API with validation."""
        self.api_key = st.secrets["settings"]["SERPER_API_KEY"]
        if not self.api_key:
            raise ValueError("🙀 SERPER_API_KEY not found in Streamlit secrets")

    def clear_cell_formatting(self):
        """Clear formatting for the sheet."""
        try:
            self.sheet.format("A1:Z1000", {"backgroundColor": {"red": 1, "green": 1, "blue": 1}}) # Clear all formatting
        except Exception as e:
            logger.error(f"🥲 Failed to clear cell formatting: {str(e)}")
            raise

    def apply_cell_formatting(self, cells_to_format: List[Dict]):
        """Apply formatting to the sheet."""
        if not cells_to_format:
            return

        try:
            for cell in cells_to_format:
                self.sheet.format(f"{cell['cell']}", {"backgroundColor": cell["color"]})
        except Exception as e:
            logger.error(f"❌ Failed to apply cell formatting: {str(e)}")
            raise

    def update_google_sheet(self):
        """Update Google Sheet with comprehensive error handling."""
        try:
            data = self.sheet.get_all_values()
            if not data:
                st.warning("🚫 No data found in the Google Sheet")
                return

            headers = data[0]
            keywords = [row[0] for row in data[1:]]
            domains = headers[1:]

            if REFERENCE_DOMAIN not in domains:
                st.error(f"🔍❌ Reference domain '{REFERENCE_DOMAIN}' not found in sheet headers")
                return

            reference_domain_index = domains.index(REFERENCE_DOMAIN)
            previous_data = {row[0]: row[1:] for row in data[1:]}
            new_data = []
            cells_to_format = []

            progress_bar = st.progress(0)
            status_text = st.empty()

            for i, keyword in enumerate(keywords):
                status_text.text(f"Processing keyword: {keyword}")
                progress_bar.progress((i + 1) / len(keywords))

                rankings = check_ranking(self.api_key, keyword, domains)
                row_data = [keyword]

                for j, domain in enumerate(domains):
                    new_position, new_rank_text = rankings.get(domain, (None, "Not Ranked"))
                    if domain == REFERENCE_DOMAIN:
                        cells_to_format.append({"cell": f"B{i+2}:Z{i+2}", "color": YELLOW_COLOR}) #Adjust range as needed
                    row_data.append(new_rank_text)
                new_data.append(row_data)

            self.sheet.update("A2", new_data)
            self.apply_cell_formatting(cells_to_format)

            progress_bar.empty()
            status_text.empty()
            st.success("✅🔥 Rankings updated successfully!")

        except Exception as e:
            logger.error(f"❗️ Failed to update Google Sheet: {str(e)}")
            st.error(f"❗️ Failed to update rankings: {str(e)}")
            raise


def main():
    st.set_page_config(
        page_title="t3cs Rank Tracker",
        page_icon="📊",
        layout="wide"
    )

    # Custom CSS (optional, but improves the look)
    st.markdown("""
        <style>
        .main .block-container { padding-top: 1rem; }
        .stButton>button {
            width: 100%;
            padding: 1rem;
            font-size: 1.2rem;
            background-color: #0066cc;
            color: white;
            border: none;
            border-radius: 0.5rem;
            transition: all 0.3s ease;
        }
        .stButton>button:hover {
            background-color: #0052a3;
            transform: translateY(-2px);
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        div[data-testid="metric-container"] {
            background-color: #f8f9fa;
            border-radius: 0.5rem;
            padding: 1rem;
        }
        </style>
    """, unsafe_allow_html=True)

    with st.sidebar:
        st.markdown("### 📈 Tracking Statistics")
        if st.secrets.get("settings") and st.secrets.get("gcp_service_account"):
            try:
                tracker = RankTracker()
                if tracker.initialization_successful:
                    data = tracker.sheet.get_all_values()
                    keywords_count = len(data) - 1 if data else 0
                    domains_count = len(data[0]) - 1 if data and data[0] else 0

                    st.markdown(f"""
                        - 🎯 Keywords tracked: **{keywords_count}**
                        - 🌐 Domains monitored: **{domains_count}**
                        - 📊 Reference domain: **{REFERENCE_DOMAIN}**
                    """)
            except Exception as e:
                st.warning(f"⚠️ Could not load tracking statistics: {e}")

        st.markdown("---")
        st.markdown("### ℹ️ About")
        st.markdown("""
            This tool tracks keyword rankings for t3cs domains across Google Search Results.
            Updates are synchronized with Google Sheets for easy tracking and sharing.
        """)

    st.title("📊 t3cs Rank Tracker")

    try:
        tracker = RankTracker()
        if not tracker.initialization_successful:
            st.error(f"⚠️ Initialization failed: {tracker.error_message}")
            return

        col1, = st.columns(1)
        with col1:
            st.metric(
                label="Reference Domain",
                value=REFERENCE_DOMAIN,
                help="Main domain being tracked",
                delta="Active"
            )

        st.markdown("---")

        st.markdown("### 🔄 Update Rankings")

        col1, col2 = st.columns([2, 1])
        with col1:
            st.info("""
                Click the button to fetch the latest keyword rankings from Google Search.
                Rankings will be automatically updated in the connected Google Sheet.
                
                **Note:** This process may take a few minutes depending on the number of keywords.
            """)

        with col2:
            if st.button("🚀 Start Update", use_container_width=True):
                with st.spinner("⏱️ Fetching latest rankings..."):
                    tracker.update_google_sheet()
                    st.success("✅ Rankings updated successfully!")

    except Exception as e:
        st.error(f"🚨 An error occurred: {str(e)}")
        logger.exception("💣 Application error")


if __name__ == "__main__":
    main()

