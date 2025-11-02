<<<<<<< HEAD
# TVStreamCZ Kodi Add-on 🎬🇨🇿

TVStreamCZ je doplněk pro Kodi, který umožňuje pohodlně procházet a streamovat filmy a seriály z [Webshare.cz](https://webshare.cz/) s metadaty z TMDb a ČSFD.

## ✨ Funkce

- 🔑 Přihlášení k Webshare (bezpečné hashování hesla, automatické uložení relace)
- 📺 Procházení filmů a seriálů: novinky, abecední seznam, filtry podle kvality, dabingu a titulků
- 🏷️ Metadata z TMDb (plakáty, popisy, žánry, hodnocení) a ČSFD (lokalizované info)
- 🔗 Streamování přes oficiální Webshare API (s volitelným vynucením HTTPS)
- 🏷️ Automatická detekce kvality (HD/UHD/SD), jazyků audia (CZ/SK/EN), titulků a dabingu přímo z názvu souboru (např. „CZ dabing“ nebo „EN dub“)
- 🎚️ Rychlé filtry pro kvalitu, jazyk a titulky

## 🛠️ Instalace

1. Zkopírujte složku doplňku do adresáře Kodi add-ons (např. `~/.kodi/addons/plugin.video.tvstreamcz`)
2. Restartujte Kodi nebo spusťte aktualizaci doplňků
3. Otevřete *Doplňky → Video doplňky → TVStreamCZ*

## ⚙️ Nastavení

- **Webshare účet** – Zadejte své přihlašovací údaje (heslo je bezpečně hashováno)
- **Výchozí filtry** – Nastavte si preferovanou kvalitu, jazyk a titulky
- **Metadata** – Zvolte zdroj (TMDb/ČSFD), nastavte TMDb API klíč a preferovaný jazyk/region
- **Streamování** – Zvolte režim stahování a případně vynucení HTTPS

Po uložení nastavení dojde k ověření účtu a uložení tokenu pro další použití.

## 💡 Tipy k použití

- V menu *Filtry* rychle najdete obsah podle kvality nebo jazyka
- Procházení podle žánru vyžaduje aktivní metadata (doporučeno TMDb)
- Pokud přehrávání selže, zkontrolujte, zda má váš Webshare účet potřebná oprávnění

## 🧑‍💻 Vývoj

- Cílí na Kodi 20+ (Python 3)
- Závislosti: `script.module.requests`
- Struktura zdrojového kódu:
  - `resources/lib/webshare_api.py` – API wrapper pro Webshare
  - `resources/lib/parser.py` – heuristiky pro rozpoznání kvality, dabingu atd.
  - `resources/lib/metadata.py` – metadata z TMDb/ČSFD
  - `resources/lib/catalogue.py` – logika vyhledávání a filtrování
  - `resources/lib/plugin.py` – hlavní logika a napojení na Kodi

## ⚠️ Upozornění

Doplněk využívá veřejné API Webshare a neoficiální HTML scraping ČSFD. Respektujte podmínky služeb a používejte doplněk zodpovědně.
=======
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
>>>>>>> 47c2fe2 (TVStreamCZ: metadata kategorie, stream selector, TMDb/ČSFD integrace, moderní README)
