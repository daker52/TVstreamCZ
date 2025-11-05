"""Stream selection dialog for choosing quality and other parameters."""

import xbmcgui


class StreamSelectorDialog:
    """Dialog for selecting stream from multiple options with quality info."""
    
    def __init__(self, streams):
        self.streams = streams
        self.dialog = xbmcgui.Dialog()
    
    def show_selection_dialog(self):
        """Show selection dialog and return chosen stream or None if cancelled."""
        if not self.streams:
            return None
            
        if len(self.streams) == 1:
            # Only one option, return it directly
            return self.streams[0]
        
        # Build display list with quality info
        display_items = []
        for stream in self.streams:
            display_text = self._build_display_text(stream)
            display_items.append(display_text)
        
        # Show selection dialog
        selected_index = self.dialog.select("Vyberte stream", display_items)
        
        if selected_index >= 0:
            return self.streams[selected_index]
        
        return None  # User cancelled
    
    def _build_display_text(self, stream):
        """Build display text for a stream with quality and size info."""
        # Get basic info
        filename = stream.get('name', 'Unknown')
        size = stream.get('size', 0)
        
        # Format size
        size_str = self._format_size(size)
        
        # Extract quality from filename
        quality = self._extract_quality(filename)
        
        # Extract audio info
        audio = self._extract_audio(filename)
        
        # Build display string
        parts = []
        
        if quality:
            parts.append(f"[COLOR yellow][{quality}][/COLOR]")
        
        if size_str:
            parts.append(f"[COLOR cyan][B]{size_str}[/B][/COLOR]")
            
        if audio:
            parts.append(f"[COLOR lime][I]{audio}[/I][/COLOR]")
        
        # Add filename (shortened)
        short_name = filename[:50] + "..." if len(filename) > 53 else filename
        parts.append(short_name)
        
        return "  ".join(parts)
    
    def _format_size(self, size_bytes):
        """Format file size in human readable format."""
        if not size_bytes or size_bytes == 0:
            return ""
        
        try:
            size_bytes = int(size_bytes)
            
            # Convert to appropriate unit
            if size_bytes >= 1073741824:  # >= 1GB
                return f"{size_bytes / 1073741824:.1f} GB"
            elif size_bytes >= 1048576:  # >= 1MB
                return f"{size_bytes / 1048576:.0f} MB"
            else:
                return f"{size_bytes / 1024:.0f} KB"
        except (ValueError, TypeError):
            return ""
    
    def _extract_quality(self, filename):
        """Extract quality information from filename."""
        import re
        
        filename_upper = filename.upper()
        
        # Check for common quality indicators
        quality_patterns = [
            (r'2160[Pp]|4K', '4K'),
            (r'1440[Pp]', '1440p'),
            (r'1080[Pp]|FHD', '1080p'),
            (r'720[Pp]|HD', '720p'),
            (r'576[Pp]', '576p'),
            (r'480[Pp]', '480p'),
            (r'360[Pp]', '360p'),
            (r'240[Pp]', '240p'),
        ]
        
        for pattern, quality in quality_patterns:
            if re.search(pattern, filename_upper):
                return quality
        
        # Check for other quality indicators
        if 'BLURAY' in filename_upper or 'BLU-RAY' in filename_upper:
            return 'BluRay'
        elif 'DVDRIP' in filename_upper:
            return 'DVDRip'
        elif 'WEBRIP' in filename_upper:
            return 'WebRip'
        elif 'WEBDL' in filename_upper or 'WEB-DL' in filename_upper:
            return 'Web-DL'
        elif 'CAM' in filename_upper:
            return 'CAM'
        elif 'TS' in filename_upper or 'TELESYNC' in filename_upper:
            return 'TS'
        
        return ""
    
    def _extract_audio(self, filename):
        """Extract audio information from filename."""
        import re
        
        filename_upper = filename.upper()
        audio_parts = []
        
        # Check for advanced audio formats first
        if 'ATMOS' in filename_upper:
            audio_parts.append('Atmos')
        elif 'DTS-HD' in filename_upper:
            audio_parts.append('DTS-HD')
        elif 'TRUEHD' in filename_upper:
            audio_parts.append('TrueHD')
        elif 'DTS' in filename_upper:
            audio_parts.append('DTS')
        elif re.search(r'DD\+', filename_upper):
            audio_parts.append('DD+')
        elif re.search(r'DD[\s\.]?5[\s\.]?1', filename_upper):
            audio_parts.append('DD 5.1')
        elif 'AC3' in filename_upper:
            audio_parts.append('AC3')
        elif 'AAC' in filename_upper:
            audio_parts.append('AAC')
        elif 'MP3' in filename_upper:
            audio_parts.append('MP3')
        elif 'FLAC' in filename_upper:
            audio_parts.append('FLAC')
        
        # Check for surround sound (if not already detected)
        if not any(x in audio_parts for x in ['Atmos', 'DD 5.1']):
            surround_patterns = [
                (r'7[\s\.]?1', '7.1'),
                (r'5[\s\.]?1', '5.1'),
                (r'2[\s\.]?1', '2.1'),
                (r'2[\s\.]?0', '2.0'),
            ]
            
            for pattern, channels in surround_patterns:
                if re.search(pattern, filename_upper):
                    audio_parts.append(channels)
                    break
        
        # Check for language - more precise patterns
        if re.search(r'[\s\._-]CZ[\s\._-]|\.CZ\.|_CZ_|-CZ-|^CZ[\s\._-]|[\s\._-]CZ$', filename_upper):
            audio_parts.append('CZ')
        elif re.search(r'[\s\._-]EN[\s\._-]|\.EN\.|_EN_|-EN-|^EN[\s\._-]|[\s\._-]EN$', filename_upper):
            audio_parts.append('EN')
        elif re.search(r'[\s\._-]SK[\s\._-]|\.SK\.|_SK_|-SK-|^SK[\s\._-]|[\s\._-]SK$', filename_upper):
            audio_parts.append('SK')
        
        return ' '.join(audio_parts) if audio_parts else ""