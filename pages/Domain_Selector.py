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

# Domain configuration
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
        "display_name": "Bankcioforum"
    },
    "baurs.com": {
        "sheet_gid": 1988253579,
        "display_name": "Baurs"
    },
    "beirabrush.com": {
        "sheet_gid": 1133723007,
        "display_name": "Beirabrush"
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

class RankTracker:
    def __init__(self, selected_domain: str):
        """Initialize the RankTracker with proper error handling."""
        try:
            self.selected_domain = selected_domain
            self.domain_config = DOMAIN_CONFIG.get(selected_domain)
            
            if not self.domain_config:
                raise ValueError(f"Configuration for domain {selected_domain} not found")
                
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
            spreadsheet = self.client.open_by_key(SHEET_ID)
            self.sheet = spreadsheet.get_worksheet_by_id(self.domain_config["sheet_gid"])
            if not self.sheet:
                raise ValueError(f"Worksheet with GID {self.domain_config['sheet_gid']} not found")
        except Exception as e:
            raise Exception(f"😭 Failed to connect to Google Sheet: {str(e)}")

    def setup_serper_api(self):
        """Set up Serper API with validation."""
        self.api_key = st.secrets.get("settings", {}).get("SERPER_API_KEY")
        if not self.api_key:
            raise ValueError("🙀 SERPER_API_KEY not found in Streamlit secrets")

    def update_google_sheet(self):
        """Update Google Sheet without changing formatting."""
        try:
            data = self.sheet.get_all_values()
            if not data:
                st.warning("🚫 No data found in the Google Sheet")
                return

            headers = data[0]
            if len(headers) < 2 or headers[0].lower() != "keyword" or self.selected_domain.lower() not in [h.lower() for h in headers]:
                st.error(f"🔍❌ Required headers 'keyword' and '{self.selected_domain}' not found in sheet")
                return
                
            domain_col_index = next(i for i, h in enumerate(headers) if h.lower() == self.selected_domain.lower())
            keywords_col_index = headers.index("keyword") if "keyword" in headers else 0
            
            keywords = [row[keywords_col_index] for row in data[1:] if row]
            previous_data = {row[keywords_col_index]: row for row in data[1:] if row}
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # We'll update cells one by one to preserve formatting
            for i, keyword in enumerate(keywords):
                if not keyword:
                    continue
                    
                status_text.text(f"Processing keyword: {keyword}")
                progress_bar.progress((i + 1) / len(keywords))
                
                # Get the ranking for this keyword
                rankings = check_ranking(self.api_key, keyword, [self.selected_domain])
                new_position, new_rank_text = rankings.get(self.selected_domain, (None, "Not Ranked"))
                
                # Get old rank for comparison and add arrow if improved
                old_rank_text = previous_data.get(keyword, [])[domain_col_index] if keyword in previous_data and len(previous_data[keyword]) > domain_col_index else ""
                if old_rank_text and "Rank" in old_rank_text:
                    old_rank_match = re.search(r'Rank (\d+)', old_rank_text)
                    if old_rank_match and new_position:
                        old_rank = int(old_rank_match.group(1))
                        if new_position < old_rank:
                            new_rank_text = f"{new_rank_text} ↑"
                
                # Update only this specific cell to preserve other formatting
                row_num = data.index(previous_data.get(keyword, [])) + 1 if keyword in previous_data else i + 2
                self.sheet.update_cell(row_num, domain_col_index + 1, new_rank_text)
                
                # Small delay to avoid hitting API rate limits
                time.sleep(0.2)
            
            progress_bar.empty()
            status_text.empty()
            st.success(f"✅🔥 Rankings for {self.selected_domain} updated successfully!")
            
        except Exception as e:
            logger.error(f"❗️ Failed to update Google Sheet: {str(e)}")
            st.error(f"❗️ Failed to update rankings: {str(e)}")
            raise

    def get_domain_stats(self) -> Dict[str, Any]:
        """Get statistics for the selected domain."""
        try:
            data = self.sheet.get_all_values()
            keywords_count = len(data) - 1 if data else 0
            return {
                "keywords_count": keywords_count,
                "reference_domain": self.selected_domain,
                "display_name": self.domain_config["display_name"]
            }
        except Exception as e:
            logger.error(f"Failed to get domain stats: {str(e)}")
            return {
                "keywords_count": 0,
                "reference_domain": self.selected_domain,
                "display_name": self.domain_config["display_name"]
            }

def main():
    st.set_page_config(
        page_title="Multi-Domain Rank Tracker",
        page_icon="📊",
        layout="wide"
    )
    
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
        .stSelectbox label, .stSelectbox div[data-baseweb="select"] {
            font-size: 1.1rem;
        }
        .stSelectbox div[data-baseweb="select"] {
            margin-top: 0.5rem;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Domain Selection
    domain_options = {config["display_name"]: domain for domain, config in DOMAIN_CONFIG.items()}
    display_names = list(domain_options.keys())
    
    selected_display_name = st.selectbox(
        "📌 Select Domain to Track",
        options=display_names,
        index=0
    )
    selected_domain = domain_options[selected_display_name]
    
    # Sidebar
    with st.sidebar:
        st.markdown("### 📈 Tracking Statistics")
        if st.secrets.get("settings") and st.secrets.get("gcp_service_account"):
            try:
                tracker = RankTracker(selected_domain)
                if tracker.initialization_successful:
                    stats = tracker.get_domain_stats()
                    
                    st.markdown(f"""
                        - 🎯 Keywords tracked: **{stats['keywords_count']}**
                        - 🌐 Reference domain: **{stats['reference_domain']}**
                    """)
            except Exception:
                st.warning("⚠️ Could not load tracking statistics")
        
        st.markdown("---")
        st.markdown("### ℹ️ About")
        st.markdown("""
            This tool tracks keyword rankings for multiple domains across Google Search Results.
            Updates are synchronized with Google Sheets for easy tracking and sharing.
            
            **Legend:**
            - ↑ Improved ranking
            
            **How to add a new domain:**
            1. Update the DOMAIN_CONFIG dictionary in the code
            2. Add the domain and its GID
            3. Ensure the sheet has 'keyword' and domain name as headers
        """)
    
    # Main content area
    st.title(f"📊 {selected_display_name} Rank Tracker")
    
    try:
        tracker = RankTracker(selected_domain)
        if not tracker.initialization_successful:
            st.error(f"⚠️ Initialization failed: {tracker.error_message}")
            return
        
        # Status metrics
        col1, = st.columns(1)
        
        with col1:
            st.metric(
                label="Reference Domain", 
                value=selected_domain,
                help="Domain being tracked",
                delta="Active"
            )
        
        st.markdown("---")
        
        # Main action area
        st.markdown("### 🔄 Update Rankings")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            st.info(f"""
                Click the button to fetch the latest keyword rankings for **{selected_domain}** from Google Search.
                Rankings will be updated in the connected Google Sheet while preserving existing formatting.
                
                **Note:** This process may take a few minutes depending on the number of keywords.
            """)
        
        with col2:
            if st.button("🚀 Start Update", use_container_width=True):
                with st.spinner(f"⏱️ Fetching latest rankings for {selected_domain}..."):
                    tracker.update_google_sheet()
                    st.session_state.last_update = time.strftime("%Y-%m-%d %H:%M:%S")

    except Exception as e:
        st.error(f"🚨 An error occurred: {str(e)}")
        logger.exception("💣 Application error")

if __name__ == "__main__":
    main()