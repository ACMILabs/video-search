import json
import os
import re
import statistics
from collections import Counter
from math import exp, floor
from pathlib import Path

import elasticsearch
import requests
from elasticsearch import Elasticsearch
from flask import Flask, render_template, request

from app.utils import STOPWORDS

DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'
XOS_API_ENDPOINT = os.getenv('XOS_API_ENDPOINT', None)
XOS_API_TOKEN = os.getenv('XOS_API_TOKEN', None)
XOS_RETRIES = int(os.getenv('XOS_RETRIES', '3'))
XOS_TIMEOUT = int(os.getenv('XOS_TIMEOUT', '60'))
ELASTICSEARCH_HOST = os.getenv('ELASTICSEARCH_HOST', 'http://video-search:9200')
ELASTICSEARCH_CLOUD_ID = os.getenv('ELASTICSEARCH_CLOUD_ID')
ELASTICSEARCH_API_KEY = os.getenv('ELASTICSEARCH_API_KEY')
ELASTICSEARCH_INDEX_NAME = os.getenv('ELASTICSEARCH_INDEX_NAME', None)
PORT = int(os.getenv('PORT', '8081'))
EXPORT_VIDEO_JSON = os.getenv('EXPORT_VIDEO_JSON', 'false').lower() == 'true'
REMOVE_QUERY_PARAMS = os.getenv('REMOVE_QUERY_PARAMS', 'false').lower() == 'true'
EXAMPLES = os.getenv('EXAMPLES', None)

application = Flask(__name__)
application.config['TEMPLATES_AUTO_RELOAD'] = DEBUG


@application.route('/')
def home():
    """
    Video search home page.
    """
    results = None
    errors = None
    examples = EXAMPLES or []
    args = request.args.copy()
    query = request.args.get('query', None)
    size = args.get('size', type=int, default=20)
    page = args.get('page', type=int, default=1)
    search_type = request.args.get('searchType', 'audio')

    if query:
        query = sanitise_string(query)
        args['query'] = query
        search = Search()
        results, errors = search.search(args)

    if EXAMPLES:
        examples = examples.strip().split(',')

    return render_template(
        'index.html',
        query=query,
        results=results,
        search_type=search_type,
        size=size,
        page=page,
        errors=errors,
        examples=examples,
    )


@application.route('/videos/<video_id>/')
def video_detail(video_id):
    """
    Video detail page.
    """
    search = Search()
    video = search.get_video(video_id)

    return render_template(
        'detail.html',
        video=video,
        export_json=EXPORT_VIDEO_JSON,
    )


@application.template_filter('tags_json_to_string')
def tags_json_to_string(tags):
    """
    Converts a JSON dictionary of tag data to a formatted string.
    Input: {"music": 69, "frog": 26, "water": 18}
    Output: music (69), frog (26), water (18)
    """
    tags = json.loads(tags)
    return ', '.join([f'{key} ({tags[key]})' for key in tags.keys() if key])


@application.template_filter('tags_list_to_string')
def tags_list_to_string(tags):
    """
    Converts a list of tag data to a formatted string.
    Input: [("music", 69), ("frog", 26), ("water", 18)]
    Output: music (69), frog (26), water (18)
    """
    return ', '.join([f'{item[0]} ({item[1]})' for item in tags if item])


@application.template_filter('seconds_to_timecode')
def seconds_to_timecode_filter(seconds):
    """
    Converts an integer of seconds into timecode format.
    """
    timecode_seconds = str(floor(seconds % 60))
    timecode_minutes = str(floor((seconds / 60) % 60))
    timecode_hours = str(floor(seconds / 60 / 60))
    timecode_seconds = pad_with_leading_zero(timecode_seconds)
    timecode_minutes = pad_with_leading_zero(timecode_minutes)
    timecode_hours = pad_with_leading_zero(timecode_hours)
    return f'{timecode_hours}:{timecode_minutes}:{timecode_seconds}'


@application.template_filter('float_to_percentage')
def float_to_percentage_filter(confidence):
    """
    Converts a confidence level float into a percentage.
    """
    return int(confidence * 100)


@application.template_filter('average_log_probability_to_percentage')
def average_log_probability_to_percentage_filter(avg_logprob):
    """
    Converts an average log probability into a percentage.
    """
    return float_to_percentage_filter(exp(avg_logprob))


