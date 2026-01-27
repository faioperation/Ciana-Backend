import secrets
import hashlib
from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.utils.crypto import constant_time_compare

def _otp_key(email: str) -> str:
    return f"pwd-reset:otp:{email.lower()}"

def _otp_attempts_key(email: str) -> str:
    return f"pwd-reset:attempts:{email.lower()}"

def _otp_reqcount_key(email: str) -> str:
    return f"pwd-reset:reqcount:{email.lower()}"

def _otp_cooldown_key(email: str) -> str:
    return f"pwd-reset:cooldown:{email.lower()}"

def _otp_verified_key(email: str) -> str:
    return f"pwd-reset:verified:{email.lower()}"

def set_verified_for_email(email: str, ttl: int = None):
    """
    Mark this email as OTP-verified for a short TTL.
    Frontend can now call reset within this window.
    """
    key = _otp_verified_key(email)
    ttl = ttl or getattr(settings, "PASSWORD_RESET_VERIFIED_TTL", 600)
    cache.set(key, 1, ttl)

def is_verified_for_email(email: str) -> bool:
    """
    Return True if the email has been recently verified.
    """
    return bool(cache.get(_otp_verified_key(email)))

def clear_verified_for_email(email: str):
    cache.delete(_otp_verified_key(email))

def generate_numeric_otp(length: int = None) -> str:
    length = length or getattr(settings, "PASSWORD_RESET_OTP_LENGTH", 6)
    max_val = 10 ** length
    n = secrets.randbelow(max_val)
    return str(n).zfill(length)

def _hash_otp(otp: str) -> str:
    pepper = getattr(settings, "PASSWORD_RESET_OTP_PEPPER", "")
    h = hashlib.sha256()
    h.update((otp + pepper).encode())
    return h.hexdigest()

def store_otp_for_email(email: str, otp: str):
    key = _otp_key(email)
    hashed = _hash_otp(otp)
    ttl = getattr(settings, "PASSWORD_RESET_OTP_TTL", 600)
    cache.set(key, hashed, ttl)
    req_key = _otp_reqcount_key(email)
    count = cache.get(req_key) or 0
    cache.set(req_key, count + 1, 3600)  # 1 hour window
    cache.set(_otp_cooldown_key(email), 1, getattr(settings, "PASSWORD_RESET_RESEND_COOLDOWN", 60))
    cache.set(_otp_attempts_key(email), 0, ttl)

def increment_verify_attempts(email: str) -> int:
    k = _otp_attempts_key(email)
    attempts = cache.get(k) or 0
    attempts += 1
    cache.set(k, attempts, getattr(settings, "PASSWORD_RESET_OTP_TTL", 600))
    return attempts

def get_stored_hashed_otp(email: str):
    return cache.get(_otp_key(email))

def clear_otp_for_email(email: str):
    cache.delete(_otp_key(email))
    cache.delete(_otp_attempts_key(email))
    cache.delete(_otp_cooldown_key(email))
    # keep request count so rate limiting remains

def can_request_otp(email: str):
    req_key = _otp_reqcount_key(email)
    cd_key = _otp_cooldown_key(email)
    count = cache.get(req_key) or 0
    max_per_hour = getattr(settings, "PASSWORD_RESET_MAX_REQUESTS_PER_HOUR", 5)
    if count >= max_per_hour:
        return False, "Too many OTP requests. Try later.", 0, 0

    # remaining cooldown in seconds (cache.ttl returns None if key not found)
    remaining_cd = None
    try:
        # django-redis exposes ttl, but for safety check None/negative
        remaining_cd = cache.ttl(cd_key)
        if remaining_cd is None or remaining_cd < 0:
            remaining_cd = 0
    except Exception:
        remaining_cd = 0

    # remaining requests this hour
    remaining_reqs = max(0, max_per_hour - count)

    if cache.get(cd_key):
        return False, "Please wait before requesting another OTP.", remaining_cd, remaining_reqs

    return True, "", remaining_cd, remaining_reqs

def send_otp_email(email: str, otp: str):
    subject = "Your OTP for Star Light Path"
    message = f"""
    <html>
        <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
            <div style="background-color: #ffffff; padding: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);">
                <h2 style="color: #333;">Your Password Reset Code</h2>
                <p style="font-size: 16px; color: #555;">
                    Hello,<br><br>
                    You requested to reset your password for <strong>Star Light Path</strong>. Your OTP is:
                </p>
                <h3 style="background-color: #fce8c8; border: 1px solid #f5b642; color: #111212; padding: 10px; border-radius: 4px; text-align: center;">
                    {otp}
                </h3>
                <p style="font-size: 16px; color: #555;">
                    Please use this code to reset your password. It expires shortly.
                </p>
                <p style="font-size: 14px; color: #777;">
                    If you did not request this, please ignore this email.
                </p>
                <footer style="margin-top: 20px; font-size: 12px; color: #999;">
                    &copy; Star Light Path. All rights reserved.
                </footer>
            </div>
        </body>
    </html>
    """
    from_email = None  # uses DEFAULT_FROM_EMAIL if set
    send_mail(subject, message, from_email, [email], fail_silently=False, html_message=message)


def verify_otp(email: str, otp: str) -> bool:
    stored = get_stored_hashed_otp(email)
    if not stored:
        return False
    provided_hashed = _hash_otp(otp)
    return constant_time_compare(provided_hashed, stored)