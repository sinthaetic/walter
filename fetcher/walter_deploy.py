"""WALTER deploy: bygger sidan och lägger en publicerbar kopia i deploy/.

  python fetcher/walter_deploy.py

Publikt: bara marknaden (data/market.js, data/cache.json) och ägarens data KRYPTERAD
(data/owner.enc, kod = WALTER_OWNER_KEY). Aldrig state.js, state.json, reports/ eller fetcher/.
Läckspärren (leak_check) stoppar publiceringen om ägarens data hittas okrypterad i deploy/.
Är WALTER_PAGES_REPO satt i fetcher/.env (t.ex. https://github.com/NAMN/walter.git)
pushas deploy/ till grenen gh-pages och sidan hamnar på https://NAMN.github.io/walter/.
Annars öppnas Netlify Drop, där deploy-mappen dras in för att få en https-länk.
Är mappen ett git-repo och main utcheckad skickas även data/state.enc (låst state.json) till main
(HEAD:main), så att GitHub Actionen (walter-auto.yml) bygger med samma journal nästa gång den hämtar.
Före bygget slås publicerade cache.json (gh-pages) ihop med den lokala, så att loggdagar som
Actionen lagt till aldrig försvinner. Med WALTER_PAGES_REPO men utan WALTER_OWNER_KEY publiceras inget.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import webbrowser
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "deploy"
OWNER_ENC = ROOT / "data" / "owner.enc"
ALLOW = ["index.html", "cipher.html", "css", "js", "assets", "data/market.js", "data/cache.json", "data/owner.enc"]
# extra spärr om någon lägger något fel i en tillåten mapp
BLOCK = {".env", "etf_raw.json", "state.json", "state.js", "owner-cache.json", "paper-journal-*.csv"}
# ord som bara finns i ägarens data – får aldrig stå okrypterat i deploy/data/
PRIVATE_WORDS = ["journal", "portfolio", "k4", "capitalChange", "daily", "notis", "proposal", "WALTER_OWNER_KEY"]

sys.path.insert(0, str(Path(__file__).resolve().parent))
from walter_fetch import load_env, warn  # noqa: E402
import walter_fetch  # noqa: E402
import walter_vault  # noqa: E402


def blocked(name):
    return any(fnmatch(name, b) for b in BLOCK)


def build_state():
    r = subprocess.run([sys.executable, str(ROOT / "fetcher" / "walter_fetch.py"), "--offline"])
    if r.returncode:
        sys.exit("Kunde inte bygga state.js – deploy avbruten.")
    r = subprocess.run([sys.executable, str(ROOT / "fetcher" / "walter_k4.py")])
    if r.returncode:
        sys.exit("Kunde inte bygga K4/avgiftsrapport – deploy avbruten.")


def build_owner_enc(state, owner_cache, code):
    """Ägarens hela bild (samma som state.js) + dagsvärden och notis, krypterad."""
    return walter_vault.encrypt({"state": state, "daily": owner_cache.get("daily") or {},
                                 "notis": owner_cache.get("notis")}, code)


def fetch_published_file(repo, rel, dst):
    """Hämta rel (t.ex. data/owner.enc) från gh-pages till dst. Bara läsning, inget pushas.
    True = hämtad, False = finns inte än (första gången). Går gh-pages inte att nå stoppas allt –
    annars kunde en kortare historik skriva över den publicerade."""
    r = subprocess.run(["git", "ls-remote", "--exit-code", repo, "refs/heads/gh-pages"], capture_output=True)
    if r.returncode == 2:
        return False  # ingen gh-pages ännu
    if r.returncode:
        sys.exit(f"Stoppat: kunde inte nå gh-pages för att hämta publicerade {rel}. Inget publicerat.")
    with tempfile.TemporaryDirectory() as t:
        subprocess.run(["git", "init", "-q"], cwd=t, check=True)
        if subprocess.run(["git", "fetch", "-q", "--depth=1", repo, "gh-pages"], cwd=t, capture_output=True).returncode:
            sys.exit(f"Stoppat: kunde inte hämta gh-pages ({rel}). Inget publicerat.")
        show = subprocess.run(["git", "show", f"FETCH_HEAD:{rel}"], cwd=t, capture_output=True)
        if show.returncode:
            return False  # gh-pages finns men utan filen – inget att tappa
        Path(dst).write_bytes(show.stdout)
    return True


def fetch_published_owner_enc(repo, dst):
    return fetch_published_file(repo, "data/owner.enc", dst)


def fetch_published_cache(repo, dst):
    return fetch_published_file(repo, "data/cache.json", dst)


def merge_market_cache(local, pages):
    """Slå ihop lokal och publicerad marknadscache. marketLog förenas per datum: den nyare cachens rader
    vinner, men en klar dag skrivs aldrig över av en halvfärdig (samma regel som append_log).
    market/fetchedAt/sources tas från den nyare cachen."""
    import walter_auto
    import walter_public as wpub
    local, pages = local or {}, pages or {}
    lt, pt = walter_auto.fetched_at(local), walter_auto.fetched_at(pages)
    pages_newer = bool(pt) and (not lt or pt > lt)
    older, newer = (local, pages) if pages_newer else (pages, local)
    log = list(older.get("marketLog") or [])
    for row in newer.get("marketLog") or []:
        log = wpub.append_log(log, row)
    out = {**older, **newer}
    out["marketLog"] = log
    return out


def merge_published_cache(repo):
    """Lokal deploy: dagar som Actionen lagt till i publicerade cache.json får inte försvinna.
    Körs före build_state, som sedan bygger om data/market.js från den sammanslagna cachen."""
    if not repo:
        return
    with tempfile.TemporaryDirectory() as t:
        dst = Path(t) / "cache.json"
        if not fetch_published_cache(repo, dst):
            return  # första gången: inget publicerat att slå ihop
        try:
            pages = json.loads(dst.read_text(encoding="utf-8"))
        except ValueError:
            sys.exit("Stoppat: publicerade cache.json går inte att läsa. Inget publicerat.")
    local = walter_fetch.read_json(walter_fetch.CACHE, {})
    merged = walter_fetch.strip_private_cache(merge_market_cache(local, pages))
    if merged != walter_fetch.strip_private_cache(local):
        walter_vault._write_atomic(walter_fetch.CACHE, json.dumps(merged, indent=2, ensure_ascii=False))
        print("Slog ihop marknadsloggen med publicerade cache.json.")


def merge_published(code, enc_path):
    """Lägg in dagsvärden/notis från publicerade owner.enc i owner-cache.json. Går den inte att låsa upp stoppas allt."""
    if walter_vault.merge_owner_cache(enc_path, code, walter_fetch.OWNER_CACHE):
        print("Slog ihop dagsvärden från publicerade owner.enc.")
        return
    if os.environ.get("WALTER_GLOM_GAMLA_DAGAR") == "1":
        warn("Publicerade owner.enc gick inte att låsa upp – WALTER_GLOM_GAMLA_DAGAR=1, gamla dagsvärden tappas.")
        return
    sys.exit("Stoppat: publicerade owner.enc gick inte att låsa upp (ny kod?). Då skulle gamla dagsvärden "
             "försvinna, så inget publiceras. Har du bytt kod med flit: kör en gång med WALTER_GLOM_GAMLA_DAGAR=1.")


def publish_owner(code, repo):
    """owner.enc till deploy: först publicerade dagsvärden in (så inget försvinner), sedan ny fil."""
    if code and repo:
        with tempfile.TemporaryDirectory() as t:
            enc = Path(t) / "owner.enc"
            if fetch_published_owner_enc(repo, enc):
                merge_published(code, enc)
    write_owner_enc(code)


def write_owner_enc(code):
    """Skriv data/owner.enc. Utan kod: ta bort en gammal så att bara marknaden publiceras."""
    if not code:
        OWNER_ENC.unlink(missing_ok=True)
        warn("WALTER_OWNER_KEY saknas – publicerar utan owner.enc (bara marknaden). "
             "Lägg koden i fetcher/.env / GitHub Secret.")
        return
    import walter_fetch as wf
    import walter_paper as wp
    _, owner = wf.load_caches()
    walter_vault._write_atomic(OWNER_ENC, json.dumps(build_owner_enc(wp.rebuild(wf), owner, code)))


def leak_check(out_dir):
    """Lista över filer i out_dir som inte får publiceras. Tom lista = OK."""
    out_dir = Path(out_dir)
    bad = []
    for p in sorted(out_dir.rglob("*")):
        rel = p.relative_to(out_dir).as_posix()
        if blocked(p.name) or p.name == "reports":
            bad.append(rel)
    data = out_dir / "data"
    for p in sorted(data.rglob("*")) if data.exists() else []:
        if not p.is_file() or p.relative_to(out_dir).as_posix() == "data/owner.enc":
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        hits = [w for w in PRIVATE_WORDS + sorted(b.split("*")[0] for b in BLOCK) if w in text]
        if hits:
            bad.append(f"{p.relative_to(out_dir).as_posix()} ({', '.join(hits)})")
    return bad


def copy_site():
    if OUT.exists():
        shutil.rmtree(OUT)
    for rel in ALLOW:
        src = ROOT / rel
        if not src.exists():
            warn(f"{rel} finns inte – hoppas över.")
            continue
        dst = OUT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dst, ignore=lambda d, names: [n for n in names if blocked(n)])
        else:
            shutil.copy2(src, dst)
    (OUT / ".nojekyll").write_text("", encoding="utf-8")  # GitHub Pages: servera filerna som de är
    leaked = leak_check(OUT)
    if leaked:
        shutil.rmtree(OUT)
        sys.exit(f"Stoppat av läckspärren: {leaked} i deploy/. Inget publicerat.")


def lock_if_changed(code):
    """Lås state.json -> state.enc, men bara om innehållet ändrats (annars blir varje deploy en commit)."""
    src, enc = walter_vault.STATE, walter_vault.ENC
    if not src.exists():
        return
    try:
        old = walter_vault.decrypt(json.loads(enc.read_text(encoding="utf-8")), code)
        if old == json.loads(src.read_text(encoding="utf-8")):
            return
    except (OSError, ValueError, walter_vault.VaultError):
        pass
    if enc.exists() and enc.stat().st_mtime > src.stat().st_mtime:
        sys.exit("state.enc är nyare än state.json och skiljer sig (eller fel kod) – vägrar skriva över. "
                 "Kör 'python fetcher/walter_vault.py las-upp' först, eller 'las' om state.json är rätt.")
    walter_vault.lock_state(code, src, enc)
    print("Låste state.json -> state.enc")


def git(*args, cwd=OUT):
    subprocess.run(["git", *args], cwd=cwd, check=True)


def current_branch():
    r = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def push_source():
    """Lokalt: commit + push av den låsta state.enc till main. Actionen gör aldrig detta.
    Pushar uttryckligen HEAD:main, och bara när main är utcheckad – annars hamnar journalen på fel gren
    (eller en ogranskad gren på main)."""
    if os.environ.get("GITHUB_ACTIONS") or not (ROOT / ".git").exists():
        return
    branch = current_branch()
    if branch != "main":
        warn(f"Du står på grenen '{branch}', inte main – state.enc committas och pushas inte. "
             "Byt till main (git switch main) och kör walter deploy igen, annars kör Actionen med förra journalen.")
        return
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    subprocess.run(["git", "add", "data/state.enc"], cwd=ROOT)
    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT).returncode:
        subprocess.run(["git", "commit", "-q", "-m", f"journal {stamp}"], cwd=ROOT)
    if subprocess.run(["git", "push", "-q", "origin", "HEAD:main"], cwd=ROOT).returncode:
        warn("Kunde inte pusha state.enc till main – Actionen kör med förra journalen tills du kör git push.")


def check_publish_config(code, repo):
    """Med WALTER_PAGES_REPO men utan WALTER_OWNER_KEY skulle publiceringen ta bort owner.enc från gh-pages:
    ägarens vy i mobilen och dagshistoriken försvinner. Då publiceras ingenting."""
    if repo and not code:
        sys.exit("Stoppat: WALTER_PAGES_REPO är satt men WALTER_OWNER_KEY saknas i fetcher/.env. "
                 "En publicering nu skulle ta bort din Walter i mobilen (owner.enc) och dagshistoriken. "
                 "Lägg in koden i fetcher/.env och kör igen. Inget publicerat.")


def push_pages(repo):
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    git("init", "-q")
    git("checkout", "-q", "-B", "gh-pages")
    git("add", "-A")
    git("-c", "user.name=WALTER", "-c", "user.email=walter@localhost", "commit", "-q", "-m", f"WALTER deploy {stamp}")
    # gh-pages innehåller bara den byggda sidan och skrivs över varje gång
    git("push", "-q", "--force", repo, "gh-pages")
    shutil.rmtree(OUT / ".git", ignore_errors=True)
    owner, name = repo.rstrip("/").removesuffix(".git").split("/")[-2:]
    print(f"\nPublicerat. Länk (kan ta 1–2 minuter första gången):\n  https://{owner}.github.io/{name}/")


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    os.system("")  # tom sträng, bara för att slå på färger (ANSI) i Windows-terminalen
    load_env()
    print("WALTER deploy …")
    code = walter_vault.owner_key()
    repo = os.environ.get("WALTER_PAGES_REPO", "").strip()
    if repo and not shutil.which("git"):
        sys.exit("git saknas – installera Git for Windows eller använd Netlify Drop.")
    check_publish_config(code, repo)
    if code:
        lock_if_changed(code)
    merge_published_cache(repo)  # före build_state, som bygger om data/market.js med hela loggen
    build_state()
    publish_owner(code, repo)
    copy_site()
    files = sum(1 for p in OUT.rglob("*") if p.is_file())
    print(f"deploy/ klar ({files} filer). Sidan är publik för alla som har länken.")

    if repo:
        push_pages(repo)
        push_source()
        return

    print("\nIngen WALTER_PAGES_REPO i fetcher/.env – använd Netlify Drop:")
    print(f"  1. Dra mappen {OUT} till sidan som öppnas nu.")
    print("  2. Logga in/skapa konto när Netlify ber om det, annars raderas sidan efter en timme.")
    print("  3. Länken ser ut som https://<namn>.netlify.app – nästa gång: Deploys → dra in mappen igen.")
    webbrowser.open("https://app.netlify.com/drop")
    if os.name == "nt":
        os.startfile(OUT)


if __name__ == "__main__":
    main()
