import requests
from newspaper import Article
from bs4 import BeautifulSoup
import spacy
from datetime import datetime, timedelta
import json
import re
from googlesearch import search
import pandas as pd
import time
from urllib.parse import quote_plus
from flask import Flask, render_template, jsonify, request
import threading
import schedule

# Load spaCy model
nlp = spacy.load("en_core_web_sm")

class MedTechNewsScraper:
    def __init__(self):
        self.known_companies = self._load_known_companies()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
    def _load_known_companies(self):
        try:
            df = pd.read_csv('known_companies.csv')
            return set(df['company_name'].str.lower())
        except FileNotFoundError:
            return set()
    
    def scrape_google_news(self, query, num_results=20):
        """Scrape Google News search results with improved error handling"""
        try:
            encoded_query = quote_plus(query)
            url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
            
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'xml')
            items = soup.find_all('item')
            
            articles = []
            for item in items[:num_results]:
                try:
                    pub_date = datetime.strptime(item.pubDate.text, '%a, %d %b %Y %H:%M:%S %z')
                    if datetime.now(pub_date.tzinfo) - pub_date <= timedelta(days=1):
                        article = {
                            'title': item.title.text,
                            'link': item.link.text,
                            'published_date': pub_date.isoformat(),
                            'source': item.source.text
                        }
                        articles.append(article)
                except Exception as e:
                    print(f"Error processing article: {e}")
                    continue
            
            return articles
        except Exception as e:
            print(f"Error scraping Google News: {e}")
            return []
    
    def extract_article_content(self, url):
        """Extract full article content using newspaper3k with retries"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                article = Article(url)
                article.download()
                article.parse()
                return {
                    'text': article.text,
                    'authors': article.authors,
                    'publish_date': article.publish_date
                }
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                print(f"Error extracting article content: {e}")
                return None
    
    def extract_entities(self, text):
        """Extract named entities using spaCy with improved accuracy"""
        doc = nlp(text)
        entities = {
            'PERSON': [],
            'ORG': [],
            'MONEY': [],
            'DATE': [],
            'GPE': []
        }
        
        for ent in doc.ents:
            if ent.label_ in entities:
                if ent.text not in entities[ent.label_]:
                    entities[ent.label_].append(ent.text)
        
        return entities
    
    def extract_quotes(self, text):
        """Extract quotes and their speakers with improved pattern matching"""
        quotes = []
        patterns = [
            r'["\'](.*?)["\']\s*(?:said|stated|announced|commented|explained|added|noted)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:said|stated|announced|commented|explained|added|noted)\s+["\'](.*?)["\']'
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                if pattern == patterns[0]:
                    quote, person = match.group(1), match.group(2)
                else:
                    person, quote = match.group(1), match.group(2)
                
                quote = quote.strip()
                if len(quote) > 20:
                    quotes.append({
                        'quote': quote,
                        'person': person
                    })
        
        return quotes
    
    def find_linkedin_profiles(self, person_name, company_name):
        """Search for LinkedIn profiles using Google search with improved accuracy"""
        query = f'"{person_name} {company_name}" site:linkedin.com/in'
        try:
            results = list(search(query, num_results=1, stop=1))
            return results[0] if results else None
        except Exception as e:
            print(f"Error finding LinkedIn profile: {e}")
            return None
    
    def detect_emerging_companies(self, entities):
        """Detect potential emerging companies with improved filtering"""
        emerging_companies = []
        for company in entities['ORG']:
            if (company.lower() not in self.known_companies and 
                len(company) > 3 and 
                not any(word in company.lower() for word in ['inc', 'llc', 'ltd', 'corp'])):
                emerging_companies.append(company)
        return emerging_companies
    
    def process_article(self, article_url):
        """Process a single article and extract all relevant information"""
        content = self.extract_article_content(article_url)
        if not content:
            return None
        
        entities = self.extract_entities(content['text'])
        quotes = self.extract_quotes(content['text'])
        emerging_companies = self.detect_emerging_companies(entities)
        
        for quote in quotes:
            linkedin_profile = self.find_linkedin_profiles(quote['person'], entities['ORG'][0] if entities['ORG'] else '')
            quote['linkedin_profile'] = linkedin_profile
        
        return {
            'content': content,
            'entities': entities,
            'quotes': quotes,
            'emerging_companies': emerging_companies
        }
    
    def save_results(self, results, filename='medtech_news.json'):
        """Save results to JSON file with timestamp"""
        data = {
            'last_updated': datetime.now().isoformat(),
            'articles': results
        }
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def run_scraper(self):
        """Run the scraper and save results"""
        queries = [
            "MedTech",
            "medical devices",
            "digital health",
            "healthcare technology",
            "medical innovation",
            "healthcare startup",
            "medical device funding",
            "health tech investment"
        ]
        
        all_results = []
        for query in queries:
            print(f"Processing query: {query}")
            articles = self.scrape_google_news(query)
            for article in articles:
                print(f"Processing article: {article['title']}")
                result = self.process_article(article['link'])
                if result:
                    result['article_info'] = article
                    all_results.append(result)
                time.sleep(1)
        
        self.save_results(all_results)

# Initialize Flask app and scraper
app = Flask(__name__)
scraper = MedTechNewsScraper()

def load_news_data():
    try:
        with open('medtech_news.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {'articles': []}

def run_scheduled_scraper():
    """Run the scraper on a schedule"""
    while True:
        schedule.run_pending()
        time.sleep(60)

# Schedule scraper to run every 6 hours
schedule.every(6).hours.do(scraper.run_scraper)

# Start the scheduler in a separate thread
scheduler_thread = threading.Thread(target=run_scheduled_scraper)
scheduler_thread.daemon = True
scheduler_thread.start()

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
        data['articles'] = [item for item in data['articles'] if 
                start_date <= item['article_info']['published_date'] <= end_date]
    
    # Filter by company if provided
    company = request.args.get('company')
    if company:
        data['articles'] = [item for item in data['articles'] if 
                any(company.lower() in org.lower() for org in item['entities']['ORG'])]
    
    return jsonify(data)

@app.route('/api/export')
def export_data():
    data = load_news_data()
    format_type = request.args.get('format', 'json')
    
    if format_type == 'csv':
        import pandas as pd
        df = pd.json_normalize(data['articles'])
        return df.to_csv(index=False)
    else:
        return jsonify(data)

@app.route('/api/refresh')
def refresh_data():
    """Manual trigger to refresh the data"""
    scraper.run_scraper()
    return jsonify({'status': 'success', 'message': 'Data refreshed successfully'})

if __name__ == '__main__':
    # Run initial scrape
    scraper.run_scraper()
    # Start Flask app
    app.run(debug=True) 
