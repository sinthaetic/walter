"""WALTER-valvet: krypterar ägarens data (data/state.json <-> data/state.enc).

  python fetcher/walter_vault.py ny-kod    skriv ut en ny åtkomstkod
  python fetcher/walter_vault.py las       state.json -> state.enc (kräver WALTER_OWNER_KEY)
  python fetcher/walter_vault.py las-upp   state.enc -> state.json (vägrar skriva över nyare state.json)

Kuvert (samma i JS): {"v":1,"kdf":"PBKDF2-SHA256","iter":600000,"salt","iv","ct"} i vanlig base64.
AES-256-GCM, 16 byte salt, 12 byte iv, ct = chiffertext + 16 byte tag.
"""

import base64
import hashlib
import json
import os
import secrets
import sys
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "data" / "state.json"
ENC = ROOT / "data" / "state.enc"
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
ITER = 600000


class VaultError(Exception):
    pass


def _key(code, salt, iterations):
    return hashlib.pbkdf2_hmac("sha256", code.encode("utf-8"), salt, iterations, 32)


def encrypt(obj, code, iter=ITER):
    salt, iv = secrets.token_bytes(16), secrets.token_bytes(12)
    data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    ct = AESGCM(_key(code, salt, iter)).encrypt(iv, data, None)
    b64 = lambda b: base64.b64encode(b).decode("ascii")
    return {"v": 1, "kdf": "PBKDF2-SHA256", "iter": iter, "salt": b64(salt), "iv": b64(iv), "ct": b64(ct)}


def decrypt(env, code):
    try:
        salt, iv, ct = (base64.b64decode(env[k]) for k in ("salt", "iv", "ct"))
        key = _key(code, salt, int(env["iter"]))
        return json.loads(AESGCM(key).decrypt(iv, ct, None).decode("utf-8"))
    except (InvalidTag, KeyError, ValueError, TypeError):
        raise VaultError("Fel kod eller trasig fil") from None


def new_code():
    return "-".join("".join(secrets.choice(ALPHABET) for _ in range(5)) for _ in range(6))


def owner_key():
    import walter_fetch
    walter_fetch.load_env()
    return os.environ.get("WALTER_OWNER_KEY") or None


def _need_key(code):
    code = code or owner_key()
    if not code:
        sys.exit("WALTER_OWNER_KEY saknas. Kör 'ny-kod' och lägg koden i fetcher/.env.")
    return code


def lock_state(code=None, src=STATE, dst=ENC, iter=ITER):
    code = _need_key(code)
    env = encrypt(json.loads(Path(src).read_text(encoding="utf-8")), code, iter)
    Path(dst).write_text(json.dumps(env), encoding="utf-8")


def unlock_state(code=None, dst=STATE, src=ENC):
    code = _need_key(code)
    dst, src = Path(dst), Path(src)
    if dst.exists() and dst.stat().st_mtime > src.stat().st_mtime:
        sys.exit("state.json är nyare än state.enc – vägrar skriva över. Kör 'las' först eller ta bort state.json.")
    try:
        obj = decrypt(json.loads(src.read_text(encoding="utf-8")), code)
    except VaultError as e:
        sys.exit(str(e))
    dst.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv):
    cmd = argv[0] if argv else ""
    if cmd == "ny-kod":
        print(new_code())
    elif cmd == "las":
        lock_state()
        print("Låst: data/state.enc")
    elif cmd == "las-upp":
        unlock_state()
        print("Upplåst: data/state.json")
    else:
        sys.exit("Använd: walter_vault.py ny-kod | las | las-upp")


if __name__ == "__main__":
    main(sys.argv[1:])
