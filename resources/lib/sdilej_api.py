"""Wrapper around the Sdilej.cz website."""
from __future__ import annotations

import re
import requests
import xbmc
from typing import List, Dict, Optional
from dataclasses import dataclass

@dataclass
class SdilejItem:
    ident: str  # The URL (toplinktracker)
    title: str
    size: Optional[int]
    duration: Optional[str]
    thumbnail: Optional[str]
    
class SdilejAPI:
    BASE_URL = "https://sdilej.cz"
    
    def __init__(self, logger=None):
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        })
        self._logger = logger or (lambda msg, level=xbmc.LOGINFO: xbmc.log(msg, level))

    def search(self, query: str) -> List[SdilejItem]:
        url = f"{self.BASE_URL}/{query}/s"
        try:
            response = self._session.get(url, timeout=10)
            response.raise_for_status()
            return self._parse_search_results(response.text)
        except Exception as e:
            self._logger(f"Sdilej search error: {e}", xbmc.LOGERROR)
            return []

    def _parse_search_results(self, html: str) -> List[SdilejItem]:
        results = []
        
        # Regex to find items
        # We look for the videobox div and extract content within it
        # Since regex on full HTML is messy, we can split by "videobox" class or similar
        
        # Pattern to match the whole block roughly
        # <div class="... videobox" ...> ... <div class="videobox-desc"> ... </div> ... </div>
        
        # Let's try to find all blocks first
        blocks = re.findall(r'<div class="[^"]*videobox"[^>]*>(.*?)<div class="videobox-desc">', html, re.DOTALL)
        descs = re.findall(r'<div class="videobox-desc">(.*?)</div>', html, re.DOTALL)
        
        # This might be misaligned if regex fails.
        # Better approach: Find the specific unique parts.
        
        # The title link is inside videobox-desc -> p -> a
        # <p class="videobox-title"><a href="(url)" title="(title)">...</a></p>
        
        # The image is inside the first a tag
        # <img ... src="(src)" ...>
        
        # The size/duration is in the second p tag of videobox-desc
        # <p>(size) / <b>Délka:</b> (duration)</p>
        
        # Let's iterate over all matches of videobox-desc
        # and for each, find the preceding image.
        
        # Actually, let's just use a robust regex for the whole item if possible, or parse line by line.
        # Given the structure is repetitive:
        
        pattern = re.compile(
            r'<a href="([^"]+toplinktracker[^"]+)"[^>]*>\s*<img[^>]+src="([^"]+)"[^>]*>.*?<div class="videobox-desc">.*?<p class="videobox-title"><a[^>]+title="([^"]+)">.*?<p>(.*?)\s*/\s*<b>D[^<]+:</b>\s*([^<]+)</p>',
            re.DOTALL
        )
        
        matches = pattern.findall(html)
        for link, img, title, size_str, duration in matches:
            size = self._parse_size(size_str)
            
            # Fix relative image URLs
            if img.startswith("/"):
                img = self.BASE_URL + img
                
            results.append(SdilejItem(
                ident=link,
                title=title,
                size=size,
                duration=duration.strip(),
                thumbnail=img
            ))
            
        return results

    def _parse_size(self, size_str: str) -> int:
        size_str = size_str.upper().replace(" ", "").strip()
        try:
            if "GB" in size_str:
                return int(float(size_str.replace("GB", "")) * 1024 * 1024 * 1024)
            if "MB" in size_str:
                return int(float(size_str.replace("MB", "")) * 1024 * 1024)
            if "KB" in size_str:
                return int(float(size_str.replace("KB", "")) * 1024)
            if "B" in size_str:
                return int(float(size_str.replace("B", "")))
        except ValueError:
            pass
        return 0

    def resolve_url(self, tracker_url: str) -> Optional[str]:
        """
        Resolves the toplinktracker URL to the final file URL.
        This might involve following redirects and then scraping the detail page.
        """
        try:
            # 1. Follow redirect to get detail page URL
            head_resp = self._session.head(tracker_url, allow_redirects=True, timeout=10)
            detail_url = head_resp.url
            
            if "sdilej.cz" not in detail_url:
                self._logger(f"Unexpected redirect URL: {detail_url}", xbmc.LOGWARNING)
                return None
                
            # 2. Fetch detail page
            resp = self._session.get(detail_url, timeout=10)
            resp.raise_for_status()
            html = resp.text
            
            # 3. Find download link
            # We look for "Stáhnout pomalu" link: <a href="/free/index.php?id=..." ...>
            match = re.search(r'<a href="(/free/index\.php\?id=[^"]+)"[^>]*class="[^"]*btn-danger"[^>]*>', html)
            if match:
                free_link = match.group(1)
                full_free_link = self.BASE_URL + free_link
                
                # 4. Follow the free download link to get the actual FastShare URL
                # This page usually has countdown and then redirects or shows the final link
                self._logger(f"Following free download link: {full_free_link}", xbmc.LOGDEBUG)
                free_resp = self._session.get(full_free_link, timeout=10, allow_redirects=True)
                free_html = free_resp.text
                
                # Look for FastShare direct link in the page
                # Common patterns: <a href="https://fastshare.cz/..."> or direct redirect
                fastshare_match = re.search(r'href="(https?://(?:www\.)?fastshare\.cz/[^"]+)"', free_html)
                if fastshare_match:
                    final_url = fastshare_match.group(1)
                    self._logger(f"Found FastShare URL: {final_url}", xbmc.LOGINFO)
                    return final_url
                
                # If we got redirected directly to fastshare
                if "fastshare.cz" in free_resp.url:
                    self._logger(f"Redirected to FastShare: {free_resp.url}", xbmc.LOGINFO)
                    return free_resp.url
                
                # Fallback: return the free link URL (might work with redirects)
                return full_free_link
                
            # Check for "Stáhnout rychle" if user has premium (future proofing)
            # match_premium = re.search(r'<a href="([^"]+)"[^>]*class="[^"]*btn-success"[^>]*>', html)
            
        except Exception as e:
            self._logger(f"Error resolving sdilej URL: {e}", xbmc.LOGERROR)
            
        return None
