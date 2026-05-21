# TVStreamCZ

Doplněk pro **Kodi** na filmy a seriály. Funguje **zdarma**, bez registrace a bez placeného účtu — stačí Kodi a internet.

## Co umí

- Filmy a seriály v přehledných kategoriích (populární, žánry, roky, novinky)
- Vyhledávání podle názvu
- U seriálů: výběr série → epizody → teprve pak stream
- Plakáty, popisy a roky z metadat (volitelný TMDB klíč jen pro lepší náhledy)
- Historie přehrávání a **Pokračovat ve sledování**
- Filtrování kvality, dabingu a titulků u streamů

## Instalace z repozitáře Kodi (doporučeno)

1. V Kodi zapněte **Neznámé zdroje** (*Nastavení → Doplňky*).
2. *Nastavení → Správce souborů → Přidat zdroj*  
   - Protokol: **HTTPS**  
   - URL: `https://raw.githubusercontent.com/daker52/TVstreamCZ/main/repo/`  
   - Název: `TVStreamCZ`
3. *Doplňky → Instalovat ze souboru → Procházet → TVStreamCZ* → nainstalujte **`repository.tvstreamcz-1.0.1.zip`**
4. *Doplňky → Instalovat z repozitáře → TVStreamCZ Repository* → vyberte **TVStreamCZ** a **YTS-Subs CZ**

Teprze po kroku 3 se objeví položka *Instalovat z repozitáře*.

## Ruční instalace (ZIP / složka)

1. Stáhněte nebo naklonujte repozitář.
2. Složku `plugin.video.tvstreamcz` zkopírujte do složky doplňků Kodi:
   - **Windows:** `%APPDATA%\Kodi\addons\`
   - **Linux:** `~/.kodi/addons/`
   - **Android TV / LibreELEC:** odpovídající `addons` adresář
3. V Kodi: *Nastavení → Doplňky → „Neznámé zdroje“* (pokud instalujete ručně).
4. Restart Kodi nebo *Aktualizovat seznam doplňků*.
5. Otevřete *Doplňky → Video doplňky → TVStreamCZ*.

### Závislosti

- Kodi 20 nebo novější (Python 3)
- Doplněk `script.module.requests` (většinou už v Kodi)

## První spuštění

Po instalaci stačí otevřít doplněk — **nepotřebujete přihlášení ani API klíče**.

Volitelně v nastavení můžete doplnit TMDB API klíč pro bohatší plakáty a přesnější názvy (není povinný).

## Doporučené titulky

K českým titulkům použijte doplněk **[YTS-Subs CZ](https://github.com/daker52/YTS-Subs-CZ)** — automatické vyhledání a zapnutí CZ titulků při startu filmu.

## Sestavení repozitáře (vývojáři)

```bash
python build_repo.py
git add repo/
git commit -m "chore: rebuild Kodi repository"
git push
```

## Licence

GPL-2.0-or-later
