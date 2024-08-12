from flask import Flask, render_template, jsonify, request
from elasticsearch import Elasticsearch
import os
import elasticapm
from elasticapm.contrib.flask import ElasticAPM

app = Flask(__name__)

# Initialize Elastic APM client
app.config['ELASTIC_APM'] = {
    'SERVICE_NAME': 'rranjan-flask-ui',
    'SECRET_TOKEN': '',
    'SERVER_URL': '',
    'ENVIRONMENT': 'php',
}
apm = ElasticAPM(app)

# Get environment variables
ELASTICSEARCH_HOST = os.getenv('ELASTICSEARCH_HOST')
ELASTICSEARCH_USERNAME = os.getenv('ELASTICSEARCH_USERNAME')
ELASTICSEARCH_PASSWORD = os.getenv('ELASTICSEARCH_PASSWORD')

# Set up Elasticsearch client
es = Elasticsearch(
    [ELASTICSEARCH_HOST],
    basic_auth=(ELASTICSEARCH_USERNAME, ELASTICSEARCH_PASSWORD)
)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/news')
def get_news():
    # Get pagination parameters from query string
    page = int(request.args.get('page', 0))
    size = int(request.args.get('size', 100))
    
    query = {
        "query": {
            "match_all": {}
        },
        "sort": [
            {
                "timestamp": {
                    "order": "desc"
                }
            }
        ],
        "from": page * size,
        "size": size
    }
    
    response = es.search(index="news", body=query)
    articles = [hit['_source'] for hit in response['hits']['hits']]
    return jsonify(articles)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5001, debug=True)
