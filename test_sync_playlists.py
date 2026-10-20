import copy
import json
from pathlib import Path
import tempfile
import unittest

from sync_playlists import (CHANNEL_ID, PRIMARY_PLAYLIST_ID, START, END,
                            merge_playlists, parse_channel_playlists, render_playlists, save_playlists)


def playlist(playlist_id="PLKU6UnEzQKJQ", title="NARUTO ENGLISH COVERS"):
    return {"id": playlist_id, "title": title}


def catalog():
    return {"channelId": CHANNEL_ID, "lastCheckedDate": None,
            "playlists": [playlist(), playlist(PRIMARY_PLAYLIST_ID, "POPPUNK NO JUTSU FULL PLAYLIST")]}


class PlaylistTests(unittest.TestCase):
    def test_new_playlist_renames_and_partial_results_preserve_primary_first(self):
        original = catalog()
        incoming = [playlist("PLnew12345678", "New playlist"), playlist(title="Renamed playlist")]
        merged = merge_playlists(original, incoming)
        self.assertEqual([p["id"] for p in merged["playlists"]], [PRIMARY_PLAYLIST_ID, "PLnew12345678", "PLKU6UnEzQKJQ"])
        self.assertEqual(merged["playlists"][2]["title"], "Renamed playlist")
        self.assertEqual(original, catalog())
        self.assertEqual(merge_playlists(merged, incoming), merged)

    def test_parse_channel_output_deduplicates_without_losing_unicode(self):
        item = dict(playlist(title="希望 & Riffs"), url="https://www.youtube.com/playlist?list=PLKU6UnEzQKJQ")
        data = {"channel_id": CHANNEL_ID, "entries": [item, copy.deepcopy(item)]}
        self.assertEqual(parse_channel_playlists(data), [playlist(title="希望 & Riffs")])
        data["id"] = data.pop("channel_id")
        self.assertEqual(len(parse_channel_playlists(data)), 1)

    def test_rejects_empty_incomplete_wrong_channel_and_unexpected_urls(self):
        bad = [None, {"channel_id": "wrong", "entries": [playlist()]},
               {"id": CHANNEL_ID, "entries": []}, {"id": CHANNEL_ID, "entries": [None]},
               {"id": CHANNEL_ID, "entries": [playlist("invalid")]},
               {"id": CHANNEL_ID, "entries": [dict(playlist(), url="https://example.com/playlist?list=PLKU6UnEzQKJQ")]},
               {"id": CHANNEL_ID, "entries": [dict(playlist(), url="https://www.youtube.com/playlist?list=PLwrong123456")]}]
        for data in bad:
            with self.subTest(data=data), self.assertRaises(ValueError):
                parse_channel_playlists(data)

    def test_render_escapes_titles_and_changes_only_playlist_block(self):
        data = catalog()
        data["playlists"].append(playlist("PLtest1234567", '<script>alert("x")</script> & 日本語'))
        before = '<h2>Smash like, hit subscribe, and crack that bell icon</h2>'
        after = '<p>so you never miss a video</p>'
        rendered = render_playlists(data, before + START + 'old cards' + END + after)
        self.assertTrue(rendered.startswith(before + START))
        self.assertTrue(rendered.endswith(END + after))
        self.assertLess(rendered.index(PRIMARY_PLAYLIST_ID), rendered.index('PLKU6UnEzQKJQ'))
        self.assertNotIn('<script>', rendered)
        self.assertIn('&lt;script&gt;', rendered)
        self.assertEqual(rendered.count('class="playlist-card"'), 3)
        self.assertEqual(render_playlists(data, rendered), rendered)

    def test_missing_markers_leave_files_untouched(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder:
            directory = Path(folder)
            source = '<p>A page without the playlist markers</p>'
            (directory / 'index.html').write_text(source, encoding='utf-8')
            (directory / 'playlists.json').write_text('original', encoding='utf-8')
            with self.assertRaises(ValueError):
                save_playlists(catalog(), directory)
            self.assertEqual((directory / 'index.html').read_text(encoding='utf-8'), source)
            self.assertEqual((directory / 'playlists.json').read_text(encoding='utf-8'), 'original')

    def test_save_round_trip(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder:
            directory = Path(folder)
            (directory / 'index.html').write_text(START + END, encoding='utf-8')
            save_playlists(catalog(), directory)
            self.assertEqual(json.loads((directory / 'playlists.json').read_text(encoding='utf-8')), catalog())
            self.assertEqual((directory / 'index.html').read_text(encoding='utf-8').count('class="playlist-card"'), 2)


if __name__ == '__main__':
    unittest.main()
