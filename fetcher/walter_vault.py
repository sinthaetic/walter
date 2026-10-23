"""WALTER-valvet: krypterar ägarens data (data/state.json <-> data/state.enc).

  python fetcher/walter_vault.py ny-kod    skriv ut en ny åtkomstkod
  python fetcher/walter_vault.py las       state.json -> state.enc (kräver WALTER_OWNER_KEY)
  python fetcher/walter_vault.py las-upp   state.enc -> state.json (vägrar skriva över nyare state.json)
  python fetcher/walter_vault.py sla-ihop FIL   lägg daily/notis från en owner.enc (gh-pages) i data/owner-cache.json

Kuvert (samma i JS): {"v":1,"kdf":"PBKDF2-SHA256","iter":600000,"salt","iv","ct"} i vanlig base64.
AES-256-GCM, 16 byte salt, 12 byte iv, ct = chiffertext + 16 byte tag.
"""

import base64
import hashlib
import json
import os
import secrets
import subprocess
import sys
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "data" / "state.json"
ENC = ROOT / "data" / "state.enc"
OWNER_CACHE = ROOT / "data" / "owner-cache.json"
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


def merge_daily(a, b):
    """Union av dagsvärden; vid samma datum vinner b."""
    return {**a, **b}


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


def _write_atomic(path, text):
    """Skriv till tempfil i samma katalog och byt sedan, så en avbruten skrivning aldrig lämnar halv fil."""
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def lock_state(code=None, src=STATE, dst=ENC, iter=ITER):
    code = _need_key(code)
    src = Path(src)
    if not src.exists():
        sys.exit(f"Hittar inte {src.name} – inget att låsa.")
    try:
        obj = json.loads(src.read_text(encoding="utf-8"))
    except ValueError:
        sys.exit(f"{src.name} är trasig (ogiltig JSON) – rätta den först.")
    _write_atomic(dst, json.dumps(encrypt(obj, code, iter)))


def unlock_state(code=None, dst=STATE, src=ENC):
    code = _need_key(code)
    dst, src = Path(dst), Path(src)
    if not src.exists():
        sys.exit(f"Hittar inte {src.name} – kör 'las' först.")
    if dst.exists() and dst.stat().st_mtime > src.stat().st_mtime:
        sys.exit(f"{dst.name} är nyare än {src.name} – vägrar skriva över. "
                 "Kör 'las' först om du vill spara dina ändringar.")
    try:
        obj = decrypt(json.loads(src.read_text(encoding="utf-8")), code)
    except (VaultError, ValueError) as e:
        sys.exit(str(e) if isinstance(e, VaultError) else "Fel kod eller trasig fil")
    _write_atomic(dst, json.dumps(obj, ensure_ascii=False, indent=2))


def _read_enc(text, code):
    try:
        return decrypt(json.loads(text), code)
    except (VaultError, ValueError):
        return None


OFFLINE_HINTS = ("could not resolve host", "unable to access", "could not read from remote",
                 "failed to connect", "connection timed out", "network is unreachable")


def _offline(stderr):
    s = stderr.lower()
    return any(h in s for h in OFFLINE_HINTS)


def sync_from_repo(root=ROOT, state=STATE, enc=ENC, run=subprocess.run):
    """Datorn: hämta main (Walter kan ha handlat i Actionen och committat state.enc) och lås upp
    state.enc -> state.json om innehållet är annat och state.json inte har egna, nyare ändringar.
    Tyst om offline, ingen git eller inget repo. Körs aldrig i Actionen.
    Returnerar None (gjorde inget), "same", "local" (behöll lokala ändringar), "pullfail" (git pull
    gick inte av annat skäl än offline – rör inget) eller "unlocked" (gamla state.json -> state.json.bak)."""
    if os.environ.get("GITHUB_ACTIONS"):
        return None
    root, state, enc = Path(root), Path(state), Path(enc)
    if not (root / ".git").exists():
        return None
    pre_text = enc.read_text(encoding="utf-8") if enc.exists() else None
    pre_mtime = enc.stat().st_mtime if enc.exists() else 0
    try:
        r = run(["git", "pull", "--ff-only", "-q"], cwd=root, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        r = None  # ingen git eller timeout: jobba med det som finns
    if r is not None and r.returncode and not _offline(getattr(r, "stderr", "") or ""):
        print("Kunde inte hämta main – kör git status. Walter använder din lokala state.json tills vidare.")
        return "pullfail"
    if not enc.exists():
        return None
    code = owner_key()
    if not code:
        return None
    text = enc.read_text(encoding="utf-8")
    remote = _read_enc(text, code)
    if remote is None:
        print(f"Kunde inte låsa upp {enc.name} (fel kod?) – använder din lokala {state.name}.")
        return None
    try:
        local = json.loads(state.read_text(encoding="utf-8")) if state.exists() else None
    except ValueError:
        local = None
    if local == remote:
        return "same"
    if local is not None and state.stat().st_mtime > pre_mtime:
        # Nyare än state.enc var före hämtningen. Lokala ändringar bara om innehållet skiljer sig från det.
        pre = remote if pre_text == text else (_read_enc(pre_text, code) if pre_text else None)
        if local != pre:
            print(f"Du har ändringar i {state.name} som är nyare än den låsta {enc.name} – Walter använder "
                  "dina lokala. Välj själv: kör walter_vault.py las (tar dina, skriver över Walters) "
                  "eller las-upp (tar Walters).")
            return "local"
    if state.exists():  # reservkopia av den gamla, ifall något gick fel (gitignorerad)
        _write_atomic(state.with_name(state.name + ".bak"), state.read_text(encoding="utf-8"))
    _write_atomic(state, json.dumps(remote, ensure_ascii=False, indent=2))
    print(f"Hämtade Walters senaste journal från GitHub ({enc.name} -> {state.name}).")
    return "unlocked"


def merge_owner_cache(enc_path, code, dst=OWNER_CACHE):
    """daily/notis från en publicerad owner.enc in i owner-cache.json. Lokala värden vinner.
    Returnerar False (och rör inget) om filen inte går att läsa, t.ex. efter byte av kod."""
    dst = Path(dst)
    try:
        remote = decrypt(json.loads(Path(enc_path).read_text(encoding="utf-8")), code)
    except (OSError, ValueError, VaultError):
        return False
    local = json.loads(dst.read_text(encoding="utf-8")) if dst.exists() else {}
    local["daily"] = merge_daily(remote.get("daily") or {}, local.get("daily") or {})
    if not local.get("notis") and remote.get("notis"):
        local["notis"] = remote["notis"]
    _write_atomic(dst, json.dumps(local, indent=2, ensure_ascii=False))
    return True


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
    elif cmd == "sla-ihop" and len(argv) > 1:
        if not Path(argv[1]).exists():
            print(f"Ingen {argv[1]} – inget att slå ihop.")
        elif merge_owner_cache(argv[1], _need_key(None)):
            print("Slog ihop daily/notis från owner.enc i data/owner-cache.json")
        else:
            sys.exit(f"Kunde inte låsa upp {argv[1]} (ny kod?). Stoppar så att gamla dagsvärden inte tappas.")
    else:
        sys.exit("Använd: walter_vault.py ny-kod | las | las-upp | sla-ihop FIL")


if __name__ == "__main__":
    main(sys.argv[1:])
