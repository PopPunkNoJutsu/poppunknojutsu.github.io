import json
from pathlib import Path
import tempfile
import unittest
from sync_youtube import (CHANNEL_ID, describe_video, merge_feed, parse_feed, save_catalog,
                          parse_channel_uploads, merge_channel_uploads)


def feed(entries, channel=CHANNEL_ID):
    return (
        '<feed xmlns="http://www.w3.org/2005/Atom" xmlns:yt="http://www.youtube.com/xml/schemas/2015">'
        f"<yt:channelId>{channel}</yt:channelId>{entries}</feed>"
    )


def entry(video_id, title="「New &amp; Loud」Acoustic English Ver - Naruto OP 1", date="2026-10-20T12:00:00Z"):
    return (
        f"<entry><yt:channelId>{CHANNEL_ID}</yt:channelId><yt:videoId>{video_id}</yt:videoId>"
        f"<title>{title}</title><published>{date}</published></entry>"
    )


class SyncTests(unittest.TestCase):
    def test_sonic_games_and_versions_share_one_category(self):
        for title, style in (
            ("Dreams of an Absolution - Sonic the Hedgehog (2006) | Anime Opening", "English covers"),
            ("Live and Learn - Sonic Adventure 2 | Pop Punk Cover", "English covers"),
            ("SONIC FRONTIERS - Acoustic Cover", "Acoustic"),
            ("Sonic X - Epic Orchestral Ver", "Orchestral"),
            ("I Am All of Me - Shadow the Hedgehog | Pop Punk Cover", "English covers"),
        ):
            with self.subTest(title=title):
                video = describe_video(title, "Abc123_-xyz")
                self.assertEqual(video["series"], "SONIC THE HEDGEHOG")
                self.assertEqual(video["style"], style)
        self.assertEqual(describe_video("Supersonic - New Anime", "Abc123_-xyz")["series"], "OTHER")

    def test_retained_sonic_upload_moves_out_of_other(self):
        old = describe_video("Dreams of an Absolution - Sonic the Hedgehog (2006)", "wjQiIlEc72c")
        old.update(series="OTHER", title="Dreams of an Absolution", anime="Sonic the Hedgehog (2006)",
                   publishedAt="2026-11-13T22:00:34+00:00")
        unrelated = describe_video("New game cover", "Abc123_-xyz")
        catalog = {"channelId": CHANNEL_ID, "lastCheckedDate": "2026-11-14", "videos": [old, unrelated]}
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder:
            save_catalog(catalog, Path(folder))
            saved = json.loads((Path(folder) / "catalog.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["videos"], [dict(old, series="SONIC THE HEDGEHOG"), unrelated])
            self.assertEqual(catalog["videos"][0]["series"], "OTHER")
            self.assertIn('"series": "SONIC THE HEDGEHOG"', (Path(folder) / "covers.js").read_text(encoding="utf-8"))

    def test_regular_cover_titles_default_to_english(self):
        for title in (
            "Blue Bird | Anime Opening",
            "Naruto OP 1 - Pop Punk Cover",
            "Bleach Ending - POP-PUNK COVER",
            "Digimon - PopPunk Cover",
            "Treachery - Pop Rock ver - BLEACH OST",
            "Anime ending cover",
            "New song",
        ):
            with self.subTest(title=title):
                self.assertEqual(describe_video(title, "Abc123_-xyz")["style"], "English covers")

    def test_specific_versions_keep_their_categories(self):
        for title, style in (
            ("Anime Opening - Acoustic English Cover", "Acoustic"),
            ("Pop Punk Cover - Epic Orchestral Ver", "Orchestral"),
            ("Anime Opening - Orchestra Cover", "Orchestral"),
            ("Anime Opening - Japanese Pop Punk Cover", "Japanese covers"),
        ):
            with self.subTest(title=title):
                self.assertEqual(describe_video(title, "Abc123_-xyz")["style"], style)

    def test_saved_history_is_recategorized_without_changing_other_metadata(self):
        old = describe_video("Old anime opening - Pop Punk Cover", "Abc123_-xyz")
        old.update(style="Covers", title="Curated song name", anime="Custom anime label",
                   publishedAt="2026-09-01T12:00:00+00:00")
        rock = describe_video("Treachery - Pop Rock ver", "New123_-xyz")
        rock["style"] = "Pop rock"
        catalog = {"channelId": CHANNEL_ID, "lastCheckedDate": "2026-11-14", "videos": [old, rock]}
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder:
            directory = Path(folder)
            page = directory / "index.html"
            page.write_text('<script src="covers.js?v=old" defer></script>', encoding="utf-8")
            save_catalog(catalog, directory)
            saved = json.loads((directory / "catalog.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["videos"], [dict(old, style="English covers"), dict(rock, style="English covers")])
            self.assertEqual(catalog["videos"][0]["style"], "Covers")
            self.assertEqual(catalog["videos"][1]["style"], "Pop rock")
            generated = (directory / "covers.js").read_text(encoding="utf-8")
            self.assertIn('"style": "English covers"', generated)
            self.assertNotIn('"style": "Covers"', generated)
            self.assertNotIn('"style": "Pop rock"', generated)
            first = page.read_text(encoding="utf-8")
            self.assertNotIn("covers.js?v=old", first)
            save_catalog(saved, directory)
            self.assertEqual(page.read_text(encoding="utf-8"), first)

    def test_channel_backup_preserves_history_dates_and_newest_first_order(self):
        old = [describe_video(f"Old {i}", f"old{i:08}") for i in range(81)]
        old[0]["publishedAt"] = "2026-10-20T12:00:00+00:00"
        catalog = {"channelId": CHANNEL_ID, "videos": old, "lastCheckedDate": "2026-10-20"}
        incoming = parse_channel_uploads({"channel_id": CHANNEL_ID, "entries": [
            {"id": "New123_-xyz", "title": "Newest upload"},
            {"id": old[0]["youtubeId"], "title": "Renamed older upload"}]})
        merged = merge_channel_uploads(catalog, incoming)
        self.assertEqual(len(merged["videos"]), 82)
        self.assertEqual(merged["videos"][0]["youtubeId"], "New123_-xyz")
        self.assertNotIn("publishedAt", merged["videos"][0])
        self.assertEqual(merged["videos"][1]["publishedAt"], old[0]["publishedAt"])
        self.assertEqual(merged["videos"][1]["title"], "Renamed older upload")
        self.assertEqual(merge_channel_uploads(merged, incoming), merged)
        self.assertEqual(len(catalog["videos"]), 81)

    def test_channel_backup_rejects_incomplete_or_wrong_channel_data(self):
        for data in (None, {"id": "wrong", "entries": []}, {"id": CHANNEL_ID, "entries": []},
                     {"id": CHANNEL_ID, "entries": [None]},
                     {"id": CHANNEL_ID, "entries": [{"id": "bad", "title": "Invalid"}]}):
            with self.subTest(data=data), self.assertRaises(ValueError):
                parse_channel_uploads(data)

    def test_parses_real_feed_id_format_and_xml_entities(self):
        videos = parse_feed(feed(entry("Abc123_-xyz"), CHANNEL_ID[2:]))
        self.assertEqual(videos[0]["title"], "New & Loud")
        self.assertEqual(videos[0]["style"], "Acoustic")
        self.assertEqual(videos[0]["series"], "NARUTO")

    def test_new_upload_and_title_change_preserve_entire_history(self):
        old = [describe_video(f"Old {i}", f"old{i:08}") for i in range(81)]
        catalog = {"channelId": CHANNEL_ID, "videos": old, "lastCheckedDate": "2026-10-19"}
        incoming = parse_feed(feed(entry("Abc123_-xyz") + entry(old[0]["youtubeId"], "Renamed upload")))
        merged = merge_feed(catalog, incoming)
        self.assertEqual(len(merged["videos"]), 82)
        self.assertEqual(merged["videos"][0]["youtubeId"], "Abc123_-xyz")
        self.assertEqual(merged["videos"][1]["title"], "Renamed upload")
        self.assertEqual(merged["videos"][-1]["youtubeId"], old[-1]["youtubeId"])
        self.assertEqual(merge_feed(merged, incoming), merged)
        self.assertEqual(catalog["videos"][0]["title"], "Old 0")

    def test_invalid_or_empty_feeds_fail(self):
        for xml in ("not XML", feed(""), feed(entry("bad")), feed(entry("Abc123_-xyz"), "other-channel")):
            with self.assertRaises(Exception):
                parse_feed(xml)

    def test_deduplicates_and_sorts_publication_dates(self):
        xml = feed(entry("Abc123_-xyz", date="2026-10-19T12:00:00Z") + entry("New123_-xyz") + entry("New123_-xyz"))
        self.assertEqual([v["youtubeId"] for v in parse_feed(xml)], ["New123_-xyz", "Abc123_-xyz"])

    def test_variants_unknown_series_and_japanese(self):
        video = describe_video("「Onogami」English Ver (TV Size) - Dragon Ball Super OP 1 | PopPunk no Jutsu", "Abc123_-xyz")
        self.assertIn("(TV Size)", video["title"])
        self.assertEqual(video["anime"], "Dragon Ball Super OP 1")
        video = describe_video("「New Song」Japanese ver - A New Anime OP 1", "Abc123_-xyz")
        self.assertEqual(video["style"], "Japanese covers")
        self.assertEqual(video["series"], "OTHER")

    def test_output_keeps_unicode_and_all_uploads(self):
        catalog = {"channelId": CHANNEL_ID, "lastCheckedDate": "2026-10-20", "videos": [describe_video("「希望」English Ver - BLEACH OP 1", "Abc123_-xyz")]}
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder:
            save_catalog(catalog, Path(folder))
            saved = json.loads((Path(folder) / "catalog.json").read_text(encoding="utf-8"))
            self.assertEqual(saved, catalog)
            self.assertIn("const COVERS =", (Path(folder) / "covers.js").read_text(encoding="utf-8"))

    def test_catalog_url_changes_only_when_catalog_content_changes(self):
        catalog = {"channelId": CHANNEL_ID, "lastCheckedDate": "2026-10-20", "videos": [describe_video("First", "Abc123_-xyz")]}
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder:
            directory = Path(folder)
            page = directory / "index.html"
            page.write_text('<script src="covers.js" defer></script><p>Keep this message</p>', encoding="utf-8")
            save_catalog(catalog, directory)
            first = page.read_text(encoding="utf-8")
            self.assertIn('covers.js?v=', first)
            save_catalog(catalog, directory)
            self.assertEqual(page.read_text(encoding="utf-8"), first)
            catalog["videos"].append(describe_video("Second", "New123_-xyz"))
            save_catalog(catalog, directory)
            self.assertNotEqual(page.read_text(encoding="utf-8"), first)
            self.assertIn('<p>Keep this message</p>', page.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
