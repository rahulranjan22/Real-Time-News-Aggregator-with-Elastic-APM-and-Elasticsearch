import requests
from elasticsearch import Elasticsearch, helpers
import os
import json
from datetime import datetime
import schedule
import time
import logging
import elasticapm
from elasticapm import Client

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Get environment variables
NEWS_API_KEY = os.getenv('NEWS_API_KEY')
ELASTICSEARCH_HOST = os.getenv('ELASTICSEARCH_HOST')
ELASTICSEARCH_USERNAME = os.getenv('ELASTICSEARCH_USERNAME')
ELASTICSEARCH_PASSWORD = os.getenv('ELASTICSEARCH_PASSWORD')
APM_SERVER_URL = os.getenv('ELASTIC_APM_SERVER_URL')
APM_SECRET_TOKEN = os.getenv('ELASTIC_APM_SECRET_TOKEN')

# Set up Elasticsearch client
es = Elasticsearch(
    [ELASTICSEARCH_HOST],
    basic_auth=(ELASTICSEARCH_USERNAME, ELASTICSEARCH_PASSWORD)
)

# Initialize Elastic APM client
apm_client = Client({
    'SERVICE_NAME': 'rranjan-news-aggregator',
    'SECRET_TOKEN': APM_SECRET_TOKEN,
    'SERVER_URL': APM_SERVER_URL,
    'ENVIRONMENT': 'production',  # Adjust environment name as needed
    'FLUSH_INTERVAL': 60  # Flush interval in seconds
})

# Attach the APM client to the current application
elasticapm.instrument()

def check_es_connection():
    with elasticapm.capture_span('Check Elasticsearch Connection'):
        try:
            if es.ping():
                logger.info("Successfully connected to Elasticsearch.")
            else:
                logger.error("Failed to connect to Elasticsearch.")
        except Exception as e:
            logger.error(f"Error connecting to Elasticsearch: {e}")

def fetch_news_data(page=1):
    with elasticapm.capture_span('Fetch News Data'):
        try:
            url = f'https://newsapi.org/v2/top-headlines?country=us&page={page}&apiKey={NEWS_API_KEY}'
            logger.debug(f"Fetching news data from URL: {url}")
            response = requests.get(url)
            if response.status_code == 200:
                logger.debug("News data fetched successfully.")
                return response.json()
            else:
                logger.error(f"Failed to fetch news data. Status code: {response.status_code}")
                return {}
        except Exception as e:
            logger.error(f"Error fetching news data: {e}")

def process_and_index(data):
    with elasticapm.capture_span('Process and Index Data'):
        try:
            actions = []
            for article in data.get('articles', []):
                try:
                    article_id = article['url']
                    if len(article_id) > 512:
                        article_id = article_id[:512]  # Truncate to 512 bytes
                    action = {
                        "_index": "news",
                        "_id": article_id,
                        "_source": {
                            "title": article.get('title'),
                            "description": article.get('description'),
                            "content": article.get('content'),
                            "publishedAt": article.get('publishedAt'),
                            "author": article.get('author'),
                            "url": article.get('url'),
                            "source": article.get('source', {}).get('name'),
                            "category": 'general',  # Add your own category logic
                            "timestamp": datetime.strptime(article.get('publishedAt', ''), "%Y-%m-%dT%H:%M:%SZ")
                        }
                    }
                    actions.append(action)
                except Exception as e:
                    logger.error(f"Error processing article: {e}")

            if actions:
                with elasticapm.capture_span('Index Articles'):
                    try:
                        helpers.bulk(es, actions)
                        logger.info(f"Indexed {len(actions)} articles.")
                    except Exception as e:
                        logger.error(f"Error indexing articles: {e}")
        except Exception as e:
            logger.error(f"Error processing and indexing data: {e}")

def fetch_and_index_news():
    with elasticapm.capture_span('Fetch and Index News'):
        try:
            logger.debug("Starting news fetch and index process...")
            page = 1
            while True:
                logger.debug(f"Fetching news data for page {page}...")
                data = fetch_news_data(page)
                if data and 'articles' in data and data['articles']:
                    process_and_index(data)
                    page += 1
                else:
                    logger.info("No more data to index or no articles returned.")
                    break
            logger.debug("Completed news fetch and index process.")
        except Exception as e:
            logger.error(f"Error in fetch and index process: {e}")

# Schedule the fetch_and_index_news function to run every 10 minutes
schedule.every(10).minutes.do(fetch_and_index_news)

if __name__ == "__main__":
    logger.info("Starting news streaming...")
    fetch_and_index_news()  # Initial run
    while True:
        schedule.run_pending()
        time.sleep(1)
