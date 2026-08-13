"""mybk_planner — read-only data-fetching layer for a HCMUT course planner.

Client for the mybk.hcmut.edu.vn portal:
  - CAS SSO auth (sso.hcmut.edu.vn) -> JWT + session
  - /app REST API (/api/...): transcript, GPA, CTĐT, timetable, exams
  - modern /app sinh-vien/* registration listing (read-only — no registration
    or ticket write endpoints are exposed)

Read-only by design: every public function is a fetch against the caller's
own student record.
"""

from .api import ApiError, MyBK
from .cas import CasError, login_app, login_dkmh

__all__ = ["ApiError", "CasError", "MyBK", "login_app", "login_dkmh"]
__version__ = "0.1.0"
