# AlibiMe — landing site

A self-contained "coming soon" landing page (single `index.html`, no build step,
no dependencies). Uses the AlibiMe brand palette and a glassy look matching the
app.

## Preview locally

Just open it:

```bash
open website/index.html
```

…or serve it:

```bash
cd website && python3 -m http.server 8080   # then visit http://localhost:8080
```

## Deploy via GitHub Pages

1. Push to GitHub (already done if you're reading this in the repo).
2. Repo **Settings → Pages**.
3. **Source:** Deploy from a branch → branch `main`, folder `/website`.
4. Save. The site goes live at `https://loukra.github.io/AlibiMe/` after a minute.

(If you'd rather serve it at the repo root or a custom domain, move `index.html`
+ `icon.png` accordingly and update the Pages folder setting / add a `CNAME`.)

## Files

- `index.html` — the page (HTML + inline CSS).
- `icon.png` — the AlibiMe app icon (also used as favicon + social preview).
