"""Deployment integration checks without any Gemini requests."""
from fastapi.testclient import TestClient
from config import Settings
from main import create_app


def test_allowed_netlify_origin_can_read_health_and_post():
    origin = 'https://cvboost-test.netlify.app'
    settings = Settings(_env_file=None, gemini_api_key='', allowed_origins=[origin])
    with TestClient(create_app(settings)) as client:
        health = client.get('/api/health', headers={'Origin': origin})
        assert health.status_code == 200
        assert health.headers['access-control-allow-origin'] == origin
        preflight = client.options('/api/analyze', headers={
            'Origin': origin, 'Access-Control-Request-Method': 'POST',
            'Access-Control-Request-Headers': 'content-type'})
        assert preflight.status_code == 200
        assert preflight.headers['access-control-allow-origin'] == origin


def test_other_origin_is_not_granted_cors_access():
    settings = Settings(_env_file=None, gemini_api_key='',
                        allowed_origins=['https://cvboost-test.netlify.app'])
    with TestClient(create_app(settings)) as client:
        response = client.options('/api/analyze', headers={
            'Origin': 'https://unrelated.example', 'Access-Control-Request-Method': 'POST'})
        assert response.status_code == 400
        assert 'access-control-allow-origin' not in response.headers


def test_secret_paths_are_not_static_routes():
    with TestClient(create_app(Settings(_env_file=None, gemini_api_key=''))) as client:
        for path in ['/.env', '/.git/config', '/config.py']:
            assert client.get(path).status_code == 404
