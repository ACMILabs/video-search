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
                    'segments': [{
                        'text': 'A segment',
                        'start': 4,
                    }],
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
