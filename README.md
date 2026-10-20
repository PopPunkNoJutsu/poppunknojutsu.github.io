# PopPunk no Jutsu

Website: https://poppunknojutsu.github.io/

The complete public channel catalog is searchable by song, anime and style. The initial collection contains all 81 uploads visible on the channel on October 20, 2026. The About section, Production Note and Copyright Notice reproduce the channel description on that date.

## Automatic updates

The GitHub Actions workflow **Update channel and publish website** checks YouTube's public upload feed hourly, at minute 17. GitHub may delay scheduled runs, so updates are not instant.

- New public uploads are added without editing website files.
- The featured Latest Drop follows the newest catalog entry.
- Titles, thumbnails and YouTube links come from the channel.
- Anime and style labels are inferred from the video title. An unfamiliar series is grouped under Other.
- Older uploads remain saved when they leave YouTube's recent-upload feed.
- If YouTube is unavailable or returns invalid data, the saved catalog remains intact and the next hourly run retries.
- No YouTube API key, password or paid service is needed.

The feed contains only the latest 15 uploads. A long interruption that spans more than 15 uploads needs a catalog backfill. This process adds public uploads; it does not automatically remove deleted/private older videos. Channel-description changes can be copied into the website separately.

The workflow saves a date of its last successful check daily, even when there are no new uploads, keeping a record of successful checks. GitHub can disable schedules after prolonged repository inactivity; check Actions if updates ever stop.

## Update now

Open the repository's **Actions** tab, choose **Update channel and publish website**, and select **Run workflow**. The run summary reports whether YouTube was checked successfully and how many uploads are saved.

GitHub Pages must use **Settings > Pages > Source: GitHub Actions**. This workflow deploys the website directly; it does not rely on a bot commit triggering another Pages build.

## Files

- `index.html`: page content, channel description and social links
- `styles.css`: responsive black, pink and off-white design
- `script.js`: search, filters, latest feature and load-more controls
- `catalog.json`: retained source catalog and channel description
- `covers.js`: generated catalog used by the page
- `sync_youtube.py`: feed validation, merging and catalog generation
- `test_sync_youtube.py`: updater tests
- `.github/workflows/update-site.yml`: hourly update and publishing workflow
- `assets/`: existing channel artwork

To correct a catalog label manually, edit `catalog.json` and run `python sync_youtube.py --render-only`. For entries still in the recent feed, the next sync derives labels again from the title.

The website does not link to the personal GitHub profile. The public repository's commit history still identifies contributors.

Original music, lyrics, characters, images, logos and related intellectual property remain with their respective rights holders.
