from unittest.mock import patch

from app.video import application

mock_search = {
    'hits': {
        'total': {
            'value': 1,
        },
        'hits': [{
            '_id': 1,
            '_score': 0.9,
            '_source': {
                'title': 'A video',
                'transcription': {
                    'segments': [
                        {
                            'text': 'A segment',
                            'start': 4,
                        },
                        {
                            'text': 'three large elephants',
                            'start': 9,
                        },
                    ],
                },
            },
        }],
    },
}


@patch('app.video.Search.search', return_value=mock_search)
def test_root(_):
    """
    Test the Video search root returns expected content.
    """
    with application.test_client() as client:
        response = client.get('/')
        assert response.status_code == 200
        assert 'Video search' in response.text

        response = client.get('/?query=segment')
        assert response.status_code == 200
        assert 'A video' in response.text
        assert 'A segment' in response.text
        assert 'elephants' not in response.text

        response = client.get('/?query=large+elephants')
        assert response.status_code == 200
        assert 'A video' in response.text
        assert 'A segment' not in response.text
        assert 'three large elephants' in response.text

        response = client.get('/?query=four+large+elephants')
        assert response.status_code == 200
        assert 'A video' in response.text
        assert 'A segment' not in response.text
        assert 'three large elephants' not in response.text
