import re


def verify_sha256_hash(test: str):
    return bool(re.match('^[a-fA-F0-9]{64}$', test))
