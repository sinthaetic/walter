"""Skriver testfixturer under tests/fixtures/. Kör om när motorn ändras:
  .venv/Scripts/python.exe tests/make_fixtures.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures"
sys.path.insert(0, str(ROOT / "fetcher"))

import walter_vault  # noqa: E402


def vault_sample():
    env = walter_vault.encrypt({"hej": "världen", "n": 1.5}, "TEST-KOD", iter=1000)
    (FIX / "vault-sample.enc").write_text(json.dumps(env), encoding="utf-8")


def main():
    FIX.mkdir(parents=True, exist_ok=True)
    vault_sample()
    print("Fixturer skrivna i", FIX)


if __name__ == "__main__":
    main()
