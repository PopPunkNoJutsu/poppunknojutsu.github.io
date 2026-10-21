"""Refresh public channel playlists while preserving the last good catalog."""

import argparse
import copy
from datetime import datetime, timezone
from html import escape
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, urlparse

from sync_youtube import CHANNEL_ID

PLAYLISTS_URL = f"https://www.youtube.com/channel/{CHANNEL_ID}/playlists"
PRIMARY_PLAYLIST_ID = "PLXM9R4S5hc7wzOnasLTO2ouKTpyLMhPzM"
PLAYLIST_ID = re.compile(r"^PL[A-Za-z0-9_-]{8,80}$")
START = "<!-- channel-playlists:start -->"
END = "<!-- channel-playlists:end -->"
VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
# Representative artwork from the channel's own published covers.
PLAYLIST_PRESENTATION = {
    PRIMARY_PLAYLIST_ID: ("elv_X95JL2s", "Every mood. Every riff. Your next favorite is in here."),
    "PLFhfmTNiH8Xk": ("qBCZv6YjbcI", "Go beyond your limits. Dragon Ball anthems, reimagined."),
    "PLKU6UnEzQKJQ": ("jg0U0WIeF0g", "Naruto nostalgia, turned all the way up."),
    "PLEFYXxnAimMY": ("wPWuA4Dzonk", "Soul Reaper energy. Familiar anthems, a new voice."),
    "PLffHg5_PW3PY": ("WckpvKtTypY", "Stay for the credits. Bleach endings that hit home."),
    "PLdqjayG3bq2U": ("ZRSMHHV9gd0", "Big scenes. Bigger feelings. Step back into the soundtrack."),
    "PLAcaGRK69mik": ("tJSpWKxx7pc", "Acoustic arrangements. All the anime feels."),
    "PLBe0yam0zKug": ("LnBxH_aBpKg", "One opening leads to another. Relive the Bleach journey."),
}


def validate_playlists(items):
    if not isinstance(items, list) or not items:
        raise ValueError("An empty playlist response must not replace the saved catalog.")
    seen = set()
    for item in items:
        if not isinstance(item, dict) or not PLAYLIST_ID.fullmatch(item.get("id", "")):
            raise ValueError("Invalid playlist ID.")
        if not isinstance(item.get("title"), str) or not item["title"].strip():
            raise ValueError("Missing playlist title.")
        if item["id"] in seen:
            raise ValueError("Duplicate playlist ID.")
        seen.add(item["id"])


def parse_channel_playlists(data):
    if not isinstance(data, dict) or (data.get("channel_id") or data.get("id")) != CHANNEL_ID:
        raise ValueError("Playlist response belongs to a different channel.")
    entries = data.get("entries")
    if not isinstance(entries, list):
        raise ValueError("Missing channel playlist entries.")
    playlists = []
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Incomplete playlist response.")
        playlist_id = entry.get("id", "")
        title = entry.get("title")
        if not isinstance(title, str):
            raise ValueError("Incomplete playlist title.")
        item = {"id": playlist_id, "title": " ".join(title.split())}
        validate_playlists([item])
        if entry.get("url"):
            url = urlparse(entry["url"])
            if (url.scheme != "https" or url.hostname not in ("www.youtube.com", "youtube.com")
                    or url.path != "/playlist" or parse_qs(url.query).get("list") != [playlist_id]):
                raise ValueError("Unexpected playlist URL.")
        if playlist_id not in seen:
            seen.add(playlist_id)
            playlists.append(item)
    validate_playlists(playlists)
    return playlists


def merge_playlists(catalog, incoming):
    if catalog.get("channelId") != CHANNEL_ID:
        raise ValueError("Saved playlist channel mismatch.")
    validate_playlists(catalog["playlists"])
    validate_playlists(incoming)
    result = copy.deepcopy(catalog)
    seen = {item["id"] for item in incoming}
    # Missing records are retained so a partial channel response cannot erase cards.
    combined = copy.deepcopy(incoming) + [item for item in result["playlists"] if item["id"] not in seen]
    result["playlists"] = sorted(combined, key=lambda item: item["id"] != PRIMARY_PLAYLIST_ID)
    result["lastCheckedDate"] = datetime.now(timezone.utc).date().isoformat()
    return result


def title_parts(title):
    for suffix in ("FULL PLAYLIST", "ENGLISH COVERS", "OST"):
        if title.upper().endswith(" " + suffix):
            return title[:-len(suffix)].rstrip(" |-"), title[-len(suffix):]
    return title, ""


