"""WALTER deploy: bygger state.js och lägger en publicerbar kopia i deploy/.

  python fetcher/walter_deploy.py

Bara filerna i ALLOW kopieras – aldrig fetcher/, .env, etf_raw.json eller .venv.
Är WALTER_PAGES_REPO satt i fetcher/.env (t.ex. https://github.com/NAMN/walter.git)
pushas deploy/ till grenen gh-pages och sidan hamnar på https://NAMN.github.io/walter/.
Annars öppnas Netlify Drop, där deploy-mappen dras in för att få en https-länk.
Är mappen ett git-repo skickas även data/state.json till main, så att GitHub
Actionen (walter-auto.yml) bygger med samma journal nästa gång den hämtar.
"""

import os
import shutil
import subprocess
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "deploy"
ALLOW = ["index.html", "css", "js", "assets", "data/state.js", "data/cache.json", "reports"]
BLOCK = {".env", "etf_raw.json"}  # extra spärr om någon lägger något fel i en tillåten mapp

sys.path.insert(0, str(Path(__file__).resolve().parent))
from walter_fetch import load_env, warn  # noqa: E402


def build_state():
    r = subprocess.run([sys.executable, str(ROOT / "fetcher" / "walter_fetch.py"), "--offline"])
    if r.returncode:
        sys.exit("Kunde inte bygga state.js – deploy avbruten.")
    r = subprocess.run([sys.executable, str(ROOT / "fetcher" / "walter_k4.py")])
    if r.returncode:
        sys.exit("Kunde inte bygga K4/avgiftsrapport – deploy avbruten.")


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
            shutil.copytree(src, dst, ignore=lambda d, names: [n for n in names if n in BLOCK])
        else:
            shutil.copy2(src, dst)
    (OUT / ".nojekyll").write_text("", encoding="utf-8")  # GitHub Pages: servera filerna som de är
    leaked = [p for p in OUT.rglob("*") if p.name in BLOCK]
    if leaked:
        shutil.rmtree(OUT)
        sys.exit(f"Stoppat: {leaked} hamnade i deploy/. Inget publicerat.")


def git(*args, cwd=OUT):
    subprocess.run(["git", *args], cwd=cwd, check=True)


def push_source():
    """Lokalt: commit + push av state.json till main. Actionen gör aldrig detta."""
    if os.environ.get("GITHUB_ACTIONS") or not (ROOT / ".git").exists():
        return
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    subprocess.run(["git", "add", "data/state.json"], cwd=ROOT)
    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT).returncode:
        subprocess.run(["git", "commit", "-q", "-m", f"journal {stamp}"], cwd=ROOT)
    if subprocess.run(["git", "push", "-q"], cwd=ROOT).returncode:
        warn("Kunde inte pusha state.json till main – Actionen kör med förra journalen tills du kör git push.")


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
    build_state()
    copy_site()
    files = sum(1 for p in OUT.rglob("*") if p.is_file())
    print(f"deploy/ klar ({files} filer). Sidan är publik för alla som har länken.")

    repo = os.environ.get("WALTER_PAGES_REPO", "").strip()
    if repo:
        if not shutil.which("git"):
            sys.exit("git saknas – installera Git for Windows eller använd Netlify Drop.")
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