@application.template_filter('calculate_prediction_counts')
def calculate_prediction_counts_filter(predictions, score=0.0):
    """
    Calculate the total occurrences of each prediction for this video.

    Returns:
        A list of touples of format: [(prediction label, count, average confidence)]
    """
    prediction_text = []
    return_list = []
    for frame in predictions:
        if frame.get('predictions'):
            for prediction in frame.get('predictions'):
                if prediction['confidence'] > score:
                    prediction_text.append(prediction['prediction'])
    most_common = dict(Counter(prediction_text).most_common())
    for item in most_common.items():
        scores = []
        for frame in predictions:
            if frame.get('predictions'):
                for prediction in frame.get('predictions'):
                    if item[0] == prediction['prediction'] and prediction['confidence'] > score:
                        scores.append(prediction['confidence'])
        return_list.append((item[0], item[1], round(statistics.mean(scores), 2)))
    return return_list


@application.template_filter('get_common_words_from_text')
def get_common_words_from_text(text, number=50):
    """
    Returns a list of tuples containing the most common word and how many times it appears.
    """
    tags = None
    try:
        text = str(text)
        words = [word.lower() for word in text.split(' ')]

        # Remove non-alphabetical characters
        regex = re.compile('[^a-zA-Z]')
        words = [regex.sub('', word) for word in words]

        # Filter out stopwords
        words = list(filter(lambda word: word not in STOPWORDS, words))
        tags = Counter(words).most_common(number)
    except TypeError:
        pass
    return tags


def pad_with_leading_zero(number):
    """
    Add leading zeros to a single digit number.
    """
    padded_number = number
    if len(str(padded_number)) == 1:
        padded_number = f'0{padded_number}'
    return padded_number


def sanitise_string(input_string):
    """
    Replace any character that is not a-z, 0-9, or ' with an empty string.
    """
    sanitized_string = re.sub(r"[^a-z0-9,' ]", '', input_string.lower())
    return sanitized_string


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
        search_results = None
        errors = None
        query = args.get('query')
        field = args.get('field', 'transcription.segments.text')
        size = args.get('size', type=int, default=20)
        page = args.get('page', type=int, default=1)
        search_type = args.get('searchType', 'audio')
        if search_type == 'image':
            field = 'classification.captions.huggingface.predictions.prediction'
        elif search_type == 'audioDescription':
            field = 'classification.captions.clap.predictions.prediction'
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

        query_body['query'] = {
            'match_phrase': {
                field: query,
            }
        }
        try:
            search_results = self.elastic_search.search(
                index=ELASTICSEARCH_INDEX_NAME or resource,
                body=query_body,
            )
        except elasticsearch.NotFoundError as exception:
            print(f'ERROR: {exception}')
            errors = exception

        return search_results, errors

    def get_video(self, video_id, resource='videos'):
        """
        Get a Video by its ID.
        """
        return self.elastic_search.search(
            index=ELASTICSEARCH_INDEX_NAME or resource,
            body={'query': {'match_phrase': {'id': video_id}}}
        )['hits']['hits'][0]

    def index(self, resource, json_data):
        """
        Update the search index for a single record.
        """
        success = False

        # Handle tags
        tags_dictionary = {}
        for tag in json_data.get('tags') or []:
            tags_dictionary[tag[0]] = tag[1]
        json_data['tags'] = json.dumps(tags_dictionary)

        if REMOVE_QUERY_PARAMS:
            # Remove the query params from resource URLs if they're in a public S3 bucket
            if json_data.get('resource'):
                json_data['resource'] = json_data['resource'].split('?')[0]
            if json_data.get('web_resource'):
                json_data['web_resource'] = json_data['web_resource'].split('?')[0]
            if json_data.get('subtitles'):
                json_data['subtitles'] = json_data['subtitles'].split('?')[0]
            if json_data.get('subtitles_vtt'):
                json_data['subtitles_vtt'] = json_data['subtitles_vtt'].split('?')[0]
            if json_data.get('snapshot'):
                json_data['snapshot'] = json_data['snapshot'].split('?')[0]

        if EXPORT_VIDEO_JSON:
            self.export_video_json(json_data)

        try:
            self.elastic_search.index(
                index=ELASTICSEARCH_INDEX_NAME or resource,
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
                if result['transcription'] or result['classification']:
                    if not self.index(resource, result):
                        failed.append(result['id'])
            page += 1
            next_page = response['next']
        if failed:
            print(f'Finished. Failed {len(failed)}: {failed}')

    def export_video_json(self, json_data):
        """
        Save the json_data to the file system using the filename as the title.
        """
        Path('app/static/json').mkdir(exist_ok=True)
        title = json_data.get('title') or json_data.get('id')
        with open(f'app/static/json/{title}.json', 'w', encoding='utf-8') as video_file:
            json.dump(json_data, video_file, ensure_ascii=False, indent=4)


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
        port=PORT,
        debug=DEBUG,
    )
