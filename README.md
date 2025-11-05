# TVStreamCZ - Kodi Addon Repository

[![Build Status](https://github.com/daker52/TVstreamCZ/workflows/Build%20TVStreamCZ%20Repository/badge.svg)](https://github.com/daker52/TVstreamCZ/actions)

Oficiální Kodi addon repozitář pro TVStreamCZ plugin - streaming z Webshare.cz s pokročilými funkcemi.

## 🚀 Rychlá instalace do Kodi

### Metoda 1: Instalace repozitáře (doporučeno)
1. V Kodi jdi do **Settings** → **System** → **Add-ons**
2. Zapni **"Unknown sources"** 
3. Jdi do **Add-ons** → **"Install from zip file"**
4. Zadej URL: 
   ```
   https://github.com/daker52/TVstreamCZ/archive/refs/heads/main.zip
   ```
5. Po instalaci repozitáře najdeš plugin v **Add-ons** → **Install from repository** → **TVStreamCZ Repository**

### Metoda 2: Přímá instalace pluginu
Můžeš také stáhnout pouze plugin ze složky `plugin.video.tvstreamcz/` a nainstalovat jako ZIP.

## 📺 Funkce pluginu

### 🎬 Základní funkce
- **Streaming z Webshare.cz** - Filmy a seriály
- **Přihlášení účtu** - Bezpečné uložení credentials
- **Metadata z TMDb/ČSFD** - Obaly, popisy, hodnocení
- **Vyhledávání** - Rychlé nalezení obsahu
- **Filtry** - Kvalita, zvuk, titulky, žánry

### 📊 Historie přehrávání (NEW!)
- **Nedávno přehrané** - Automatické zaznamenávání
- **Nejčastěji přehrávané** - Statistiky sledování  
- **Oblíbené** - Označování a správa oblíbených
- **Pozastavené filmy** - Resume points pro nedokončené
- **Statistiky** - Detailní přehled sledování

### 🎭 Pokročilé funkce
- **Strukturované seriály** - Sezóny a epizody
- **Smart vyhledávání** - Metadata-first přístup
- **Dialog výběru streamů** - Kvalita, velikost, audio
- **Roční období** - Sezónní obsah
- **Automatické aktualizace** - Přes repozitář

## ⚙️ Požadavky

- **Kodi 19.x** (Matrix) nebo novější
- **Python 3.8+**
- **script.module.requests**
- **Webshare.cz účet** (pro přístup k obsahu)

## 🔄 Automatické aktualizace

Repozitář používá GitHub Actions pro automatické buildy:
- Při každé změně pluginu se automaticky aktualizuje `addons.xml`
- Kodi automaticky detekuje nové verze
- Uživatelé dostanou notifikaci o dostupných aktualizacích

## 📋 Changelog

### Version 0.1.1 (2024-11-05)
- ✅ Přidána kompletní historie přehrávání
- ✅ Opraveno prázdné zobrazení historie
- ✅ Zachován dialog pro výběr streamů
- ✅ Lepší zpracování metadat

### Version 0.1.0 (2024-11-01)
- 🎬 Základní funkcionalita
- 🔐 Webshare.cz integrace
- 🎭 TMDb/ČSFD metadata

## 🛠️ Pro vývojáře

### Struktura repozitáře
```
TVstreamCZ/
├── addon.xml                    # Repository metadata
├── addons.xml                   # Generated addon index  
├── addons.xml.md5              # Checksum
├── generate_addons.py          # Build script
├── plugin.video.tvstreamcz/    # Main plugin
└── .github/workflows/          # CI/CD
```

### Build proces
```bash
python generate_addons.py
```

## ⚠️ Disclaimer

Tento addon slouží pouze jako rozhraní pro přístup k legálně dostupnému obsahu na Webshare.cz. Autoři nenesou odpovědnost za obsah streamovaný prostřednictvím tohoto doplňku. Používejte pouze legální obsah.

## 📞 Podpora

- **Issues:** [GitHub Issues](https://github.com/daker52/TVstreamCZ/issues)
- **Dokumentace:** [Wiki](https://github.com/daker52/TVstreamCZ/wiki)

---

**Vytvořeno s ❤️ pro českou Kodi komunitu**
