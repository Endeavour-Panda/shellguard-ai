"""Public, credential-free QR for the URL currently open in the browser."""

from io import BytesIO
from urllib.parse import urlsplit, urlunsplit

from fastapi import FastAPI, Request
from fastapi.responses import Response
import qrcode
import qrcode.image.svg


MOBILE_LOGIN_HTML = """
<style>
.sg-mobile-login { position:relative; display:inline-block; text-align:center; margin:10px 0; font-family:system-ui,sans-serif; }
.sg-mobile-login summary { list-style:none; cursor:pointer; color:#087f8c; font-size:14px; font-weight:650; padding:9px 18px; border:1px solid #087f8c40; border-radius:9px; background:#e8f6f5; }
.sg-mobile-login summary::-webkit-details-marker { display:none; }
.sg-mobile-login summary:focus-visible { outline:2px solid #087f8c; outline-offset:3px; }
.sg-mobile-qr { display:none; position:absolute; top:100%; left:50%; transform:translateX(-50%); width:232px; max-width:80vw; box-sizing:border-box; padding:14px; background:#fff; color:#203449; border:1px solid #dce6ee; border-radius:12px; box-shadow:0 12px 36px #10263c28; z-index:1000; }
.sg-mobile-login:hover .sg-mobile-qr, .sg-mobile-toggle[open] + .sg-mobile-qr, .sg-mobile-login:focus-within .sg-mobile-qr { display:block; }
.sg-mobile-qr img { display:block; width:200px; max-width:100%; height:auto; margin:0 auto 8px; background:white; }
.sg-mobile-qr p { margin:5px 0; line-height:1.5; font-size:12px; color:#52657a; }
</style>
<div class="sg-mobile-login">
  <details class="sg-mobile-toggle"><summary>手机端登录</summary></details>
  <div class="sg-mobile-qr">
    <img src="./mobile-login-qr.svg" alt="使用手机扫描，打开当前 ShellGuard AI 页面" width="200" height="200">
    <p><strong>手机扫码打开当前页面</strong></p>
    <p>扫码后仍需账号登录；也可注册新账号。</p>
    <p>二维码随当前访问地址生成。</p>
  </div>
</div>
"""


def mobile_login_url(request: Request) -> str:
    # A same-origin image request carries the actual browser URL in Referer,
    # including the public Gradio hostname even behind the share tunnel.
    referer = request.headers.get("referer", "")
    try:
        parsed = urlsplit(referer)
    except ValueError:
        parsed = urlsplit("")
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
        parsed = urlsplit(str(request.base_url))
    # Strip query/fragment (which might contain tokens) and login/register paths.
    prefix = request.scope.get("root_path", "").rstrip("/")
    return urlunsplit((parsed.scheme, parsed.netloc, prefix + "/", "", ""))


def register_mobile_login_routes(app: FastAPI) -> None:
    @app.get("/mobile-login-qr.svg", include_in_schema=False)
    async def mobile_qr(request: Request) -> Response:
        qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=4)
        qr.add_data(mobile_login_url(request))
        qr.make(fit=True)
        output = BytesIO()
        qr.make_image(image_factory=qrcode.image.svg.SvgPathImage).save(output)
        return Response(output.getvalue(), media_type="image/svg+xml", headers={
            "Cache-Control": "no-store", "Vary": "Referer, Host", "X-Content-Type-Options": "nosniff",
        })
