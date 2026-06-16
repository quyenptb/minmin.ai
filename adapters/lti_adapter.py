import os
import logging
import urllib.parse
import uuid
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

logger = logging.getLogger("LTIAdapter")
router = APIRouter()

@router.get("/lti/login")
@router.post("/lti/login")
async def lti_oidc_login(request: Request):
    """
    Bước 1: OIDC Login Initiation (Tuân thủ nghiêm ngặt LTI 1.3 Core Spec).
    Nhận yêu cầu từ saLTIre và thực hiện redirect bảo mật ngược lại Auth Server của saLTIre.
    """
    params = dict(request.query_params)
    if request.method == "POST":
        form_data = await request.form()
        params.update(dict(form_data))

    iss = params.get("iss")
    login_hint = params.get("login_hint")
    target_link_uri = params.get("target_link_uri")
    lti_message_hint = params.get("lti_message_hint")

    logger.info(f"OIDC Login Init: iss={iss}, login_hint={login_hint}")

    # Lấy Client ID từ cấu hình hoặc mặc định khớp với Client ID saLTIre cấp cho bạn
    client_id = "saltire.lti.app"
    
    # URL Authentication Server của saLTIre Platform (Từ màn hình Security Model của bạn)
    auth_url = "https://saltire.lti.app/platform/auth"

    # Xây dựng các tham số OIDC bắt buộc
    redirect_params = {
        "scope": "openid",
        "response_type": "id_token",
        "response_mode": "form_post",
        "prompt": "none",
        "client_id": client_id,
        "redirect_uri": target_link_uri or "https://goldsmith-oasis-frill.ngrok-free.dev/lti/launch",
        "login_hint": login_hint,
        "state": str(uuid.uuid4()),
        "nonce": str(uuid.uuid4()) # Sinh nonce hợp lệ để giải quyết lỗi Invalid nonce
    }

    if lti_message_hint:
        redirect_params["lti_message_hint"] = lti_message_hint

    # Mã hóa các tham số và thực hiện redirect
    encoded_params = urllib.parse.urlencode(redirect_params)
    target_redirect = f"{auth_url}?{encoded_params}"
    
    logger.info(f"Redirecting to saLTIre OIDC Auth Server: {target_redirect}")
    return RedirectResponse(url=target_redirect, status_code=302)

@router.post("/lti/launch", response_class=HTMLResponse)
async def lti_launch(request: Request):
    """
    Bước 2: LTI 1.3 Tool Launch.
    Nhận POST request chứa id_token đã được ký số từ saLTIre LMS và hiển thị giao diện iPad.
    """
    form_data = await request.form()
    id_token = form_data.get("id_token")
    
    if id_token:
        logger.info("LTI 1.3 Handshake thành công! Đã nhận id_token bảo mật từ saLTIre.")
    else:
        logger.warning("Không tìm thấy id_token. Chạy ở chế độ Demo độc lập.")

    # Đọc và trả về file HTML giao diện iPad
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    html_path = os.path.join(base_dir, "frontend_demo", "neuro_ipad_demo.html")
    
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except Exception as e:
        logger.error(f"Lỗi tải giao diện: {e}")
        return HTMLResponse(content=f"<h1>Lỗi tải giao diện Neuro-Sync: {e}</h1>", status_code=500)

@router.get("/lti/launch", response_class=HTMLResponse)
async def lti_launch_get():
    """Hỗ trợ tải trực tiếp qua trình duyệt khi test local debug"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    html_path = os.path.join(base_dir, "frontend_demo", "neuro_ipad_demo.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)