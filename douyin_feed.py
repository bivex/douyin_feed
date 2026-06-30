#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Douyin (китайский TikTok) — безлогиновый фид через внешний сервис подписи.

Полностью воспроизводит доказанно рабочий пайплайн:
    ttwid (register) -> msToken (Chrome 149 UA) -> aBogus -> эндпоинт Douyin

Зависимости:  pip install requests "requests[socks]"
Автор подписей: api2.52jan.com (тестовый cid из публичного репо Superheroff).
Лимит cid: 200 запросов/день (тестовый аккаунт — не для нагрузки).

Запуск:  python3 douyin_feed.py
"""
import hashlib
import time
import json
import requests
from urllib.parse import urlencode

# ─────────────────────────── КОНФИГ ───────────────────────────
# cid тестового аккаунта сервиса подписей api2.52jan.com
CID = "d9ba8ae07d955b83c3b04280f3dc5a4a"
SIGN_HOST = "https://api2.52jan.com"
# Соль AppKey из репозитория Superheroff (см. TikTokApiTest.__AppKey)
APPKEY_SALT = "5c6b8r9a"

# SOCKS5-прокси (для обращений к Douyin; к 52jan.com прокси не обязателен)
SOCKS5 = "socks5://jAGome9inQjtByd:iGoQn4cIBkteq3R@89.32.126.116:43438"

# UA должен быть именно Chrome 149 — этого требует эндпоинт msToken сервиса
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36")
# ────────────────────────────────────────────────────────────────


class DouyinClient:
    """Безлогиновый клиент Douyin: ttwid + msToken + aBogus поверх api2.52jan.com."""

    def __init__(self, cid=CID, sign_host=SIGN_HOST, socks5=SOCKS5, ua=UA):
        self.cid = cid
        self.sign_host = sign_host
        self.ua = ua
        self.appkey = hashlib.sha256((cid + APPKEY_SALT).encode()).hexdigest()
        proxies = {"http": socks5, "https": socks5} if socks5 else None

        self.s = requests.Session()
        self.s.headers.update({
            "User-Agent": ua,
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": "https://www.douyin.com/",
        })
        if proxies:
            self.s.proxies.update(proxies)
        # к сервису подписей тоже идём через тот же прокси
        self._proxies = proxies

        self.ttwid = ""
        self.ms_token = ""

    # ── подпись для api2.52jan.com ──
    def _sign(self, ts):
        # sign = md5('1005' + cid + ts + AppKey)
        raw = "1005" + self.cid + ts + self.appkey
        return hashlib.md5(raw.encode("utf8")).hexdigest()

    def _api(self, path, payload):
        """POST в сервис подписей с авто-подписью."""
        ts = str(int(time.time()))
        body = dict(payload)
        body["sign"] = self._sign(ts)
        return requests.post(
            self.sign_host + path,
            json=body,
            headers={"cid": self.cid, "timestamp": ts, "content-type": "application/json"},
            proxies=self._proxies,
            timeout=25,
        )

    # ── подготовка сессии ──
    def init_tokens(self):
        """Получает свежие ttwid и msToken без логина."""
        # 1) ttwid через register-эндпоинт
        self.s.post(
            "https://ttwid.bytedance.com/ttwid/union/register/",
            json={
                "region": "cn", "aid": 1768, "needFid": False,
                "service": "https://www.douyin.com",
                "migrate_info": {"ticket": "", "source": "node"},
                "cbUrlProtocol": "https", "union": True, "fid": "",
            },
            timeout=25,
        )
        self.ttwid = self.s.cookies.get("ttwid") or ""

        # 2) msToken (нужен cookie + Chrome 149 UA)
        r = self._api("/dyapi/web/get_msToken", {
            "msToken": "",
            "headers": {"User-Agent": self.ua, "Cookie": f"ttwid={self.ttwid}"},
            "uuid": "",
        })
        self.ms_token = r.json().get("msToken", "")
        return self.ttwid and self.ms_token

    def _signed_get(self, url, params):
        """Считает aBogus над полным URL и делает GET к Douyin."""
        if not (self.ttwid and self.ms_token):
            self.init_tokens()
        p = dict(params)
        p["msToken"] = self.ms_token
        full = url + ("&" if "?" in url else "?") + urlencode(p)
        abogus = self._api("/dyapi/web/abogus", {
            "url": full, "ua": self.ua, "data": "", "t": "",
        }).json().get("abogus", "")
        return self.s.get(full + "&a_bogus=" + abogus,
                          headers={"Accept": "application/json"}, timeout=30)

    # ── эндпоинты Douyin (без логина) ──
    def get_trending(self, limit=46):
        """Тренды Douyin: /aweme/v1/web/hot/search/list/ — работает без логина."""
        resp = self._signed_get(
            "https://www.douyin.com/aweme/v1/web/hot/search/list/",
            {
                "device_platform": "webapp", "aid": "6383",
                "channel": "channel_pc_web", "detail": "1", "source": "6",
                "cookie_enabled": "true",
                "screen_width": "1920", "screen_height": "1080",
                "browser_language": "zh-CN", "browser_platform": "Win32",
                "browser_name": "Chrome", "browser_version": "149.0.0.0",
                "browser_online": "true",
            },
        )
        data = resp.json()
        words = (data.get("data") or {}).get("word_list") or []
        return {
            "status_code": data.get("status_code"),
            "raw_bytes": len(resp.content),
            "items": [{
                "position": w.get("position"),
                "word": w.get("word"),
                "hot_value": w.get("hot_value"),
                "sentence_id": w.get("sentence_id"),
            } for w in words[:limit]],
        }


def main():
    print("Douyin безлогиновый фид (тренды)")
    print("=" * 50)
    cli = DouyinClient()
    if not cli.init_tokens():
        print("Не удалось получить ttwid/msToken")
        return

    print(f"ttwid : {cli.ttwid[:24]}...")
    print(f"msToken: {cli.ms_token[:24]}...")
    print("=" * 50)

    feed = cli.get_trending(limit=15)
    print(f"status_code: {feed['status_code']} | байт: {feed['raw_bytes']} | "
          f"тем: {len(feed['items'])}\n")
    for it in feed["items"]:
        print(f"  #{it['position']} [{it['hot_value']}🔥] {it['word']}")


if __name__ == "__main__":
    main()
