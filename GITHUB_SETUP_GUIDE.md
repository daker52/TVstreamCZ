# 🎯 FINÁLNÍ NÁVOD PRO TVŮJ GITHUB REPOZITÁŘ

## 📂 Aktuální situace
- GitHub repo: https://github.com/daker52/TVstreamCZ
- Lokální složka: D:\project\plugin.video.tvstreamcz

## 🚀 CO MUSÍŠ UDĚLAT (krok za krokem):

### 1. Přejmenuj soubory
```bash
# Přejmenuj repository addon
mv repository_addon.xml addon.xml
```

### 2. Vytvoř ikony (volitelné, ale doporučené)
- `icon.png` - ikona repozitáře (256x256px)
- `fanart.jpg` - pozadí repozitáře (1920x1080px)

### 3. Nahraj všechny soubory na GitHub
```bash
cd D:\project\plugin.video.tvstreamcz

# Inicializuj git (pokud není)
git init

# Nastav remote na tvůj repo
git remote add origin https://github.com/daker52/TVstreamCZ.git

# Nebo pokud už existuje:
git remote set-url origin https://github.com/daker52/TVstreamCZ.git

# Přidej všechny soubory
git add .

# Commitni
git commit -m "Setup complete Kodi addon repository with auto-updates"

# Pushni na GitHub
git push -u origin main
```

### 4. GitHub Actions se automaticky spustí
- Vygeneruje `addons.xml` a `addons.xml.md5`
- Při každé změně pluginu se automaticky aktualizuje

## 🔗 INSTALACE DO KODI

### URL pro přímou instalaci:
```
https://github.com/daker52/TVstreamCZ/archive/refs/heads/main.zip
```

### Postup v Kodi:
1. Settings → System → Add-ons → zapni "Unknown sources"
2. Add-ons → Install from zip file 
3. Zadej URL výše
4. Repository se nainstaluje jako "TVStreamCZ Repository"
5. Pak Install from repository → TVStreamCZ Repository → Video add-ons → TVStreamCZ

## 📦 STRUKTURA PO NAHRÁNÍ

```
https://github.com/daker52/TVstreamCZ/
├── addon.xml                    # Repository metadata
├── addons.xml                   # Auto-generovaný index
├── addons.xml.md5              # Auto-generovaný hash
├── README.md                    # Dokumentace
├── generate_addons.py          # Build script
├── plugin.video.tvstreamcz/    # Tvůj plugin
│   ├── addon.xml               # Plugin v0.1.1
│   ├── addon.py                # Hlavní kód
│   ├── changelog.txt           # Historie změn
│   └── resources/              # Resources
└── .github/workflows/          # Auto-buildy
    └── build.yml               # GitHub Actions
```

## 🔄 BUDOUCÍ AKTUALIZACE

### Když chceš aktualizovat plugin:
1. Uprav verzi v `plugin.video.tvstreamcz/addon.xml`
2. Aktualizuj `changelog.txt`
3. Git commit & push
4. GitHub Actions automaticky aktualizuje repozitář
5. Kodi uživatelům nabídne aktualizaci

### Versioning:
- `0.1.1` → `0.1.2` (opravy bugů)
- `0.1.2` → `0.2.0` (nové funkce)
- `0.2.0` → `1.0.0` (major release)

## ✅ KONTROLNÍ SEZNAM

- [ ] repository_addon.xml přejmenován na addon.xml
- [ ] Ikony přidány (volitelné)
- [ ] Všechno nahráno na GitHub
- [ ] GitHub Actions běží
- [ ] addons.xml se vygeneroval
- [ ] Testováno v Kodi

## 🎉 VÝSLEDEK

Po dokončení budou uživatelé moct:
- Instalovat repozitář z URL
- Automaticky dostávat aktualizace
- Instalovat plugin přímo z repozitáře
- Vidět changelog a popis

**🎬 Tvůj repozitář bude plně funkční Kodi addon repository!**