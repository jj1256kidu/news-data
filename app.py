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
import streamlit as st
import threading
import schedule

# Load spaCy model
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    st.error("Please install the spaCy English language model by running: python -m spacy download en_core_web_sm")
    st.stop()

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
                    pub_date = datetime.strptime(item.pubDate.text, '%a, %d %b %b %Y %H:%M:%S %z')
                    if datetime.now(pub_date.tzinfo) - pub_date <= timedelta(days=1):
                        article = {
                            'title': item.title.text,
                            'link': item.link.text,
                            'published_date': pub_date.isoformat(),
                            'source': item.source.text
                        }
                        articles.append(article)
                except Exception as e:
                    st.warning(f"Error processing article: {e}")
                    continue
            
            return articles
        except Exception as e:
            st.error(f"Error scraping Google News: {e}")
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
                st.warning(f"Error extracting article content: {e}")
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
            st.warning(f"Error finding LinkedIn profile: {e}")
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
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, query in enumerate(queries):
            status_text.text(f"Processing query: {query}")
            articles = self.scrape_google_news(query)
            
            for j, article in enumerate(articles):
                status_text.text(f"Processing article: {article['title']}")
                result = self.process_article(article['link'])
                if result:
                    result['article_info'] = article
                    all_results.append(result)
                time.sleep(1)
                progress_bar.progress((i * len(articles) + j + 1) / (len(queries) * len(articles)))
        
        self.save_results(all_results)
        status_text.text("Scraping completed!")
        progress_bar.empty()

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

# Initialize scraper
scraper = MedTechNewsScraper()

# Streamlit UI
st.set_page_config(page_title="MedTech News Dashboard", layout="wide")
st.title("MedTech News Dashboard")

# Sidebar controls
with st.sidebar:
    st.header("Controls")
    if st.button("Refresh Data"):
        scraper.run_scraper()
    
    st.header("Filters")
    start_date = st.date_input("Start Date")
    end_date = st.date_input("End Date")
    company_filter = st.text_input("Filter by Company")

# Load and filter data
data = load_news_data()
articles = data.get('articles', [])

if start_date and end_date:
    articles = [item for item in articles if 
                start_date <= datetime.fromisoformat(item['article_info']['published_date']).date() <= end_date]

if company_filter:
    articles = [item for item in articles if 
                any(company_filter.lower() in org.lower() for org in item['entities']['ORG'])]

# Display articles
for article in articles:
    with st.container():
        st.markdown(f"### {article['article_info']['title']}")
        st.markdown(f"*Source: {article['article_info']['source']} - {datetime.fromisoformat(article['article_info']['published_date']).strftime('%Y-%m-%d %H:%M')}*")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"[Read Article]({article['article_info']['link']})")
            
            if article['entities']['ORG']:
                st.markdown("**Companies:**")
                for org in article['entities']['ORG']:
                    st.markdown(f"- {org}")
            
            if article['entities']['MONEY']:
                st.markdown("**Funding:**")
                for money in article['entities']['MONEY']:
                    st.markdown(f"- {money}")
            
            if article['emerging_companies']:
                st.markdown("**New Companies:**")
                for company in article['emerging_companies']:
                    st.markdown(f"- {company}")
        
        with col2:
            if article['quotes']:
                st.markdown("**Key Quotes:**")
                for quote in article['quotes']:
                    with st.expander(f"{quote['person']}"):
                        st.markdown(f'"{quote["quote"]}"')
                        if quote['linkedin_profile']:
                            st.markdown(f"[LinkedIn Profile]({quote['linkedin_profile']})")
        
        st.markdown("---")

# Export options
st.sidebar.header("Export")
if st.sidebar.button("Export to CSV"):
    df = pd.json_normalize(articles)
    csv = df.to_csv(index=False)
    st.sidebar.download_button(
        label="Download CSV",
        data=csv,
        file_name="medtech_news.csv",
        mime="text/csv"
    )

if st.sidebar.button("Export to JSON"):
    st.sidebar.download_button(
        label="Download JSON",
        data=json.dumps(articles, indent=2),
        file_name="medtech_news.json",
        mime="application/json"
    )

# Start the scheduler in a separate thread
scheduler_thread = threading.Thread(target=run_scheduled_scraper)
scheduler_thread.daemon = True
scheduler_thread.start()

# Schedule scraper to run every 6 hours
schedule.every(6).hours.do(scraper.run_scraper) 
