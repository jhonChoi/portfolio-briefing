"""
[최초 1회만] 카카오 리프레시 토큰 발급 도우미 — 내 PC에서 실행

사용법:
    pip install requests
    python scripts/get_kakao_token.py

사전 준비 (developers.kakao.com):
  1. 애플리케이션 추가하기
  2. 앱 설정 > 앱 키 > REST API 키 복사
  3. 카카오 로그인 > 활성화 ON
  4. 카카오 로그인 > Redirect URI 등록: http://localhost:8080/callback
  5. 카카오 로그인 > 동의항목 > '카카오톡 메시지 전송(talk_message)' 을 '이용 중 동의'로 설정
     ※ '나에게 보내기'는 비즈앱 전환이나 별도 권한 신청이 필요 없습니다.
        (친구에게 보내기만 권한 신청 필요)
"""
from __future__ import annotations

import http.server
import socketserver
import threading
import urllib.parse
import webbrowser

import requests

REDIRECT = "http://localhost:8080/callback"
code_box: dict[str, str] = {}


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):                                  # noqa: N802
        q = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(q)
        if "code" in params:
            code_box["code"] = params["code"][0]
            body = "<h2>인증 완료</h2><p>터미널로 돌아가세요.</p>"
        else:
            body = f"<h2>실패</h2><pre>{params}</pre>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, *a):                         # 콘솔 조용히
        pass


def main() -> None:
    rest_key = input("REST API 키: ").strip()

    auth_url = (
        "https://kauth.kakao.com/oauth/authorize"
        f"?client_id={rest_key}"
        f"&redirect_uri={urllib.parse.quote(REDIRECT)}"
        "&response_type=code"
        "&scope=talk_message"
    )

    with socketserver.TCPServer(("", 8080), Handler) as httpd:
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        print("\n브라우저에서 카카오 로그인 후 동의해주세요...")
        print(auth_url + "\n")
        webbrowser.open(auth_url)
        while "code" not in code_box:
            pass
        httpd.shutdown()

    r = requests.post(
        "https://kauth.kakao.com/oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": rest_key,
            "redirect_uri": REDIRECT,
            "code": code_box["code"],
        },
        timeout=20,
    )
    r.raise_for_status()
    j = r.json()

    print("\n" + "=" * 60)
    print("아래 두 값을 GitHub 레포 Settings > Secrets and variables > Actions 에 등록하세요.")
    print("=" * 60)
    print(f"\nKAKAO_REST_API_KEY\n  {rest_key}")
    print(f"\nKAKAO_REFRESH_TOKEN\n  {j['refresh_token']}")
    print(f"\n(리프레시 토큰 유효기간: {j.get('refresh_token_expires_in', 0) // 86400}일)")
    print("\n※ 이 값들은 비밀번호와 같습니다. 코드나 채팅에 붙여넣지 마세요.")


if __name__ == "__main__":
    main()
