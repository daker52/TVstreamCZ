# TVStreamCZ Kodi Add-on

TVStreamCZ is a Kodi video add-on that browses and streams films and TV shows hosted on [Webshare.cz](https://webshare.cz/). The plug-in provides structured navigation (recent titles, alphabetical listings, quality filters, genre drill-down) and augments Webshare entries with metadata fetched from TMDb and/or ČSFD.

## Features

- Webshare authentication (salted MD5-crypt + SHA1 digest) with session persistence.
- Movies and series navigation: recently added, alphabetical view, quality/audio/subtitle filters.
- Optional metadata enrichment:
  - **TMDb** (requires personal API key) for posters, overviews, ratings, genres.
  - **ČSFD** scraping fallback for localized metadata.
- Streaming links resolved via the official Webshare API (`file_link` endpoint) with optional HTTPS enforcement.
- Basic heuristics extract quality (HD/UHD/SD), audio languages (CZ/SK/EN), subtitle tags and season/episode numbers directly from Webshare filenames.

## Installation

1. Copy the add-on folder into your Kodi add-ons directory (e.g. `~/.kodi/addons/plugin.video.tvstreamcz`).
2. Restart Kodi or trigger an add-on scan so that Kodi registers the new plug-in.
3. Open *Add-ons → Video add-ons → TVStreamCZ*.

## Configuration

Open the add-on settings before first use:

- **Webshare account** – Provide your Webshare username/e-mail and password. The password is hashed client-side as required by the API.
- **Default filters** – Optional default quality/audio/subtitle filters and page size.
- **Metadata** – Choose metadata source order and configure your TMDb API key and preferred language/region. ČSFD scraping uses a configurable User-Agent header.
- **Streaming** – Select download mode (`video_stream` is recommended) and whether HTTPS links should be enforced.

After saving the settings the add-on will authenticate against Webshare and cache the session token for subsequent runs.

## Usage Tips

- The *Filters* menu allows quick access to quality and language filtered views.
- Genre browsing requires at least one enabled metadata provider that exposes a genre catalogue (TMDb recommended).
- If a video fails to play, verify that your Webshare account has sufficient privileges to stream the selected file.

## Development Notes

- The project targets Kodi 20+ (Python 3). Dependencies: `script.module.requests`.
- Source layout:
  - `resources/lib/webshare_api.py` – low-level API wrapper.
  - `resources/lib/parser.py` – heuristics for filename parsing.
  - `resources/lib/metadata.py` – metadata providers (TMDb, ČSFD) with caching.
  - `resources/lib/catalogue.py` – search/filter orchestration.
  - `resources/lib/plugin.py` – Kodi routing and UI glue.

## Disclaimer

This add-on relies on publicly documented Webshare endpoints and unofficial ČSFD HTML parsing. Respect the terms of service of all involved platforms and use the add-on responsibly.
