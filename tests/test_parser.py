'''
"""Unit tests for the parser.py module."""
import sys
import os
import unittest

# Add the parent directory to the path to allow importing the parser module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from resources.lib import parser

class TestParser(unittest.TestCase):
    """Test suite for media file name parsing."""

    def test_detect_season_episode(self):
        """Test season and episode detection."""
        self.assertEqual(parser.detect_season_episode("The.Show.S01E02.720p.mkv"), (1, 2))
        self.assertEqual(parser.detect_season_episode("the.show.s01e02.720p.mkv"), (1, 2))
        self.assertEqual(parser.detect_season_episode("The.Show.S01.E02.720p.mkv"), (1, 2))
        self.assertEqual(parser.detect_season_episode("The.Show.1x02.720p.mkv"), (1, 2))
        self.assertEqual(parser.detect_season_episode("The.Show.10x05.720p.mkv"), (10, 5))
        self.assertEqual(parser.detect_season_episode("The.Show.No.Season.mkv"), (None, None))

    def test_detect_year(self):
        """Test year detection."""
        self.assertEqual(parser.detect_year("Movie.Title.2023.1080p.mkv"), 2023)
        self.assertEqual(parser.detect_year("Movie.Title.1999.1080p.mkv"), 1999)
        self.assertEqual(parser.detect_year("Movie.Title.No.Year.mkv"), None)
        self.assertEqual(parser.detect_year("Some.File.With.A.Number.1080.mkv"), None)

    def test_detect_quality(self):
        """Test video quality detection."""
        self.assertEqual(parser.detect_quality("Movie.2160p.mkv")[0], "uhd")
        self.assertEqual(parser.detect_quality("Movie.4K.mkv")[0], "uhd")
        self.assertEqual(parser.detect_quality("Movie.UHD.mkv")[0], "uhd")
        self.assertEqual(parser.detect_quality("Movie.1080p.mkv")[0], "hd")
        self.assertEqual(parser.detect_quality("Movie.720p.mkv")[0], "hd")
        self.assertEqual(parser.detect_quality("Movie.Bluray.mkv")[0], "hd")
        self.assertEqual(parser.detect_quality("Movie.DVDRip.mkv")[0], "sd")
        self.assertEqual(parser.detect_quality("Movie.CAM.mkv")[0], "sd")
        self.assertEqual(parser.detect_quality("Movie.No.Quality.mkv")[0], None)

    def test_clean_title(self):
        """Test title cleaning."""
        self.assertEqual(parser.clean_title("Movie.Title.2023.1080p.x264-GROUP"), "Movie Title")
        self.assertEqual(parser.clean_title("The.Show.S01E02.720p.mkv"), "The Show")
        self.assertEqual(parser.clean_title("A.Movie-With-Dots.and.Hyphens"), "A Movie With Dots and Hyphens")
        self.assertEqual(parser.clean_title("Film.CZ.SK.EN.MULTi.2020.BDRip.x264"), "Film")

    def test_classify_media_type(self):
        """Test media type classification."""
        self.assertEqual(parser.classify_media_type("The.Show.S01E01.mkv"), "tvshow")
        self.assertEqual(parser.classify_media_type("A.Good.Movie.2023.mkv"), "movie")
        self.assertEqual(parser.classify_media_type("A.Movie.Trailer.mkv"), "other")
        self.assertEqual(parser.classify_media_type("Some.Show.S02.mkv"), "tvshow")
        self.assertEqual(parser.classify_media_type("Some.Show.E03.mkv"), "tvshow")
        self.assertEqual(parser.classify_media_type("My.Series.Part01.mkv"), "other")
        self.assertEqual(parser.classify_media_type("My.Movie.CD1.mkv"), "other")

    def test_parse_media_entry(self):
        """Test full parsing of a Webshare API entry."""
        # Movie entry
        movie_data = {
            "ident": "mov123",
            "name": "Awesome.Movie.2021.1080p.BluRay.x264.CZ-ENG.DTS-GROUP.mkv",
            "size": "8589934592", # 8 GB
            "type": "mkv"
        }
        movie_item = parser.parse_media_entry(movie_data)
        self.assertEqual(movie_item.ident, "mov123")
        self.assertEqual(movie_item.original_name, movie_data["name"])
        self.assertEqual(movie_item.media_type, "movie")
        self.assertEqual(movie_item.cleaned_title, "Awesome Movie")
        self.assertEqual(movie_item.guessed_year, 2021)
        self.assertEqual(movie_item.quality, "hd")
        self.assertIn("cz", movie_item.audio_languages)
        self.assertIn("en", movie_item.audio_languages)

        # TV Show entry
        tv_data = {
            "ident": "tv456",
            "name": "My.Favorite.Show.S03E04.The.Episode.Title.720p.WEB-DL.SK.AAC.mkv",
            "size": "1073741824", # 1 GB
            "type": "mkv"
        }
        tv_item = parser.parse_media_entry(tv_data)
        self.assertEqual(tv_item.ident, "tv456")
        self.assertEqual(tv_item.media_type, "tvshow")
        self.assertEqual(tv_item.cleaned_title, "My Favorite Show The Episode Title")
        self.assertEqual(tv_item.season, 3)
        self.assertEqual(tv_item.episode, 4)
        self.assertEqual(tv_item.quality, "hd")
        self.assertIn("sk", tv_item.audio_languages)

if __name__ == '__main__':
    unittest.main()
''