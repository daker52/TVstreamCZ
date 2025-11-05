# 🚀 KOMPLETNÍ NÁVOD: Kodi Addon Repository

## 📋 KROK ZA KROKEM

### 1. Příprava struktury repozitáře

```bash
# Vytvoř novou složku pro repozitář
mkdir repository.tvstreamcz
cd repository.tvstreamcz

# Inicializuj Git
git init
```

### 2. Vytvoř addon.xml pro repozitář

```xml
<?xml version="1.0" encoding="UTF-8"?>
<addon id="repository.tvstreamcz"
       name="TVStreamCZ Repository" 
       version="1.0.0"
       provider-name="TVStreamCZ">
    <requires>
        <import addon="xbmc.addon" version="12.0.0"/>
    </requires>
    <extension point="xbmc.addon.repository" name="TVStreamCZ Repository">
        <dir>
            <info compressed="false">https://raw.githubusercontent.com/TVOJE_JMENO/repository.tvstreamcz/main/addons.xml</info>
            <checksum>https://raw.githubusercontent.com/TVOJE_JMENO/repository.tvstreamcz/main/addons.xml.md5</checksum>
            <datadir zip="true">https://raw.githubusercontent.com/TVOJE_JMENO/repository.tvstreamcz/main/</datadir>
        </dir>
    </extension>
    <extension point="xbmc.addon.metadata">
        <summary lang="cs_CZ">TVStreamCZ Addon Repository</summary>
        <description lang="cs_CZ">Oficiální repozitář pro TVStreamCZ doplňky</description>
        <platform>all</platform>
        <assets>
            <icon>icon.png</icon>
            <fanart>fanart.jpg</fanart>
        </assets>
    </extension>
</addon>
```

### 3. Zkopíruj plugin do repozitáře

```bash
# Zkopíruj celou složku plugin.video.tvstreamcz
cp -r ../plugin.video.tvstreamcz ./
```

### 4. Vytvoř ikony a obrázky

- `icon.png` - ikona repozitáře (256x256px)
- `fanart.jpg` - pozadí (1920x1080px) 
- `plugin.video.tvstreamcz/icon.png` - ikona pluginu
- `plugin.video.tvstreamcz/fanart.jpg` - pozadí pluginu

### 5. Vygeneruj addons.xml

Spusť Python script:
```python
python generate_repository.py
```

### 6. Nahraj na GitHub

```bash
git add .
git commit -m "Initial TVStreamCZ repository"
git remote add origin https://github.com/TVOJE_JMENO/repository.tvstreamcz.git
git push -u origin main
```

## 🔗 INSTALACE DO KODI

### Metoda 1: Přímá instalace ze ZIP
1. Jdi na: `https://github.com/TVOJE_JMENO/repository.tvstreamcz/archive/refs/heads/main.zip`
2. V Kodi: Settings → System → Add-ons → zapni "Unknown sources"
3. Add-ons → Install from zip file → zadej URL výše

### Metoda 2: Repository ZIP soubor
1. Vytvoř ZIP pouze z repository addon:
```bash
zip -r repository.tvstreamcz-1.0.0.zip addon.xml icon.png fanart.jpg
```
2. Nahraj ZIP na GitHub Releases
3. V Kodi instaluj z tohoto ZIP souboru

## 🤖 AUTOMATIZACE S GITHUB ACTIONS

Vytvoř `.github/workflows/build.yml`:

```yaml
name: Build Repository
on:
  push:
    branches: [ main ]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    - name: Generate addons.xml
      run: python generate_repository.py
    - name: Commit changes
      run: |
        git config --local user.email "action@github.com"
        git config --local user.name "GitHub Action"
        git add addons.xml addons.xml.md5
        git diff --staged --quiet || git commit -m "Auto-update addons.xml"
    - name: Push changes
      uses: ad-m/github-push-action@master
      with:
        github_token: ${{ secrets.GITHUB_TOKEN }}
```

## 🔄 AKTUALIZACE PLUGINU

### Při nové verzi pluginu:
1. Uprav `plugin.video.tvstreamcz/addon.xml` - zvedni verzi
2. Push změny na GitHub
3. GitHub Actions automaticky aktualizuje addons.xml
4. Kodi automaticky detekuje novou verzi

### Versioning:
- `1.0.0` → `1.0.1` (bugfix)
- `1.0.1` → `1.1.0` (nová funkce)  
- `1.1.0` → `2.0.0` (breaking changes)

## 📁 FINÁLNÍ STRUKTURA

```
repository.tvstreamcz/
├── addon.xml                 # Repository metadata
├── icon.png                  # Repository icon
├── fanart.jpg               # Repository fanart
├── README.md                # Documentation
├── generate_repository.py   # Build script
├── addons.xml              # Generated addon index
├── addons.xml.md5          # Generated checksum
├── .github/workflows/      # GitHub Actions
│   └── build.yml
└── plugin.video.tvstreamcz/ # Your plugin
    ├── addon.xml
    ├── addon.py
    ├── icon.png
    ├── fanart.jpg
    └── resources/
```

## ✅ KONTROLNÍ SEZNAM

- [ ] Repository má správné URL v addon.xml
- [ ] Plugin má aktuální verzi v addon.xml
- [ ] Ikony jsou ve správných rozměrech
- [ ] addons.xml je vygenerován
- [ ] Repository je nahraný na GitHub
- [ ] GitHub Actions fungují
- [ ] Testováno v Kodi

🎯 **Repozitář je připraven k použití!**