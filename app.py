import streamlit as st
import requests
import pandas as pd
import csv
import io

# Retrieve API key from Streamlit Secrets
API_KEY = st.secrets["settings"]["SERPER_API_KEY"]

# Function to Check Rankings
def check_ranking(keyword, target_urls):
    url = "https://google.serper.dev/search"
    headers = {
        "X-API-KEY": API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "q": keyword,
        "gl": "LK",
        "hl": "en",
        "num": 100
    }
    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        rankings = data.get("organic", [])
        results = {}
        for target_url in target_urls:
            position = next(
                (res["position"] for res in rankings if target_url in res["link"]), 
                None
            )
            if position:
                page_number = ((position - 1) // 10) + 1
                position_in_page = ((position - 1) % 10) + 1
                results[target_url] = f"Page {page_number} Rank {position_in_page}"
            else:
                results[target_url] = "Not Ranked"
        return results
    else:
        st.error(f"❌ Error for '{keyword}': {response.status_code} - {response.text}")
        return {url: "Error" for url in target_urls}

# Function to Generate CSV
def generate_csv(data, target_urls):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Keyword"] + target_urls)
    writer.writerows(data)
    return output.getvalue()

# Page config
st.set_page_config(
    page_title="Keyword Ranking Checker",
    page_icon="🔍",
    layout="wide"
)

# Custom CSS for modern UI
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
    .input-section {
        background-color: #f8f9fa;
        padding: 1.5rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .results-section {
        background-color: #ffffff;
        padding: 1.5rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .sidebar .sidebar-content {
        background-color: #f8f9fa;
        padding: 1.5rem;
        border-radius: 0.5rem;
    }
    .stMarkdown h3 {
        color: #0066cc;
    }
    .stMarkdown h2 {
        color: #004080;
    }
    .stDataFrame {
        border-radius: 0.5rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    </style>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.markdown("### ℹ️ About")
    st.info("""
        This tool helps you check keyword rankings for any URL on Google.lk.
        
        - Enter multiple keywords (comma-separated)
        - Enter multiple URLs to track
        - Get page and position rankings
        - Export results to CSV
    """)
    st.markdown("---")
    st.markdown("### 🛠️ How to Use")
    st.write("""
        1. Enter keywords in the **Keywords** field.
        2. Enter URLs in the **URLs to Track** field.
        3. Click **Start Ranking Check**.
        4. View results and download as CSV.
    """)

# Main content
st.title("🔍 Keyword Ranking Checker")
st.markdown("Check the rankings of your keywords on Google.lk for specific URLs.")

# Input section
st.markdown("### 📝 Enter Your Keywords and URLs")
with st.container():
    col1, col2 = st.columns(2)

    with col1:
        keywords = st.text_area(
            "Keywords",
            placeholder="Enter keywords separated by commas...\nExample: loan, leasing, finance",
            help="Enter each keyword separated by commas"
        )

    with col2:
        urls = st.text_area(
            "URLs to Track",
            placeholder="Enter URLs separated by commas...\nExample: lolc.com, example.com",
            help="Enter each URL separated by commas"
        )

# Action button
if st.button("🚀 Start Ranking Check", use_container_width=True):
    if keywords and urls:
        keywords_list = [k.strip() for k in keywords.split(",")]
        urls_list = [u.strip() for u in urls.split(",")]
        
        with st.status("🔄 Checking rankings...") as status:
            ranking_data = []
            progress_bar = st.progress(0)
            
            for i, keyword in enumerate(keywords_list):
                status.update(label=f"Processing: {keyword}")
                rankings = check_ranking(keyword, urls_list)
                ranking_data.append([keyword] + [rankings[url] for url in urls_list])
                progress_bar.progress((i + 1) / len(keywords_list))
            
            status.update(label="✅ Ranking check completed!", state="complete")
            
            # Display Results
            st.markdown("### 📊 Ranking Results")
            df = pd.DataFrame(ranking_data, columns=["Keyword"] + urls_list)
            st.dataframe(df, use_container_width=True)
            
            # Download button
            csv_data = generate_csv(ranking_data, urls_list)
            st.download_button(
                label="📥 Download Results as CSV",
                data=csv_data,
                file_name="rankings.csv",
                mime="text/csv",
                help="Download the results in CSV format"
            )
    else:
        st.warning("⚠️ Please enter both keywords and URLs to check rankings.")