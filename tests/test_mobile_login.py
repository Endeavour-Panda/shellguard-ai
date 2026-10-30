import fastapi
from fastapi.testclient import TestClient
from starlette.requests import Request

from src.mobile_login import MOBILE_LOGIN_HTML, mobile_login_url, register_mobile_login_routes


def request(referer="", root_path=""):
    return Request({"type": "http", "scheme": "http", "server": ("127.0.0.1", 6006),
                    "path": "/mobile-login-qr.svg", "root_path": root_path,
                    "headers": [(b"host", b"127.0.0.1:6006"), (b"referer", referer.encode())]})


def test_public_tunnel_url_and_rotated_hostname():
    for host in ["a0629c5b89aa97487b.gradio.live", "new-address.gradio.live"]:
        assert mobile_login_url(request(f"https://{host}/?token=secret#private")) == f"https://{host}/"


def test_registration_and_proxy_prefix_point_to_login_root():
    assert mobile_login_url(request("https://example.com/register")) == "https://example.com/"
    assert mobile_login_url(request("https://example.com/app/register", "/app")) == "https://example.com/app/"


def test_missing_invalid_or_credentialed_referer_uses_request_url():
    for value in ["", "javascript:alert(1)", "https://user:password@example.com/", "https://[broken"]:
        assert mobile_login_url(request(value)) == "http://127.0.0.1:6006/"


def test_qr_route_is_public_and_uncached():
    app = fastapi.FastAPI()
    register_mobile_login_routes(app)
    response = TestClient(app).get('/mobile-login-qr.svg', headers={"referer": "https://new.gradio.live/"})
    assert response.status_code == 200
    assert response.headers['content-type'].startswith('image/svg+xml')
    assert response.headers['cache-control'] == 'no-store'
    assert '<svg' in response.text and '<path' in response.text


def test_widget_supports_hover_touch_and_keyboard_without_external_service():
    assert '<details' in MOBILE_LOGIN_HTML and '<summary>手机端登录</summary>' in MOBILE_LOGIN_HTML
    assert ':hover' in MOBILE_LOGIN_HTML and ':focus-within' in MOBILE_LOGIN_HTML
    assert 'src="./mobile-login-qr.svg"' in MOBILE_LOGIN_HTML
    assert 'http://' not in MOBILE_LOGIN_HTML and 'https://' not in MOBILE_LOGIN_HTML
