"""CAS SSO authentication against the HCMUT Apereo CAS 3.5.1.

Port of the proven HCMUT CAS login flow:

  1. entry -> 302 Location  (…)/cas/login?service=<service>
  2. GET  login form, regex out `lt` + `execution` + form `action`
  3. POST username/password/lt/execution/_eventId=submit/submit=Login
  4. 302 Location carries ?ticket=ST-…
  5. GET service?ticket=… (follows redirects) -> app shell with #hid_Token

Same `requests.Session` may be reused across services: the CAS TGC cookie is
kept, so a second `cas_flow` for the DKMH service does a ticket exchange
without re-entering credentials.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

import requests

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) mybk-planner/0.1"


class CasError(RuntimeError):
    pass


def _extract(pattern: str, html: str) -> str | None:
    m = re.search(pattern, html, re.IGNORECASE)
    return m.group(1).strip() if m else None


def _absolute(base: str, url: str) -> str:
    return url if url.startswith("http") else urljoin(base + "/", url)


def discover_cas(session: requests.Session, entry_url: str) -> str | None:
    """Follow the app's own redirect chain to find the CAS login URL.

    Returns None when the resource is already authenticated (e.g. a TGC in
    the session short-circuits the redirect) — callers should treat that as
    "session is already valid".
    """
    r = session.get(entry_url, allow_redirects=False, timeout=30)
    loc = r.headers.get("Location", "")
    if "cas/login" in loc:
        return loc if loc.startswith("http") else urljoin(entry_url, loc)
    return None


def cas_flow(session: requests.Session, username: str, password: str, cas_login_url: str) -> requests.Response:
    """Perform the full CAS form login; returns the final service response.

    Raises CasError on parse failure, HTTP error, or missing ticket.
    """
    # 1. fetch the login form
    form = session.get(cas_login_url, timeout=30)
    form.raise_for_status()
    lt = _extract(r'name="lt"\s+value="([^"]+)"', form.text)
    execution = _extract(r'name="execution"\s+value="([^"]+)"', form.text)
    action = _extract(r"<form[^>]*action=\"([^\"]+)\"", form.text)
    if not lt or not execution:
        raise CasError("Could not parse CAS form (lt/execution missing) — check network / rate limit")
    form_action = _absolute(cas_login_url, action)

    # 2. POST credentials (form-urlencoded, no redirects — we want the 302)
    r = session.post(
        form_action,
        data={
            "username": username,
            "password": password,
            "lt": lt,
            "execution": execution,
            "_eventId": "submit",
            "submit": "Login",
        },
        allow_redirects=False,
        timeout=30,
    )
    if r.status_code not in (301, 302, 303):
        raise CasError(f"CAS POST returned HTTP {r.status_code} with no redirect — bad credentials or rate-limited")
    location = r.headers.get("Location", "")
    ticket = _extract(r"ticket=([^&\s]+)", location)
    if not ticket:
        raise CasError(f"CAS redirect carried no ticket: {location}")

    # 3. follow the ticket back to the service, complete the session
    final = session.get(location, timeout=30)
    final.raise_for_status()
    return final


def login_app(username: str, password: str, session: requests.Session | None = None):
    """CAS login for the modern /app portal; returns (session, jwt).

    JWT raw value from #hid_Token (matches the live /app/js/main.js which
    sends `Authorization: <token>` un-prefixed).
    """
    s = session or requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    cas_url = discover_cas(s, "https://mybk.hcmut.edu.vn/app/login?type=cas")
    if not cas_url:
        t = _extract(r'hid_Token"\s+value="([^"]+)"', s.get("https://mybk.hcmut.edu.vn/app/", timeout=30).text)
        if t:
            return s, t
        raise CasError("app/login?type=cas did not redirect to CAS and no existing token found")
    final = cas_flow(s, username, password, cas_url)
    jwt = _extract(r'id="hid_Token"\s+value="([^"]+)"', final.text)
    if not jwt:
        raise CasError("Ticket exchange completed but #hid_Token was not found in the app shell")
    return s, jwt


def login_dkmh(session: requests.Session, username: str, password: str) -> requests.Session:
    """CAS login for the legacy DKMH module (if the session has no TGC yet).

    The entry /dkmh/ redirects to a local CAS instance
    (mybk.hcmut.edu.vn/cas/login); when a TGC already exists the redirect is
    skipped and the session is simply returned.
    """
    cas_url = discover_cas(session, "https://mybk.hcmut.edu.vn/dkmh/")
    if cas_url:
        cas_flow(session, username, password, cas_url)
    return session