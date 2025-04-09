import requests
from newspaper import Article
from bs4 import BeautifulSoup
import spacy
from datetime import datetime
import json
import re
from googlesearch import search
import pandas as pd

# Load spaCy model
nlp = spacy.load("en_core_web_sm")

class MedTechNewsScraper:
    def __init__(self):
        self.known_companies = self._load_known_companies()
        
    def _load_known_companies(self):
        try:
            df = pd.read_csv('known_companies.csv')
            return set(df['company_name'].str.lower())
        except FileNotFoundError:
            return set()
    
    def scrape_google_news(self, query, num_results=10):
        """Scrape Google News search results"""
        url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'xml')
        items = soup.find_all('item')
        
        articles = []
        for item in items[:num_results]:
            article = {
                'title': item.title.text,
                'link': item.link.text,
                'published_date': item.pubDate.text,
                'source': item.source.text
            }
            articles.append(article)
        return articles
    
    def extract_article_content(self, url):
        """Extract full article content using newspaper3k"""
        try:
            article = Article(url)
            article.download()
            article.parse()
            return {
                'text': article.text,
                'authors': article.authors,
                'publish_date': article.publish_date
            }
        except:
            return None
    
    def extract_entities(self, text):
        """Extract named entities using spaCy"""
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
                entities[ent.label_].append(ent.text)
        
        return entities
    
    def extract_quotes(self, text):
        """Extract quotes and their speakers"""
        quotes = []
        # Pattern for finding quotes and speakers
        quote_pattern = r'["\'](.*?)["\']\s*(?:said|stated|announced|commented|explained|added|noted)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'
        matches = re.finditer(quote_pattern, text)
        
        for match in matches:
            quotes.append({
                'quote': match.group(1),
                'person': match.group(2)
            })
        
        return quotes
    
    def find_linkedin_profiles(self, person_name, company_name):
        """Search for LinkedIn profiles using Google search"""
        query = f'"{person_name} {company_name}" site:linkedin.com/in'
        try:
            results = list(search(query, num_results=1, stop=1))
            return results[0] if results else None
        except:
            return None
    
    def detect_emerging_companies(self, entities):
        """Detect potential emerging companies"""
        emerging_companies = []
        for company in entities['ORG']:
            if company.lower() not in self.known_companies:
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
        
        # Find LinkedIn profiles for quoted people
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
        """Save results to JSON file"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    scraper = MedTechNewsScraper()
    queries = [
        "MedTech",
        "medical devices",
        "digital health",
        "healthcare technology",
        "medical innovation"
    ]
    
    all_results = []
    for query in queries:
        articles = scraper.scraper.scrape_google_news(query)
        for article in articles:
            result = scraper.process_article(article['link'])
            if result:
                result['article_info'] = article
                all_results.append(result)
    
    scraper.save_results(all_results) 
