
# -*- coding: utf-8 -*-
"""
A module for interacting with the Trakt.tv API.
"""

import json
import time
import webbrowser

import requests
import xbmc
import xbmcgui

# TODO: Replace with your own Trakt.tv API keys
CLIENT_ID = "YOUR_CLIENT_ID"
CLIENT_SECRET = "YOUR_CLIENT_SECRET"
API_URL = "https://api.trakt.tv"


class TraktAPI:
    """
    A class to handle interactions with the Trakt.tv API.
    """

    def __init__(self, addon, logger):
        self.addon = addon
        self.logger = logger
        self.token = self.addon.getSetting("trakt_token")
        self.refresh_token = self.addon.getSetting("trakt_refresh_token")

    def _get_headers(self):
        """
        Returns the headers required for API requests.
        """
        headers = {
            "Content-Type": "application/json",
            "trakt-api-version": "2",
            "trakt-api-key": CLIENT_ID,
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _handle_response(self, response):
        """
        Handles the response from the API.
        """
        if response.status_code == 200:
            return response.json()
        if response.status_code == 201:
            return response.json()
        if response.status_code == 204:
            return True
        if response.status_code == 401:
            self.logger("Trakt.tv token has expired, refreshing...", xbmc.LOGINFO)
            if self.refresh_access_token():
                self.logger("Trakt.tv token refreshed successfully.", xbmc.LOGINFO)
                return True
            self.logger("Failed to refresh Trakt.tv token.", xbmc.LOGERROR)
            return False
        self.logger(f"Trakt.tv API error: {response.status_code} - {response.text}", xbmc.LOGERROR)
        return None

    def authorize(self):
        """
        Initiates the authorization process with Trakt.tv.
        """
        # Step 1: Get device code
        data = {"client_id": CLIENT_ID}
        response = requests.post(f"{API_URL}/oauth/device/code", json=data)
        if response.status_code != 200:
            self.logger(f"Failed to get device code: {response.text}", xbmc.LOGERROR)
            return False

        device_code_data = response.json()
        user_code = device_code_data["user_code"]
        device_code = device_code_data["device_code"]
        interval = device_code_data["interval"]
        verification_url = device_code_data["verification_url"]

        # Step 2: Show instructions to the user
        dialog = xbmcgui.Dialog()
        dialog.ok(
            "Trakt.tv Authorization",
            f"Please go to [B]{verification_url}[/B] and enter the code: [B]{user_code}[/B]",
        )
        webbrowser.open(verification_url)

        # Step 3: Poll for the token
        start_time = time.time()
        while time.time() - start_time < device_code_data["expires_in"]:
            data = {
                "code": device_code,
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
            }
            response = requests.post(f"{API_URL}/oauth/device/token", json=data)

            if response.status_code == 200:
                token_data = response.json()
                self.token = token_data["access_token"]
                self.refresh_token = token_data["refresh_token"]
                self.addon.setSetting("trakt_token", self.token)
                self.addon.setSetting("trakt_refresh_token", self.refresh_token)
                self.logger("Trakt.tv authorized successfully.", xbmc.LOGINFO)
                xbmcgui.Dialog().notification("Trakt.tv", "Authorization successful", xbmcgui.NOTIFICATION_INFO)
                return True

            if response.status_code == 400:
                # Still pending, wait and try again
                time.sleep(interval)
            else:
                self.logger(f"Failed to get token: {response.text}", xbmc.LOGERROR)
                xbmcgui.Dialog().notification("Trakt.tv", "Authorization failed", xbmcgui.NOTIFICATION_ERROR)
                return False

        self.logger("Trakt.tv authorization timed out.", xbmc.LOGERROR)
        xbmcgui.Dialog().notification("Trakt.tv", "Authorization timed out", xbmcgui.NOTIFICATION_ERROR)
        return False

    def refresh_access_token(self):
        """
        Refreshes the access token.
        """
        if not self.refresh_token:
            return False

        data = {
            "refresh_token": self.refresh_token,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
            "grant_type": "refresh_token",
        }
        response = requests.post(f"{API_URL}/oauth/token", json=data)

        if response.status_code == 200:
            token_data = response.json()
            self.token = token_data["access_token"]
            self.refresh_token = token_data["refresh_token"]
            self.addon.setSetting("trakt_token", self.token)
            self.addon.setSetting("trakt_refresh_token", self.refresh_token)
            return True

        return False

    def scrobble(self, media_type, tmdb_id, progress, season=None, episode=None):
        """
        Scrobbles a video to Trakt.tv.
        """
        if not self.token:
            return

        data = {
            "progress": progress,
            "app_version": self.addon.getAddonInfo("version"),
            "app_date": self.addon.getAddonInfo("id"),
        }

        if media_type == "movie":
            data["movie"] = {"ids": {"tmdb": tmdb_id}}
        elif media_type == "episode":
            data["episode"] = {
                "season": season,
                "number": episode,
                "ids": {"tmdb": tmdb_id},
            }
        else:
            return

        if progress > 80:
            # Scrobble as watched
            response = requests.post(
                f"{API_URL}/scrobble/stop",
                headers=self._get_headers(),
                json=data,
            )
        else:
            # Scrobble as watching
            response = requests.post(
                f"{API_URL}/scrobble/start",
                headers=self._get_headers(),
                json=data,
            )

        self._handle_response(response)

    def add_to_history(self, media_type, tmdb_id, season=None, episode=None):
        """
        Adds an item to the user's Trakt.tv history.
        """
        if not self.token:
            return

        data = {}
        if media_type == "movie":
            data["movies"] = [{"ids": {"tmdb": tmdb_id}}]
        elif media_type == "episode":
            data["episodes"] = [{"ids": {"tmdb": tmdb_id}}]
        else:
            return

        response = requests.post(
            f"{API_URL}/sync/history",
            headers=self._get_headers(),
            json=data,
        )
        self._handle_response(response)
