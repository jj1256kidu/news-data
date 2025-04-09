# MedTech News Dashboard

A real-time dashboard for monitoring MedTech industry activity, including news, key people, quotes, LinkedIn profiles, emerging startups, and funding events.

## Features

- Real-time news scraping from Google News
- Entity extraction (people, companies, funding amounts, dates, locations)
- Quote extraction with speaker identification
- LinkedIn profile lookup
- Emerging company detection
- Modern, responsive dashboard UI
- Export capabilities (CSV/JSON)
- Date and company filtering

## Setup

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Download spaCy model:
```bash
python -m spacy download en_core_web_sm
```

3. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

## Usage

1. Run the news scraper to collect data:
```bash
python news_scraper.py
```

2. Start the Flask application:
```bash
python app.py
```

3. Open your browser and navigate to:
```
http://localhost:5000
```

## Project Structure

- `news_scraper.py`: Main scraper module for collecting and processing news
- `app.py`: Flask web application
- `templates/index.html`: Dashboard UI
- `known_companies.csv`: List of established MedTech companies
- `medtech_news.json`: Generated news data file

## Automation

For automated daily updates, you can set up a scheduled task:

### Windows
1. Open Task Scheduler
2. Create a new task
3. Set trigger to daily
4. Action: `python news_scraper.py`

### Linux/Mac
Add to crontab:
```bash
0 0 * * * python /path/to/news_scraper.py
```

## Contributing

Feel free to submit issues and enhancement requests!

## License

MIT License 
