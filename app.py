from flask import Flask, render_template, request, jsonify, send_from_directory, redirect, url_for
from flask_socketio import SocketIO, emit
import requests
import csv
import datetime
import os
import threading
import time
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, async_mode='threading')

# 🔹 Your Serper API Key
API_KEY = os.getenv('SERPER_API_KEY')

# 🔹 Function to Check Rankings
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
        "num": 100    # Get top 100 results
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
        print(f"❌ Error for '{keyword}': {response.status_code} - {response.text}")
        return {url: "Error" for url in target_urls}

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@socketio.on('start_ranking')
def handle_start_ranking(data):
    keywords = data.get('keywords', '').split(',')
    target_urls = data.get('urls', '').split(',')
    
    def perform_ranking():
        ranking_data = []
        total_keywords = len(keywords)
        for i, keyword in enumerate(keywords):
            keyword = keyword.strip()
            print(f"🔍 Checking rankings for: {keyword}")
            rankings = check_ranking(keyword, target_urls)
            ranking_data.append([keyword] + [rankings[url.strip()] for url in target_urls])
            progress_percent = (i + 1) / total_keywords * 100
            socketio.emit('progress_update', {'percent': progress_percent})
        
        csv_filename = get_csv_filename()
        with open(csv_filename, mode="w", newline="") as file:
            writer = csv.writer(file)
            
            # Write header
            writer.writerow(["Keyword"] + [url.strip() for url in target_urls])
            
            # Write data
            writer.writerows(ranking_data)
        
        socketio.emit('ranking_complete', {'filename': csv_filename, 'ranking_data': ranking_data, 'target_urls': [url.strip() for url in target_urls]})
    
    thread = threading.Thread(target=perform_ranking)
    thread.start()

@app.route('/download', methods=['POST'])
def download_file():
    ranking_data = request.form.get('ranking_data', '')
    target_urls = request.form.get('target_urls', '')
    
    if not ranking_data or not target_urls:
        return jsonify({'error': 'No data provided'}), 400
    
    ranking_data = eval(ranking_data)
    target_urls = eval(target_urls)
    
    csv_filename = get_csv_filename()
    with open(csv_filename, mode="w", newline="") as file:
        writer = csv.writer(file)
        
        # Write header
        writer.writerow(["Keyword"] + target_urls)
        
        # Write data
        writer.writerows(ranking_data)
    
    return jsonify({'filename': csv_filename})

@app.route('/results', methods=['POST'])
def results():
    ranking_data = request.form.get('ranking_data', '')
    target_urls = request.form.get('target_urls', '')
    
    return render_template('results.html', ranking_data=eval(ranking_data), target_urls=eval(target_urls))

# 🔹 Save CSV in the same directory as the script
def get_csv_filename():
    now = datetime.datetime.now()
    script_dir = os.path.dirname(os.path.abspath(__file__))  # Get script directory
    return os.path.join(script_dir, f"rankings_matrix_{now.strftime('%Y-%m-%d_%H-%M')}.csv")

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)