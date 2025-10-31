# TVStreamCZ Kodi Add-on

Streamovací doplněk pro Webshare.cz pro Kodi.

## Funkce

*   Procházení filmů a seriálů na Webshare.cz
*   Vyhledávání filmů a seriálů
*   Filtrování podle kvality, jazyka a titulků
*   Podpora pro přihlášení k účtu Webshare.cz
*   Obohacení metadat z TMDb a ČSFD
*   Integrace s Trakt.tv pro synchronizaci historie sledování

## Instalace

1.  Stáhněte si nejnovější verzi doplňku ze stránky [releases](https://github.com/your-username/plugin.video.tvstreamcz/releases).
2.  Otevřete Kodi a přejděte do "Doplňky".
3.  Klikněte na ikonu "Instalovat ze souboru zip".
4.  Vyberte stažený soubor a potvrďte instalaci.

## Nastavení

Po instalaci je třeba doplněk nakonfigurovat:

1.  Otevřete nastavení doplňku.
2.  V sekci "Účet Webshare" zadejte své přihlašovací údaje.
3.  (Volitelné) V sekci "Metadata" zadejte svůj TMDb API klíč pro obohacení metadat.

### Integrace s Trakt.tv

Pro synchronizaci historie sledování s Trakt.tv postupujte následovně:

1.  Vytvořte si aplikaci na [Trakt.tv](https://trakt.tv/oauth/applications/new).
2.  Zadejte "urn:ietf:wg:oauth:2.0:oob" jako "Redirect uri".
3.  Zkopírujte "Client ID" a "Client Secret".
4.  Otevřete soubor `resources/lib/trakt_api.py` a vložte své klíče do proměnných `CLIENT_ID` a `CLIENT_SECRET`.
5.  V nastavení doplňku v sekci "Integrace Trakt.tv" povolte integraci a klikněte na "Autorizovat Trakt.tv".
6.  Postupujte podle pokynů na obrazovce.