import streamlit as st
import requests
import csv
import datetime
import os
import pandas as pd
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
API_KEY = os.getenv("SERPER_API_KEY")

# Function to Check Rankings
def check_ranking(keyword, target_urls):
    url = "https://google.serper.dev/search"
    
    headers = {
        "X-API-KEY": API_KEY,
        "Content-Type": "application/json"
    }
    
    payload = {
        "q": keyword,
        "gl": "LK",  # Google.lk
        "hl": "en",
        "num": 100  # Get top 100 results
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
                results[target_url] = f"Page {((position - 1) // 10) + 1} Rank {position}"
            else:
                results[target_url] = "Not Ranked"
        
        return results
    else:
        st.error(f"❌ Error for '{keyword}': {response.status_code} - {response.text}")
        return {url: "Error" for url in target_urls}

# Save CSV File
def save_csv(data, target_urls):
    now = datetime.datetime.now()
    filename = f"rankings_matrix_{now.strftime('%Y-%m-%d_%H-%M')}.csv"
    filepath = os.path.join(os.getcwd(), filename)
    
    with open(filepath, mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["Keyword"] + target_urls)
        writer.writerows(data)
    
    return filepath

# Streamlit UI
st.title("🔍 Keyword Ranking Checker")

keywords = st.text_area("Enter Keywords (comma separated)", "")
urls = st.text_area("Enter URLs (comma separated)", "")

if st.button("Start Ranking Check"):
    if keywords and urls:
        keywords_list = [k.strip() for k in keywords.split(",")]
        urls_list = [u.strip() for u in urls.split(",")]
        
        ranking_data = []
        progress_bar = st.progress(0)
        
        for i, keyword in enumerate(keywords_list):
            rankings = check_ranking(keyword, urls_list)
            ranking_data.append([keyword] + [rankings[url] for url in urls_list])
            progress_bar.progress((i + 1) / len(keywords_list))
        
        df = pd.DataFrame(ranking_data, columns=["Keyword"] + urls_list)
        st.success("✅ Ranking check completed!")

        # Display Results
        st.write("### Ranking Results")
        st.dataframe(df)

        # Save and Provide Download Option
        csv_file = save_csv(ranking_data, urls_list)
        with open(csv_file, "rb") as file:
            st.download_button(
                label="📥 Download CSV",
                data=file,
                file_name=os.path.basename(csv_file),
                mime="text/csv"
            )
    else:
        st.warning("⚠️ Please enter both keywords and URLs.")
