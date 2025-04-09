from flask import Flask, render_template, jsonify, request
import json
from datetime import datetime
import os

app = Flask(__name__)

def load_news_data():
    try:
        with open('medtech_news.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/news')
def get_news():
    data = load_news_data()
    
    # Filter by date if provided
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    if start_date and end_date:
        data = [item for item in data if 
                start_date <= item['article_info']['published_date'] <= end_date]
    
    # Filter by company if provided
    company = request.args.get('company')
    if company:
        data = [item for item in data if 
                any(company.lower() in org.lower() for org in item['entities']['ORG'])]
    
    return jsonify(data)

@app.route('/api/export')
def export_data():
    data = load_news_data()
    format_type = request.args.get('format', 'json')
    
    if format_type == 'csv':
        # Convert to CSV format
        import pandas as pd
        df = pd.json_normalize(data)
        return df.to_csv(index=False)
    else:
        return jsonify(data)

if __name__ == '__main__':
    app.run(debug=True) 
