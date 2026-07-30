"""
5단계 — 카카오톡 '나에게 보내기'

카카오 공식 문서 확인 사항:
  - 엔드포인트 POST https://kapi.kakao.com/v2/api/talk/memo/default/send
  - '나에게 보내기'는 별도 사용 권한 신청 불필요 (친구 발송만 신청 필요)
  - 필요: 카카오 로그인 활성화 + 동의항목 talk_message
  - 텍스트 템플릿 text는 200자 제한

액세스 토큰은 약 6시간이면 만료되므로 매 실행마다 리프레시 토큰으로 재발급한다.
리프레시 토큰이 회전되면 GH_PAT로 GitHub Secret을 자동 갱신한다.
"""
from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path

import requests

DATA = Path("data")
REST_KEY = os.environ.get("KAKAO_REST_API_KEY", "").strip()
REFRESH = os.environ.get("KAKAO_REFRESH_TOKEN", "").strip()
FAILURE_MODE = "--failure" in sys.argv


def get_access_token() -> tuple[str, str | None]:
    """리프레시 토큰으로 액세스 토큰 재발급. 새 리프레시 토큰이 오면 함께 반환."""
    r = requests.post(
        "https://kauth.kakao.com/oauth/token",
        data={
            "grant_type": "refresh_token",
            "client_id": REST_KEY,
            "refresh_token": REFRESH,
        },
        timeout=20,
    )
    r.raise_for_status()
    j = r.json()
    # 리프레시 토큰은 만료 1개월 미만일 때만 새로 내려온다
    return j["access_token"], j.get("refresh_token")


def send_text(token: str, text: str, link: str | None = None) -> None:
    """텍스트 템플릿 발송. text는 200자 제한."""
    if len(text) > 200:
        raise ValueError(f"200자 초과: {len(text)}자")
    obj = {
        "object_type": "text",
        "text": text,
        "link": {"web_url": link, "mobile_web_url": link} if link else {},
    }
    r = requests.post(
        "https://kapi.kakao.com/v2/api/talk/memo/default/send",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
        },
        data={"template_object": json.dumps(obj, ensure_ascii=False)},
        timeout=20,
    )
    if r.status_code != 200:
        raise RuntimeError(f"발송 실패 {r.status_code}: {r.text}")
    print(f"✅ 카톡 발송 완료 ({len(text)}자)")


def rotate_secret(new_refresh: str) -> None:
    """새 리프레시 토큰을 GitHub Secret에 자동 반영 (GH_PAT 필요)."""
    pat = os.environ.get("GH_PAT", "").strip()
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if not pat or not repo:
        print("⚠️  리프레시 토큰이 회전됐으나 GH_PAT가 없어 자동 갱신 불가.")
        print("    KAKAO_REFRESH_TOKEN 시크릿을 수동으로 교체하세요:")
        print(f"    {new_refresh}")
        return
    try:
        from nacl import encoding, public          # pynacl

        h = {"Authorization": f"Bearer {pat}",
             "Accept": "application/vnd.github+json"}
        pk = requests.get(
            f"https://api.github.com/repos/{repo}/actions/secrets/public-key",
            headers=h, timeout=20).json()
        sealed = public.SealedBox(
            public.PublicKey(pk["key"].encode(), encoding.Base64Encoder())
        ).encrypt(new_refresh.encode())
        requests.put(
            f"https://api.github.com/repos/{repo}/actions/secrets/KAKAO_REFRESH_TOKEN",
            headers=h, timeout=20,
            json={"encrypted_value": base64.b64encode(sealed).decode(),
                  "key_id": pk["key_id"]},
        ).raise_for_status()
        print("🔄 KAKAO_REFRESH_TOKEN 시크릿 자동 갱신 완료")
    except Exception as e:                          # noqa: BLE001
        print(f"⚠️  시크릿 갱신 실패: {e!r}")
        print(f"    수동 교체 필요: {new_refresh}")


def main() -> int:
    if not REST_KEY or not REFRESH:
        print("KAKAO_REST_API_KEY / KAKAO_REFRESH_TOKEN 없음", file=sys.stderr)
        return 1

    token, new_refresh = get_access_token()
    if new_refresh:
        rotate_secret(new_refresh)

    if FAILURE_MODE:
        run_url = os.environ.get("RUN_URL", "")
        send_text(token,
                  f"[브리핑 실패]\n오늘 자동 브리핑이 실패했습니다.\n"
                  f"로그를 확인해주세요.\n{run_url}"[:200],
                  run_url or None)
        return 0

    b = json.loads((DATA / "briefing.json").read_text(encoding="utf-8"))
    page = (DATA / "page_path.txt").read_text(encoding="utf-8").strip()

    base = os.environ.get("PAGES_BASE", "").strip().rstrip("/")
    if not base:
        owner, repo_name = os.environ["GITHUB_REPOSITORY"].split("/")
        base = f"https://{owner}.github.io/{repo_name}"
    url = f"{base}/{page}"

    text = b["kakao"].replace("{{URL}}", url)
    if len(text) > 200:                              # 최후 방어선
        keep = text.rsplit("\n", 1)[0]
        text = (keep[: 200 - len(url) - 2] + "\n" + url)[:200]

    send_text(token, text, url)
    print(f"   링크: {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
