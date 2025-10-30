# TVStreamCZ Kodi Plugin

![TVStreamCZ](https://img.shields.io/badge/Kodi-21.x-blue?logo=kodi)

**TVStreamCZ** je moderní český plugin pro Kodi, který umožňuje pohodlné sledování filmů a seriálů z Webshare.cz s bohatou integrací metadat (TMDb, ČSFD) a profesionálním výběrem streamů.

---

## Hlavní funkce

- **Vyhledávání filmů a seriálů** s automatickým rozpoznáním typu obsahu
- **Hierarchická navigace** v seriálech (sezóny, epizody)
- **Profesionální výběr streamu** (kvalita, velikost, audio, jazyk)
- **Filtrování podle žánru, kvality, zvuku, titulků**
- **Metadata z TMDb a ČSFD** (popisy, plakáty, hodnocení, žánry)
- **Kategorie: Populární, Nejlépe hodnocené, Právě v kinech, Novinky, Top 10, podle žánru**
- **Podpora češtiny a angličtiny**
- **Automatická detekce CZ/EN/SK audio**
- **Rychlé vyhledávání přes Webshare API**
- **Správná struktura ZIP pro instalaci v Kodi**

---

## Instalace

1. Stáhněte ZIP balíček z [releases](https://github.com/daker52/TVstreamCZ/releases)
2. V Kodi zvolte `Doplňky` > `Instalovat ze souboru ZIP`
3. Vyberte stažený ZIP soubor
4. Plugin najdete v sekci `Doplňky > Video`

---

## Nastavení

- Vložte své přihlašovací údaje k Webshare.cz
- (Volitelné) Zadejte TMDb API klíč pro lepší metadata
- Vyberte preferovaný jazyk metadat (cz/en)

---

## Metadata kategorie

### Filmy
- Populární
- Nejlépe hodnocené
- Právě v kinech
- Novinky
- Podle žánru

### Seriály
- Populární
- Nejlépe hodnocené
- Vysílané dnes
- Aktuálně vysílané
- Podle žánru

---

## Výběr streamu

Při výběru souboru se zobrazí dialog s přehledem kvality, velikosti a audio informací (podobně jako Stream Cinema).

- **Kvalita:** 4K/2160p, 1080p, 720p, CAM, atd.
- **Velikost:** v GB/MB
- **Audio:** kodek, kanály, jazyk (CZ/EN/SK)

---

## Vývoj

- [GitHub repozitář](https://github.com/daker52/TVstreamCZ)
- Pull requesty vítány!

---

## Licence

MIT

---

## Autoři

- [daker52](https://github.com/daker52)
- [další přispěvatelé vítáni]

---

## FAQ

**Q: Proč nevidím metadata?**
- Zkontrolujte, že máte správně nastavený TMDb API klíč a internetové připojení.

**Q: Proč nefunguje přehrávání?**
- Ověřte, že máte aktivní Webshare účet a správně zadané přihlašovací údaje.

**Q: Jak přidat další zdroje metadat?**
- Plugin podporuje hybridní režim TMDb/ČSFD, další lze přidat rozšířením `metadata.py`.

---

## Podpora

Pro nahlášení chyb nebo návrhy na vylepšení použijte [issues](https://github.com/daker52/TVstreamCZ/issues) na GitHubu.
