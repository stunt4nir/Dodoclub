# Club Dodo — GitHub Pages Deployment

The web version of this app is automatically published to GitHub Pages on every
push to `main` via the workflow at `.github/workflows/gh-pages.yml`.

## ⚙️ One-time GitHub repository setup

After pushing this code to a GitHub repo, do this **once**:

1. Open your repo on github.com → **Settings** → **Pages** (left sidebar).
2. Under "Build and deployment" → **Source**, select **GitHub Actions**.
3. (No need to pick a branch — the workflow uploads the artifact directly.)
4. Push any commit to `main` (or trigger the workflow manually under
   **Actions** → "Deploy Web to GitHub Pages" → **Run workflow**).
5. After ~2 minutes, the Pages section will show your live URL, typically:
   `https://<your-username>.github.io/<repo-name>/`

## 🔁 Updating

Any future `git push origin main` re-runs the workflow and republishes the
site. No manual rebuild needed.

## 🧠 What the workflow does under the hood

* Installs frontend dependencies with yarn.
* Runs `npx expo export -p web` with `EXPO_PUBLIC_BACKEND_URL` set to the
  permanent backend (`https://dodo-roster-build.emergent.host`).
* Adds three small files for GitHub Pages SPA support:
  * `.nojekyll` — stops GitHub from stripping the `_expo/` build folder.
  * `404.html` — encodes any unknown path into a query string and reloads
    `index.html` (the *spa-github-pages* trick).
  * Inline `<script>` injected at the top of `index.html` that decodes that
    query string back into the SPA's history, so deep links like
    `/match/<id>` work after refresh.
* Uploads `frontend/dist/` to GitHub Pages.

## 🔌 Backend

The backend (FastAPI + MongoDB) runs on Emergent at
`https://dodo-roster-build.emergent.host`. The web build is hard-coded to
this URL at build time. If the backend URL ever changes, update both
`frontend/.env` AND the `EXPO_PUBLIC_BACKEND_URL` in
`.github/workflows/gh-pages.yml` so the next push picks it up.

## 🔑 Admin credentials

* Email: `admin@clubdodo.com`
* Password: `dodo2026`
