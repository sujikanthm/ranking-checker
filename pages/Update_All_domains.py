import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import re
import time
import logging
from typing import Dict, List, Tuple, Optional, Any
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
SHEET_ID = "1vOo7sD_I7cyAWrRWeDaa8szHi8xEG4WrFwqfpsnhDpQ"

# Domain configuration (same as previous script)
DOMAIN_CONFIG = {
    "alliancefinance.lk": {
        "sheet_gid": 82728278,
        "display_name": "Alliance Finance"
    },
    "anthoneys.com": {
        "sheet_gid": 1524835619,
        "display_name": "Anthoneys"
    },
    "babynames.lk": {
        "sheet_gid": 2062356919,
        "display_name": "Babynames"
    },
    "bankcioforum.lk": {
        "sheet_gid": 277049799,
        "display_name": "Bank CIO Forum"
    },
    "baurs.com": {
        "sheet_gid": 1988253579,
        "display_name": "Baurs"
    },
    "beirabrush.com": {
        "sheet_gid": 1133723007,
        "display_name": "Beira Brush"
    },
    "carsoncumberbatch.com": { 
        "sheet_gid": 1203202907,
        "display_name": "Carson Cumberbatch"
    },
    "dorakadapaliya.com": {
        "sheet_gid": 78524544,
        "display_name": "Dorakadapaliya"
    },
    "ecospindles.com": {
        "sheet_gid": 450928913,
        "display_name": "Ecospindles"
    },
    "janathasteels.lk": {
        "sheet_gid": 252478567,
        "display_name": "Janatha Steels"
    },
    "johnkeellsfoundation.com": {
        "sheet_gid": 2068561581,
        "display_name": "John Keells Foundation"
    },
    "kalapola.lk": {
        "sheet_gid": 45289608,
        "display_name": "Kalapola"
    },
    "kia.lk": {
        "sheet_gid": 58695663,
        "display_name": "Kia"
    },
    "lalangroup.com": {
        "sheet_gid": 299225538,
        "display_name": "Lalan Group"
    },
    "lalanrubbers.com": {
        "sheet_gid": 756345670,
        "display_name": "Lalan Rubbers"
    },
    "lankaacdemy.lk": {
        "sheet_gid": 603026025,
        "display_name": "Lanka Academy"
    },
    "lankatalents.lk": {
        "sheet_gid": 1970971384,
        "display_name": "Lanka Talents"
    },
    "lolcfinance.com": {
        "sheet_gid": 408082916,
        "display_name": "LOLC Finance"
    },
    "lolcgeneral.com": {
        "sheet_gid": 287586014,
        "display_name": "LOLC General"
    },
    "lolclife.com": {
        "sheet_gid": 1720241000,
        "display_name": "LOLC Life"
    },
    "plasticcycle.lk": {
        "sheet_gid": 1724175216,
        "display_name": "Plasticcycle"
    },
    "senikmaholdings.com": {
        "sheet_gid": 22768441,
        "display_name": "Senikma Holdings"
    },
    "keells.com": {
        "sheet_gid": 2055861260,
        "display_name": "Keells"
    }
    # Add more domains here in the future
}

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
                logger.error(f"⏰ All attempts failed for keyword: {keyword}")
                return {url: (None, "Error") for url in target_urls}