def playlist_presentation(item, videos):
    available = [video for video in videos if isinstance(video, dict)
                 and VIDEO_ID.fullmatch(str(video.get("youtubeId", "")))]
    curated, description = PLAYLIST_PRESENTATION.get(
        item["id"], (None, "A fresh mix from PopPunk no Jutsu. Find your next favorite."))
    if curated and any(video["youtubeId"] == curated for video in available):
        return curated, description
    # New playlists get relevant channel artwork without downloading any media.
    title = item["title"].upper()
    series = next((name for name in sorted({video.get("series", "") for video in available}, key=len, reverse=True)
                   if name and name != "OTHER" and name in title), None)
    style = next((style for word, style in (("ACOUSTIC", "Acoustic"), ("ORCHESTRAL", "Orchestral"),
                                           ("ENGLISH", "English covers")) if word in title), None)
    kind = "ED" if "ENDING" in title else "OP" if "OPENING" in title else "OST" if re.search(r"\bOST\b", title) else None
    if series or style or kind:
        for video in available:
            context = f'{video.get("anime", "")} {video.get("rawTitle", "")}'.upper()
            if ((not series or video.get("series") == series)
                    and (not style or video.get("style") == style)
                    and (not kind or re.search(rf"\b{kind}\b", context))):
                return video["youtubeId"], description
    # A branded image is preferable to unrelated music when no match is known.
    return None, description


def render_playlists(catalog, source, videos=()):
    validate_playlists(catalog["playlists"])
    if source.count(START) != 1 or source.count(END) != 1:
        raise ValueError("The page must have exactly one playlist section marker pair.")
    start, end = source.index(START), source.index(END)
    if start >= end:
        raise ValueError("Invalid playlist section markers.")
    cards = []
    ordered = sorted(catalog["playlists"], key=lambda item: item["id"] != PRIMARY_PLAYLIST_ID)
    for number, item in enumerate(ordered, 1):
        title, subtitle = title_parts(item["title"])
        secondary = f"<span>{escape(subtitle)}</span>" if subtitle else ""
        video_id, description = playlist_presentation(item, videos)
        thumbnail = f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg" if video_id else "assets/channel-banner.jpg"
        video_attribute = f' data-video-id="{video_id}"' if video_id else ""
        cards.append(
            f'          <a class="playlist-card" href="https://www.youtube.com/playlist?list={item["id"]}" '
            f'target="_blank" rel="noopener noreferrer" aria-label="{escape(item["title"], quote=True)}">'
            f'<span class="playlist-art"><img src="{thumbnail}"{video_attribute} alt="" '
            'width="1280" height="720" loading="lazy" decoding="async">'
            f'<span class="playlist-number">{number:02d}</span>'
            '<span class="playlist-play" aria-hidden="true">▶</span></span>'
            '<span class="playlist-body">'
            f'<span class="playlist-title">{escape(title)}{secondary}</span>'
            f'<span class="playlist-description">{escape(description)}</span>'
            '<span class="playlist-bottom">Play playlist <b aria-hidden="true">↗</b></span></span></a>'
        )
    return source[:start + len(START)] + "\n" + "\n".join(cards) + "\n          " + source[end:]


def save_playlists(catalog, directory):
    if catalog.get("channelId") != CHANNEL_ID:
        raise ValueError("Saved playlist channel mismatch.")
    source = (directory / "index.html").read_text(encoding="utf-8")
    # Validate and render before either file is touched.
    video_path = directory / "catalog.json"
    video_catalog = json.loads(video_path.read_text(encoding="utf-8")) if video_path.exists() else {"channelId": CHANNEL_ID, "videos": []}
    if video_catalog.get("channelId") != CHANNEL_ID:
        raise ValueError("Playlist artwork channel mismatch.")
    rendered = render_playlists(catalog, source, video_catalog.get("videos", []))
    outputs = {"playlists.json": json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", "index.html": rendered}
    for name, content in outputs.items():
        destination = directory / name
        if destination.exists() and destination.read_text(encoding="utf-8") == content:
            continue
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.write_text(content, encoding="utf-8", newline="\n")
        temporary.replace(destination)


def fetch_playlists():
    # Flat extraction reads playlist metadata and pagination, never video/audio files.
    from yt_dlp import YoutubeDL
    options = {"extract_flat": True, "skip_download": True, "quiet": True,
               "socket_timeout": 30, "retries": 3, "extractor_retries": 3,
               "ignoreerrors": False, "cachedir": False}
    with YoutubeDL(options) as youtube:
        return youtube.extract_info(PLAYLISTS_URL, download=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--input-file", type=Path, help="Use extracted channel JSON for an offline check.")
    parser.add_argument("--render-only", action="store_true")
    args = parser.parse_args()
    catalog = json.loads((args.directory / "playlists.json").read_text(encoding="utf-8"))
    if not args.render_only:
        data = json.loads(args.input_file.read_text(encoding="utf-8")) if args.input_file else fetch_playlists()
        old_ids = {item["id"] for item in catalog["playlists"]}
        catalog = merge_playlists(catalog, parse_channel_playlists(data))
        added = len({item["id"] for item in catalog["playlists"]} - old_ids)
        print(f"Checked YouTube playlists: {len(catalog['playlists'])} playlists; {added} new.")
    else:
        catalog["playlists"] = sorted(catalog["playlists"], key=lambda item: item["id"] != PRIMARY_PLAYLIST_ID)
    save_playlists(catalog, args.directory)


if __name__ == "__main__":
    main()
