# PopPunk no Jutsu website

Open index.html in your browser to preview the website.

This portable package contains:
- index.html: page structure, featured video, playlists and social links
- styles.css: black, hot pink and off-white responsive design
- covers.js: 31 verified YouTube video links, checked on 2026-10-20
- script.js: combined search, anime/style filters, reset and load-more behavior
- assets/: the channel's existing logo and banner

To add a cover, add an object at the top of COVERS in covers.js. Update the featured video in index.html when choosing a new release. The curated catalog does not automatically sync new uploads.

The public page contains no links to the owner's GitHub profile or repositories. This does not change the visibility of any existing GitHub repository.

## Publish to GitHub Pages

The intended website address is https://poppunknojutsu.github.io/.

1. Create a public repository named `poppunknojutsu.github.io` owned by the `PopPunkNoJutsu` organization.
2. Upload the contents of this folder, including `assets/` and `.nojekyll`. Keep `index.html` at the repository root; do not upload the ZIP itself or wrap the files inside another folder.
3. Commit the files to `main`.
4. Open the repository's Settings > Pages. Under Build and deployment, choose Deploy from a branch, then `main` and `/(root)`, and save.
5. Wait for GitHub's deployment to finish, then use the Visit site link.

No build commands or paid hosting plan are needed. The `.nojekyll` file tells GitHub to serve these static files directly.

Deployment status must be checked in GitHub; the address above is the intended address, not proof that the site is already live. Source checks passed. Browser visual checks are still pending.

Original channel artwork and third-party music, lyrics, characters and related material remain subject to their respective rights holders. The website includes the channel's Production Note and Copyright notice.