class MultiDomainRankTracker:
    def __init__(self):
        """Initialize the MultiDomainRankTracker with proper error handling."""
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
            raise Exception(f"🤯 Failed to set up Google credentials: {str(e)}")

    def setup_google_sheets(self):
        """Set up connection to the Sheet."""
        try:
            self.spreadsheet = self.client.open_by_key(SHEET_ID)
        except Exception as e:
            raise Exception(f"😭 Failed to connect to Google Sheet: {str(e)}")

    def setup_serper_api(self):
        """Set up Serper API with validation."""
        self.api_key = st.secrets.get("settings", {}).get("SERPER_API_KEY")
        if not self.api_key:
            raise ValueError("🙀 SERPER_API_KEY not found in Streamlit secrets")

    def update_all_domains(self):
        """Update rankings for all domains in the configuration."""
        progress_bar = st.progress(0)
        status_text = st.empty()
        domains_processed = []
        domains_failed = []

        try:
            total_domains = len(DOMAIN_CONFIG)
            for i, (domain, config) in enumerate(DOMAIN_CONFIG.items()):
                try:
                    # Update status
                    status_text.text(f"Processing domain: {domain}")
                    progress_bar.progress((i + 1) / total_domains)

                    # Get the specific worksheet
                    sheet = self.spreadsheet.get_worksheet_by_id(config["sheet_gid"])
                    if not sheet:
                        st.warning(f"⚠️ Worksheet for {domain} not found")
                        domains_failed.append(domain)
                        continue

                    # Get data from sheet
                    data = sheet.get_all_values()
                    if not data:
                        st.warning(f"🚫 No data found in sheet for {domain}")
                        domains_failed.append(domain)
                        continue

                    headers = data[0]
                    if len(headers) < 2 or headers[0].lower() != "keyword" or domain.lower() not in [h.lower() for h in headers]:
                        st.error(f"🔍❌ Required headers for {domain} not found")
                        domains_failed.append(domain)
                        continue
                
                    domain_col_index = next(i for i, h in enumerate(headers) if h.lower() == domain.lower())
                    keywords_col_index = headers.index("keyword") if "keyword" in headers else 0
                
                    keywords = [row[keywords_col_index] for row in data[1:] if row]
                    previous_data = {row[keywords_col_index]: row for row in data[1:] if row}
                
                    # We'll update cells one by one to preserve formatting
                    for j, keyword in enumerate(keywords):
                        if not keyword:
                            continue
                    
                        # Get the ranking for this keyword
                        rankings = check_ranking(self.api_key, keyword, [domain])
                        new_position, new_rank_text = rankings.get(domain, (None, "Not Ranked"))
                    
                        # Get old rank for comparison and add arrow if improved
                        old_rank_text = previous_data.get(keyword, [])[domain_col_index] if keyword in previous_data and len(previous_data[keyword]) > domain_col_index else ""
                        if old_rank_text and "Rank" in old_rank_text:
                            old_rank_match = re.search(r'Rank (\d+)', old_rank_text)
                            if old_rank_match and new_position:
                                old_rank = int(old_rank_match.group(1))
                                if new_position < old_rank:
                                    new_rank_text = f"{new_rank_text} ↑"
                    
                        # Update only this specific cell to preserve other formatting
                        row_num = data.index(previous_data.get(keyword, [])) + 1 if keyword in previous_data else j + 2
                        sheet.update_cell(row_num, domain_col_index + 1, new_rank_text)
                    
                        # Small delay to avoid hitting API rate limits
                        time.sleep(0.2)
                
                    domains_processed.append(domain)
                
                except Exception as domain_error:
                    logger.error(f"Error processing {domain}: {str(domain_error)}")
                    domains_failed.append(domain)
            
            # Final summary
            progress_bar.empty()
            status_text.empty()
            
            if domains_processed:
                st.success(f"✅🔥 Rankings updated for: {', '.join(domains_processed)}")
            if domains_failed:
                st.warning(f"⚠️ Failed to update: {', '.join(domains_failed)}")
            
        except Exception as e:
            logger.error(f"❗️ Failed to update all domains: {str(e)}")
            st.error(f"❗️ Failed to update rankings: {str(e)}")
            raise

def main():
    st.set_page_config(
        page_title="All Domains Rank Tracker",
        page_icon="📊",
        layout="wide"
    )
    
    # Custom CSS for styling
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
    
    st.title("📊 Multi-Domain Rank Tracker")
    
    try:
        tracker = MultiDomainRankTracker()
        if not tracker.initialization_successful:
            st.error(f"⚠️ Initialization failed: {tracker.error_message}")
            return
        
        # Sidebar with instructions
        with st.sidebar:
            st.markdown("### ℹ️ About")
            st.markdown("""
                This tool updates keyword rankings for **ALL** configured domains in one click.
                
                What it does:
                - Fetches rankings for every domain
                - Updates Google Sheets for each domain
                - Preserves existing sheet formatting
                
                Domains to be updated:
            """)
            
            # List domains in a more readable format
            for config in DOMAIN_CONFIG.values():
                st.markdown(f"- {config['display_name']}")
        
        # Main content area
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.info(f"""
                Click the button below to fetch the latest keyword rankings for **{len(DOMAIN_CONFIG)} domains**.
                
                **Note:** This process may take several minutes depending on the total number of keywords across all domains.
            """)
        
        with col2:
            if st.button("🚀 Update All Domains", use_container_width=True):
                with st.spinner("⏱️ Fetching latest rankings for all domains..."):
                    tracker.update_all_domains()
                    st.session_state.last_update = time.strftime("%Y-%m-%d %H:%M:%S")

    except Exception as e:
        st.error(f"🚨 An error occurred: {str(e)}")
        logger.exception("💣 Application error")

if __name__ == "__main__":
    main()