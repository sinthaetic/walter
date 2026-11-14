# WALTER logos

Logofilerna ligger här:

| Fil | Innehåll | Används |
|---|---|---|
| `walter-symbol.svg` | Bara symbolen | Mobil topbar |
| `walter-wordmark.svg` | Bara ordet WALTER | (reserv) |
| `walter-full.svg` | Symbol + wordmark | Desktop topbar |

- Det är OK att ta fram nya logos och byta ut filerna (ändrat okt 2026).
- Spåren just nu: hexagon-W och kretskorts-W, i samma rena designspråk som appen.
- Wordmark i en färg: grafit på ljust, vit på mörkt. Ingen regnbågs-gradient eller gradient-text.

Är filerna PNG i stället för SVG: ändra bara `src` i `index.html`.

## Skisser (steg 2, okt 2026)
`skisser/` har fyra utkast, 64×64, grafit + teal. De används inte av sidan än.

| Fil | Spår |
|---|---|
| `skisser/hexagon-w-a.svg` | Linjehexagon runt W |
| `skisser/hexagon-w-b.svg` | Fylld hexagon, W utskuret |
| `skisser/kretskort-w-a.svg` | W med lödpunkter och ledningar |
| `skisser/kretskort-w-b.svg` | W i 45°-ledningar |

Teal-punkten är Walters "lampa" och finns i alla fyra. Se ritytan "Logoskisser" i designskissen (länk i docs/ROADMAP.md).
När en variant är vald: gör om den till walter-symbol/-full/-wordmark.svg (steg 7).

## Vald logo (22 okt 2026): "Inskriven"
Hexagon som är öppen upptill, W:ets spetsar sitter i hexagonens hörn, teal-lampan i öppningen.
Filerna ligger i `vald/` och används av `index.html` och `cipher.html` (inkopplade i steg 7). De gamla namnen i tabellen överst finns inte längre.

| Fil | Används till |
|---|---|
| `vald/walter-symbol-ljust.svg` | Symbol på ljus bakgrund (grafit + teal) |
| `vald/walter-symbol-morkt.svg` | Symbol på mörk bakgrund (vit + ljus teal) |
| `vald/walter-favicon.svg` | Flikikon, grövre streck, byter färg med ljust/mörkt |
| `vald/walter-appikon.svg` | Appikon / hemskärm (mörk ruta) |

Ordet W A L T E R skrivs som text i Jost (500, spärrning 0.62em) bredvid symbolen, inte som bild.
Tunt streck (2.4) från 40 px och uppåt, grovt (4.5) för 32 px och mindre.
