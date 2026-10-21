"""Merge YouTube's public upload feed into the full, retained channel catalog."""

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

CHANNEL_ID = "UCroKf5_gPSKi63fmIl7OymQ"
FEED_URL = f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}"
NS = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}
VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
SERIES = [
    ("BLEACH", r"\bbleach\b"),
    ("NARUTO", r"\bnaruto\b|\bboruto\b"),
    ("DRAGON BALL", r"\bdragon\s*ball\b"),
    ("BLACK CLOVER", r"\bblack clover\b"),
    ("DIGIMON", r"\bdigimon\b"),
    ("SWORD ART ONLINE", r"\bsword art online\b"),
    ("ONE PIECE", r"\bone piece\b"),
    ("JUJUTSU KAISEN", r"\bjujutsu kaisen\b"),
    ("SOUL EATER", r"\bsoul eater\b"),
]


def describe_video(raw_title, video_id):
    """Keep the complete source title; derive concise, searchable card labels."""
    raw_title = " ".join(raw_title.split())
    if not raw_title or not VIDEO_ID.fullmatch(video_id):
        raise ValueError("A video needs a title and a valid YouTube ID.")
    quoted = re.search(r"「(.+?)」", raw_title)
    title = quoted.group(1).strip() if quoted else raw_title
    remainder = raw_title[quoted.end():] if quoted else ""
    for variant in ("TV Size", "Re:Mix Edit", "Re:Make"):
        if variant.lower() in remainder.lower():
            title += f" ({variant})"
    anime_match = re.search(r"(?:\s[-–—]\s*|ver\s*-\s*)(.+)", remainder, re.I)
    anime = anime_match.group(1) if anime_match else ""
    anime = re.sub(r"\s*\|\s*(?:by\s+)?PopPunk no Jutsu.*$", "", anime, flags=re.I).strip()
    series = next((label for label, pattern in SERIES if re.search(pattern, raw_title, re.I)), "OTHER")
    if re.search(r"\bacoustic\b", raw_title, re.I):
        style = "Acoustic"
    elif re.search(r"\borchestra(?:l)?\b|\bepic\b", raw_title, re.I):
        style = "Orchestral"
    elif re.search(r"\benglish\b", raw_title, re.I):
        style = "English covers"
    elif re.search(r"\bjapanese\b", raw_title, re.I):
        style = "Japanese covers"
    elif re.search(r"\bpop rock\b", raw_title, re.I):
        style = "Pop rock"
    else:
        style = "Covers"
    return {
        "youtubeId": video_id, "rawTitle": raw_title, "title": title,
        "anime": anime or (series.title() if series != "OTHER" else "PopPunk no Jutsu"),
        "series": series, "style": style,
    }


def parse_feed(xml):
    root = ET.fromstring(xml)
    channel = root.findtext("yt:channelId", "", NS)
    # YouTube currently omits UC on the feed-level ID, but includes it on entries.
    if channel not in (CHANNEL_ID, CHANNEL_ID[2:]):
        raise ValueError("The feed does not belong to the expected channel.")
    entries = []
    seen = set()
    for entry in root.findall("a:entry", NS):
        if entry.findtext("yt:channelId", "", NS) != CHANNEL_ID:
            raise ValueError("An entry belongs to a different channel.")
        video_id = entry.findtext("yt:videoId", "", NS)
        if video_id in seen:
            continue
        video = describe_video(entry.findtext("a:title", "", NS), video_id)
        published = entry.findtext("a:published", "", NS)
        parsed_date = datetime.fromisoformat(published.replace("Z", "+00:00"))
        if parsed_date.tzinfo is None:
            raise ValueError("Upload dates must include a timezone.")
        video["publishedAt"] = parsed_date.astimezone(timezone.utc).isoformat()
        seen.add(video_id)
        entries.append(video)
    if not entries:
        raise ValueError("YouTube returned an empty feed; the saved catalog will be preserved.")
    return sorted(entries, key=lambda entry: entry["publishedAt"], reverse=True)


def merge_feed(catalog, incoming):
    result = copy.deepcopy(catalog)
    existing = {video["youtubeId"]: video for video in result["videos"]}
    if len(existing) != len(result["videos"]):
        raise ValueError("The saved catalog contains duplicate IDs.")
    additions = []
    for item in incoming:
        if item["youtubeId"] in existing:
            existing[item["youtubeId"]].update(item)
        else:
            additions.append(item)
    # Old uploads are deliberately retained: the feed contains only recent uploads.
    combined = additions + result["videos"]
    known_dates = sorted(
        (video for video in combined if video.get("publishedAt")),
        key=lambda video: video["publishedAt"], reverse=True,
    )
    undated_history = [video for video in combined if not video.get("publishedAt")]
    result["videos"] = known_dates + undated_history
    result["lastCheckedDate"] = datetime.now(timezone.utc).date().isoformat()
    return result


