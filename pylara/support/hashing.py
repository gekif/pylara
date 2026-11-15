"""
Hash - hashing password dengan PBKDF2-HMAC-SHA256 (hanya stdlib).
Mirip Hash::make() / Hash::check() di Laravel.

Format hasil: pbkdf2_sha256$<iterasi>$<salt hex>$<hash hex>
"""

import hashlib
import hmac
import secrets

ITERATIONS = 260_000


class Hash:

    @staticmethod
    def make(password: str, iterations: int = ITERATIONS) -> str:
        salt = secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), iterations)
        return f"pbkdf2_sha256${iterations}${salt}${digest.hex()}"

    @staticmethod
    def check(password: str, hashed: str) -> bool:
        try:
            algo, iterations, salt, expected = hashed.split("$")
            if algo != "pbkdf2_sha256":
                return False
            digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations))
        except (ValueError, AttributeError):
            return False
        return hmac.compare_digest(digest.hex(), expected)
