"""Тесты для утилиты разбора YouTube URL.

Проверяет:
    - Различение watch?v vs playlist?list
    - Вырезание &list= из watch-ссылок
    - Короткие youtu.be ссылки
    - Валидация URL
"""

import pytest

from src.infrastructure.url_utils import is_valid_youtube_url, parse_youtube_url


class TestIsValidYoutubeUrl:
    """Валидация YouTube URL."""

    def test_standard_watch(self) -> None:
        assert is_valid_youtube_url("https://www.youtube.com/watch?v=abc123")

    def test_short_url(self) -> None:
        assert is_valid_youtube_url("https://youtu.be/abc123")

    def test_playlist_url(self) -> None:
        assert is_valid_youtube_url(
            "https://www.youtube.com/playlist?list=PLabc123"
        )

    def test_mobile_url(self) -> None:
        assert is_valid_youtube_url("https://m.youtube.com/watch?v=abc123")

    def test_music_url(self) -> None:
        assert is_valid_youtube_url("https://music.youtube.com/watch?v=abc")

    def test_not_youtube(self) -> None:
        assert not is_valid_youtube_url("https://vimeo.com/12345")

    def test_no_scheme(self) -> None:
        assert not is_valid_youtube_url("youtube.com/watch?v=abc")

    def test_empty(self) -> None:
        assert not is_valid_youtube_url("")

    def test_plain_text(self) -> None:
        assert not is_valid_youtube_url("not a url at all")


class TestParseYoutubeUrl:
    """Разбор YouTube URL."""

    def test_explicit_playlist(self) -> None:
        url = "https://www.youtube.com/playlist?list=PLQMs5svASiXN3xSynw"
        clean, is_pl = parse_youtube_url(url)
        assert clean == url
        assert is_pl is True

    def test_watch_with_list_returns_single_video(self) -> None:
        url = "https://www.youtube.com/watch?v=8Odr2PClgZ8&list=PLQMs5svASiXN3xSynw"
        clean, is_pl = parse_youtube_url(url)
        assert is_pl is False
        assert "list=" not in clean
        assert "v=8Odr2PClgZ8" in clean

    def test_watch_without_list(self) -> None:
        url = "https://www.youtube.com/watch?v=8Odr2PClgZ8"
        clean, is_pl = parse_youtube_url(url)
        assert clean == url
        assert is_pl is False

    def test_short_url_with_list(self) -> None:
        url = "https://youtu.be/8Odr2PClgZ8?list=PLQMs5svASiXN3xSynw"
        clean, is_pl = parse_youtube_url(url)
        assert is_pl is False
        assert "list=" not in clean
        assert "8Odr2PClgZ8" in clean

    def test_short_url_without_list(self) -> None:
        url = "https://youtu.be/8Odr2PClgZ8"
        clean, is_pl = parse_youtube_url(url)
        assert clean == url
        assert is_pl is False

    def test_watch_with_list_and_index(self) -> None:
        url = "https://www.youtube.com/watch?v=abc&list=PLxyz&index=3"
        clean, is_pl = parse_youtube_url(url)
        assert is_pl is False
        assert "list=" not in clean
        assert "index=" not in clean
        assert "v=abc" in clean

    def test_watch_with_timestamp(self) -> None:
        url = "https://www.youtube.com/watch?v=abc&t=120"
        clean, is_pl = parse_youtube_url(url)
        assert clean == url
        assert is_pl is False

    def test_watch_with_list_preserves_timestamp(self) -> None:
        url = "https://www.youtube.com/watch?v=abc&list=PLxyz&t=120"
        clean, is_pl = parse_youtube_url(url)
        assert is_pl is False
        assert "t=120" in clean
        assert "v=abc" in clean
        assert "list=" not in clean

    def test_non_youtube_url_passthrough(self) -> None:
        url = "https://vimeo.com/12345"
        clean, is_pl = parse_youtube_url(url)
        assert clean == url
        assert is_pl is False