def save_catalog(catalog, directory):
    videos = catalog["videos"]
    if not videos or len({v["youtubeId"] for v in videos}) != len(videos):
        raise ValueError("Refusing to save an empty or duplicate catalog.")
    for video in videos:
        if not VIDEO_ID.fullmatch(video["youtubeId"]):
            raise ValueError("Invalid video ID in catalog.")
    metadata = {key: catalog[key] for key in ("channelId", "lastCheckedDate")}
    outputs = {
        "catalog.json": json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        "covers.js": (
            "// Generated from catalog.json. New uploads are synced by GitHub Actions.\n"
            + "const CHANNEL = " + json.dumps(metadata, ensure_ascii=False) + ";\n"
            + "const COVERS = " + json.dumps(videos, ensure_ascii=False, indent=2) + ";\n"
        ),
    }
    page = directory / "index.html"
    if page.exists():
        # A changed catalog gets a new URL so returning browsers do not reuse old songs.
        version = hashlib.sha256(outputs["covers.js"].encode("utf-8")).hexdigest()[:16]
        source = page.read_text(encoding="utf-8")
        updated, count = re.subn(
            r'(<script\s+src=")covers\.js(?:\?[^"\s]*)?("\s+defer></script>)',
            lambda match: match[1] + f"covers.js?v={version}" + match[2], source,
        )
        if count != 1:
            raise ValueError("Expected exactly one catalog script reference in the page.")
        outputs["index.html"] = updated
    for name, content in outputs.items():
        destination = directory / name
        if destination.exists() and destination.read_text(encoding="utf-8") == content:
            continue
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.write_text(content, encoding="utf-8", newline="\n")
        temporary.replace(destination)


def fetch_feed():
    for attempt in range(3):
        try:
            request = Request(FEED_URL, headers={"User-Agent": "PopPunkNoJutsu-Website/1.0", "Accept": "application/atom+xml"})
            with urlopen(request, timeout=30) as response:
                return response.read(2_000_001)
        except Exception:
            if attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))


def parse_channel_uploads(data):
    if not isinstance(data, dict) or (data.get("channel_id") or data.get("id")) != CHANNEL_ID:
        raise ValueError("Upload response belongs to a different channel.")
    if not isinstance(data.get("entries"), list) or not data["entries"]:
        raise ValueError("The channel returned no uploads; the saved catalog will be preserved.")
    videos, seen = [], set()
    for entry in data["entries"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("title"), str):
            raise ValueError("Incomplete channel upload response.")
        video = describe_video(entry["title"], entry.get("id", ""))
        if video["youtubeId"] not in seen:
            videos.append(video)
            seen.add(video["youtubeId"])
    return videos


def merge_channel_uploads(catalog, incoming):
    """The public Videos tab supplies newest-first order but not reliable dates."""
    if not incoming or catalog.get("channelId") != CHANNEL_ID:
        raise ValueError("Invalid channel upload catalog.")
    result = copy.deepcopy(catalog)
    existing = {video["youtubeId"]: video for video in result["videos"]}
    if len(existing) != len(result["videos"]):
        raise ValueError("Duplicate saved video IDs.")
    ordered, seen = [], set()
    for video in incoming:
        video_id = video["youtubeId"]
        if video_id in seen or not VIDEO_ID.fullmatch(video_id):
            raise ValueError("Invalid or duplicate incoming video IDs.")
        saved = copy.deepcopy(existing.get(video_id, {}))
        saved.update(video)
        ordered.append(saved)
        seen.add(video_id)
    result["videos"] = ordered + [video for video in result["videos"] if video["youtubeId"] not in seen]
    result["lastCheckedDate"] = datetime.now(timezone.utc).date().isoformat()
    return result


def fetch_channel_uploads():
    from yt_dlp import YoutubeDL
    options = {"extract_flat": True, "skip_download": True, "quiet": True,
               "playlistend": 50, "socket_timeout": 30, "retries": 3,
               "extractor_retries": 3, "ignoreerrors": False, "cachedir": False}
    with YoutubeDL(options) as youtube:
        return youtube.extract_info(f"https://www.youtube.com/channel/{CHANNEL_ID}/videos", download=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, default=Path(__file__).resolve().parent)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--feed-file", type=Path, help="Use a saved feed for an offline check.")
    source.add_argument("--render-only", action="store_true")
    source.add_argument("--channel-page", action="store_true", help="Use the public Videos tab if the feed is unavailable.")
    args = parser.parse_args()
    catalog = json.loads((args.directory / "catalog.json").read_text(encoding="utf-8"))
    if catalog["channelId"] != CHANNEL_ID:
        raise ValueError("Catalog channel mismatch.")
    if not args.render_only:
        old_count = len(catalog["videos"])
        if args.channel_page:
            catalog = merge_channel_uploads(catalog, parse_channel_uploads(fetch_channel_uploads()))
        else:
            xml = args.feed_file.read_bytes() if args.feed_file else fetch_feed()
            if len(xml) > 2_000_000:
                raise ValueError("Unexpectedly large feed.")
            catalog = merge_feed(catalog, parse_feed(xml))
        print(f"Checked YouTube: {len(catalog['videos'])} uploads; {len(catalog['videos']) - old_count} new.")
    save_catalog(catalog, args.directory)


if __name__ == "__main__":
    main()
