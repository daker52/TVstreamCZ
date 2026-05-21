"""Stream selection dialog for choosing quality and other parameters."""

import re

import xbmcgui


class StreamSelectorDialog:
    """Dialog for selecting stream from multiple options with quality info."""

    def __init__(
        self,
        streams,
        title: str = "Vyberte stream",
        default_quality: str = "any",
        default_audio: str = "any",
    ):
        self.streams = streams
        self.title = title
        self.default_quality = (default_quality or "any").lower()
        self.default_audio = (default_audio or "any").lower()
        self.dialog = xbmcgui.Dialog()

    def show_selection_dialog(self):
        """Show selection dialog and return chosen stream or None if cancelled."""
        if not self.streams:
            return None

        display_items = []
        default_index = 0
        best_score = -1
        for idx, stream in enumerate(self.streams):
            display_text = self._build_display_text(stream)
            score = self._preference_score(stream)
            if score > best_score:
                best_score = score
                default_index = idx
            if score >= 100:
                display_text = f"[COLOR gold]★[/COLOR] {display_text}"
            display_items.append(display_text)

        try:
            selected_index = self.dialog.select(
                self.title, display_items, preselect=default_index
            )
        except TypeError:
            selected_index = self.dialog.select(self.title, display_items)
        if selected_index >= 0:
            return self.streams[selected_index]
        return None

    def _preference_score(self, stream) -> int:
        """Score stream against user default quality/audio settings."""
        score = 0
        filename = (stream.get("name") or "").upper()
        quality = self._extract_quality(filename)
        q_pref = self.default_quality
        if q_pref == "uhd" and quality in ("4K", "2160p"):
            score += 100
        elif q_pref == "hd" and quality in ("1080p", "720p", "HD"):
            score += 100
        elif q_pref == "sd" and quality in ("480p", "576p", "360p", "SD"):
            score += 100
        elif q_pref == "any" and quality:
            score += 40
        audio = self._extract_audio(filename)
        langs = stream.get("audio_languages") or []
        if self.default_audio == "cz" and ("CZ" in audio or "cz" in langs):
            score += 50
        elif self.default_audio == "sk" and ("SK" in audio or "sk" in langs):
            score += 50
        elif self.default_audio == "en" and ("EN" in audio or "en" in langs):
            score += 50
        size = stream.get("size") or 0
        if size > 500_000_000:
            score += 10
        return score

    def _build_display_text(self, stream):
        """Build display text for a stream with quality and size info."""
        filename = stream.get("name", "Unknown")
        size = stream.get("size", 0)
        ident = stream.get("ident", "")

        is_sdilej = str(ident).startswith("http")
        provider_tag = "[COLOR orange][Sdilej][/COLOR]" if is_sdilej else "[COLOR deepskyblue][Webshare][/COLOR]"
        size_str = self._format_size(size)
        quality = stream.get("quality") or self._extract_quality(filename)
        if quality and isinstance(quality, str):
            quality = quality.upper()
        else:
            quality = self._extract_quality(filename)
        audio = self._extract_audio(filename)
        subs = self._format_subtitles(stream.get("subtitle_languages") or [], filename)

        parts = [provider_tag]
        if quality:
            parts.append(f"[COLOR yellow][{quality}][/COLOR]")
        if size_str:
            parts.append(f"[COLOR cyan][B]{size_str}[/B][/COLOR]")
        if audio:
            parts.append(f"[COLOR lime][I]{audio}[/I][/COLOR]")
        if subs:
            parts.append(f"[COLOR lightblue]{subs}[/COLOR]")
        short_name = filename[:55] + "..." if len(filename) > 58 else filename
        parts.append(short_name)
        return "  ".join(parts)

    def _format_subtitles(self, langs, filename: str) -> str:
        tags = []
        if langs:
            tags.extend(code.upper() for code in langs if code)
        upper = filename.upper()
        if re.search(r"CZ\s*TIT|CZECH\s*SUB|TITULKY\s*CZ", upper):
            if "CZ" not in tags:
                tags.append("CZ tit")
        return " ".join(tags[:3])

    def _format_size(self, size_bytes):
        if not size_bytes or size_bytes == 0:
            return ""
        try:
            size_bytes = int(size_bytes)
            if size_bytes >= 1073741824:
                return f"{size_bytes / 1073741824:.1f} GB"
            if size_bytes >= 1048576:
                return f"{size_bytes / 1048576:.0f} MB"
            return f"{size_bytes / 1024:.0f} KB"
        except (ValueError, TypeError):
            return ""

    def _extract_quality(self, filename):
        filename_upper = filename.upper()
        quality_patterns = [
            (r"2160[Pp]|4K", "4K"),
            (r"1440[Pp]", "1440p"),
            (r"1080[Pp]|FHD", "1080p"),
            (r"720[Pp]|HD", "720p"),
            (r"576[Pp]", "576p"),
            (r"480[Pp]", "480p"),
        ]
        for pattern, quality in quality_patterns:
            if re.search(pattern, filename_upper):
                return quality
        if "BLURAY" in filename_upper:
            return "BluRay"
        if "WEBDL" in filename_upper or "WEB-DL" in filename_upper:
            return "Web-DL"
        return ""

    def _extract_audio(self, filename):
        filename_upper = filename.upper()
        audio_parts = []
        if "ATMOS" in filename_upper:
            audio_parts.append("Atmos")
        elif "DTS-HD" in filename_upper:
            audio_parts.append("DTS-HD")
        elif "AC3" in filename_upper:
            audio_parts.append("AC3")
        elif "AAC" in filename_upper:
            audio_parts.append("AAC")
        if re.search(r"[\s\._-]CZ[\s\._-]|\.CZ\.|_CZ_", filename_upper):
            audio_parts.append("CZ")
        elif re.search(r"[\s\._-]EN[\s\._-]|\.EN\.|_EN_", filename_upper):
            audio_parts.append("EN")
        elif re.search(r"[\s\._-]SK[\s\._-]|\.SK\.|_SK_", filename_upper):
            audio_parts.append("SK")
        return " ".join(audio_parts) if audio_parts else ""
