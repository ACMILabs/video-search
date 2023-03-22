import json
import os
from math import floor

import elasticsearch
import requests
from elasticsearch import Elasticsearch
from flask import Flask, render_template, request

DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'
XOS_API_ENDPOINT = os.getenv('XOS_API_ENDPOINT', None)
XOS_API_TOKEN = os.getenv('XOS_API_TOKEN', None)
XOS_RETRIES = int(os.getenv('XOS_RETRIES', '3'))
XOS_TIMEOUT = int(os.getenv('XOS_TIMEOUT', '60'))
ELASTICSEARCH_HOST = os.getenv('ELASTICSEARCH_HOST', 'http://video-search:9200')
ELASTICSEARCH_CLOUD_ID = os.getenv('ELASTICSEARCH_CLOUD_ID')
ELASTICSEARCH_API_KEY = os.getenv('ELASTICSEARCH_API_KEY')

application = Flask(__name__)


@application.route('/')
def home():
    """
    Video search home page.
    """
    results = None
    args = request.args.copy()
    field = request.args.get('field', None)
    if not field:
        args['field'] = 'transcription.segments.text'
    query = request.args.get('query', None)

    if query:
        search = Search()
        results = search.search(args)

    return render_template(
        'index.html',
        query=query,
        results=results,
    )


@application.template_filter('seconds_to_timecode')
def seconds_to_timecode_filter(seconds):
    timecode_seconds = str(floor(seconds % 60))
    timecode_minutes = str(floor((seconds / 60) % 60))
    timecode_hours = str(floor(seconds / 60 / 60))
    timecode_seconds = pad_with_leading_zero(timecode_seconds)
    timecode_minutes = pad_with_leading_zero(timecode_minutes)
    timecode_hours = pad_with_leading_zero(timecode_hours)
    return f'{timecode_hours}:{timecode_minutes}:{timecode_seconds}'


def pad_with_leading_zero(number):
    padded_number = number
    if len(str(padded_number)) == 1:
        padded_number = f'0{padded_number}'
    return padded_number


class Search():
    """
    Elasticsearch interface.
    """
    def __init__(self):
        if DEBUG:
            self.elastic_search = Elasticsearch(
                ELASTICSEARCH_HOST,
            )
        else:
            self.elastic_search = Elasticsearch(
                cloud_id=ELASTICSEARCH_CLOUD_ID,
                api_key=ELASTICSEARCH_API_KEY,
            )

    def search(self, args, resource='videos'):
        """
        Perform a search for a query string in the index (resource).
        """
        query_body = {}
        query = args.get('query')
        field = args.get('field')
        size = args.get('size', type=int, default=20)
        page = args.get('page', type=int, default=1)
        # Limit search results per page to 50
        size = min(size, 50)
        query_body['size'] = size

        # Elasticsearch uses `from` to specify page of results
        # e.g. Page 1 = from 0
        if page == 1:
            page = 0
        else:
            page = (page - 1) * size
        query_body['from'] = page

        if field:
            query_body['query'] = {
                'match_phrase_prefix': {
                    field: query,
                }
            }
            search_results = self.elastic_search.search(index=resource, body=query_body)
        else:
            search_results = self.elastic_search.search(  # pylint: disable=unexpected-keyword-arg
                index=resource,
                q=query,
                params=query_body,
            )

        return search_results

    def index(self, resource, json_data):
        """
        Update the search index for a single record.
        """
        success = False

        # Handle tags
        tags_dictionary = {}
        for tag in json_data.get('tags'):
            tags_dictionary[tag[0]] = tag[1]
        json_data['tags'] = json.dumps(tags_dictionary)
        try:
            self.elastic_search.index(
                index=resource,
                id=json_data.get('id'),
                body=json_data,
            )
            success = True
            return success
        except (
            elasticsearch.exceptions.RequestError,
            elasticsearch.exceptions.ConnectionTimeout,
            elasticsearch.exceptions.ConnectionError,
        ) as exception:
            print(f'ERROR indexing {json_data.get("id")}: {exception}')
            return success

    def index_all(self, resource='videos'):
        """
        Index all of the objects for this resource.
        """
        client = XOSAPI()
        failed = []

        next_page = True
        page = 1
        api = None

        if resource == 'videos':
            api = 'assets'

        while next_page:
            print(f'Starting page {page}')
            params = {
                'page': page,
                'page_size': 100,
            }
            response = client.get(resource=api, params=params).json()
            for result in response['results']:
                if result['transcription']:
                    if not self.index(resource, result):
                        failed.append(result['id'])
            page += 1
            next_page = response['next']
        if failed:
            print(f'Finished. Failed {len(failed)}: {failed}')


class XOSAPI():  # pylint: disable=too-few-public-methods
    """
    XOS private API interface.
    """
    def __init__(self):
        self.uri = XOS_API_ENDPOINT
        self.headers = {
            'Content-Type': 'application/json',
        }
        self.params = {
            'page_size': 10,
        }

    def get(self, resource, params=None):
        """
        Returns JSON for this resource.
        """
        endpoint = os.path.join(self.uri, f'{resource}/')
        if not params:
            params = self.params.copy()
        if XOS_API_TOKEN:
            self.headers['Authorization'] = f'Token {XOS_API_TOKEN}'
        retries = 0
        while retries < XOS_RETRIES:
            try:
                response = requests.get(
                    url=endpoint,
                    headers=self.headers,
                    params=params,
                    timeout=XOS_TIMEOUT,
                )
                response.raise_for_status()
                return response
            except (
                requests.exceptions.HTTPError,
                requests.exceptions.ConnectionError,
                requests.exceptions.ReadTimeout,
            ) as exception:
                print(
                    f'ERROR: couldn\'t get {endpoint} with params: {params}, '
                    f'exception: {exception}... retrying',
                )
                retries += 1
                if retries == XOS_RETRIES:
                    raise exception
        return None


if __name__ == '__main__':
    application.run(
        host='0.0.0.0',
        port=8081,
        debug=DEBUG,
    )
