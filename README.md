# 📺 MyEPG — Bot Programme TV Telegram

Un bot Telegram intelligent pour consulter les programmes TV en temps réel. Accès aux EPG (Electronic Program Guides) France et Royaume-Uni avec filtrage avancé (films, séries, sport, inédits).

## ✨ Fonctionnalités

### 📡 Consultations EPG
- **`/maintenant`** — Programme en direct (par pays ou chaîne)
- **`/soir`** — Soirée TNT FR (19h-00h)
- **`/prime`** — Prime time 20h-22h30
- **`/demain`** — Programme de demain soir
- **`/nuit`** — Programmes nuit 00h-06h

### 🎬 Filtres Spécialisés
- **`/film`** — Films de la soirée (TNT FR)
- **`/series`** — Séries de la soirée (TNT FR)
- **`/sport [pays]`** — Sports du jour (FR/GB)
- **`/live [filtre]`** — Lives en cours (canal, bein, rmc...)
- **`/nouveautes`** — Programmes inédits

### 📊 Résumés & Analyses
- **`/resume`** — Résumé compact en ce moment
- **`/soir5`** — Les 5 prochains soirs (vedettes)
- **`/doublons`** — Programmes en doublon TNT (6h)
- **`/trending`** — Titres tendance du jour
- **`/chaine <nom>`** — Prochains programmes d'une chaîne
- **`/chaines`** — Parcourir toutes les chaînes
- **`/recherche <mot>`** — Recherche full-text

### 🔧 Admin (réservé)
- **`/admin`** — Panneau de contrôle
- **`/status`** — Vue synthétique
- **`/cache`** — État du cache EPG
- **`/refresh [pays]`** — Forcer rechargement
- **`/logs`** — Dernières erreurs
- **`/stats`** — Statistiques EPG
- Et 15+ autres commandes...

---

## 🏗️ Architecture Modulaire

### Structures des Fichiers

```
myepg/
├── config.py              # Configuration (tokens, chaînes, blacklists)
├── logger_utils.py        # Logging en mémoire
├── utils.py               # Utilitaires (parsing, nettoyage, détection)
├── epg_loader.py          # Chargement & cache EPG
├── epg_query.py           # Requêtes EPG (extraction, formatage)
├── builders.py            # Construction résultats filtrés
├── senders.py             # Formatage & envoi messages
├── keyboards.py           # Claviers Telegram inline
├── decorators.py          # Décorateurs (admin_only, etc.)
├── state.py               # État global (utilisateurs, temps démarrage)
├── handlers_public.py     # Handlers commandes publiques
├── handlers_admin.py      # Handlers commandes admin (à créer)
├── callbacks.py           # Gestionnaires de callbacks (à créer)
├── main.py                # Point d'entrée du bot (à créer)
└── requirements.txt       # Dépendances
```

### Dépendances Entre Modules

```
config.py
  ├── utils.py
  ├── epg_loader.py
  │   └── logger_utils.py
  ├── keyboards.py
  ├── builders.py
  │   └── epg_query.py
  ├── senders.py
  ├── handlers_public.py
  └── state.py
```

---

## 🚀 Installation

### 1. Cloner le repository

```bash
git clone https://github.com/Deltek/MyEPG.git
cd MyEPG
```

### 2. Créer un environnement Python

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows
```

### 3. Installer les dépendances

```bash
pip install -r requirements.txt
```

### 4. Configurer les variables d'environnement

```bash
export BOT_TOKEN="votre_token_telegram"
export ADMIN_USER_ID="votre_user_id"
```

Ou créer un fichier `.env` :

```env
BOT_TOKEN=votre_token_telegram
ADMIN_USER_ID=votre_user_id
```

### 5. Lancer le bot

```bash
python3 main.py
```

---

## 📋 Configuration

### Variables d'Environnement

| Variable | Type | Description |
|----------|------|-------------|
| `BOT_TOKEN` | string | Token Telegram (obtenu via @BotFather) |
| `ADMIN_USER_ID` | int | User ID de l'administrateur (pour `/admin` et autres commandes) |

### Configuration Python (`config.py`)

```python
CACHE_TTL        = 3600  # Cache EPG expire après 1h
PAGE_SIZE        = 20    # Résultats par page (listes chaînes)
SEARCH_PAGE_SIZE = 5     # Résultats par page (recherche)
```

---

## 🌍 Sources EPG Supportées

### France 🇫🇷
- **URL** : `https://iptv-epg.org/files/epg-fr.xml.gz`
- **Chaînes TNT** : 27 chaînes (TF1, France 2, M6, Arte, etc.)
- **Chaînes Sport** : 60+ chaînes (Eurosport, beIN, RMC Sport, L'Équipe, etc.)

### Royaume-Uni 🇬🇧
- **URL** : `https://iptv-epg.org/files/epg-gb.xml.gz`
- **Chaînes FTA** : 17 chaînes (BBC, ITV, Channel 4/5, etc.)
- **Chaînes Sport** : 15+ chaînes (Sky Sports, TNT Sports, Eurosport, etc.)

---

## 🧠 Logique de Détection

### Films
- Catégorie "film" ou durée ≥ 75 minutes
- Exclut les séries (pas d'episode-num)

### Séries
- Catégorie "série", "sitcom", "soap"
- Ou contient pattern S##E## ou "saison #"

### Sports
- Chaînes sport + Filtrage fillers
- Détecte placeholders EPG
- Exclut les annonces génériques

### Inédits
- Filtre "new" EPG
- Exclut news, météo, jeux TV récurrents
- Sport : exclut fillers sport

---

## 🔄 Flux de Données

```
EPG Source (gzip XML)
        ↓
    load_epg() [cache 1h]
        ↓
    ET.parse() (ElementTree)
        ↓
    builders.build_*() [filtrage]
        ↓
    senders.send_*() [formatage]
        ↓
    Telegram API
        ↓
    Utilisateur 📱
```

---

## 📦 Dépendances

- **`python-telegram-bot`** (≥20.0) — Bot Telegram async
- **`requests`** — Téléchargement EPG
- **`psutil`** (optionnel) — Monitoring mémoire
- **`python-dotenv`** (optionnel) — Variables `.env`

### Installation complète

```bash
pip install python-telegram-bot>=20.0 requests psutil python-dotenv
```

---

## 🐛 Troubleshooting

### "BOT_TOKEN non défini"
```bash
export BOT_TOKEN="YOUR_TOKEN"
echo $BOT_TOKEN  # Vérifier
```

### Cache EPG expiré
Le bot recharge automatiquement après 1 heure. Force : `/refresh`

### Performance lente
- Vérifier mémoire : `/memoire` (admin)
- Forcer GC : `/gc` (admin)

### Chaînes manquantes
- Vérifier EPG source : `/testepg` (admin)
- Lister orphelines : `/chainesorphelines` (admin)

---

## 📊 Commandes Admin

### Monitoring
- `/status` — Vue synthétique (uptime, cache, erreurs)
- `/ping` — Latence
- `/memoire` — Utilisation mémoire
- `/logs` — Dernières erreurs

### EPG
- `/cache` — État du cache
- `/stats` — Statistiques
- `/testepg [pays]` — Tester source EPG
- `/refresh [pays]` — Recharger cache
- `/diff [pays]` — Diff avec snapshot précédent

### Chaînes
- `/top [pays]` — Top 10 chaînes
- `/cherche_id <nom>` — Trouver channel ID
- `/debug <id>` — Programmes bruts d'une chaîne
- `/couverture [pays]` — Couverture 24h
- `/manquantes [pays]` — Chaînes absentes de listes

### Utilitaires
- `/blacklist` — Afficher les blacklists
- `/gc` — Garbage collection
- `/nbusers` — Utilisateurs distincts

---

## 🎨 Format Messages

### Programme En Direct
```
🔴 ▶️ Titre du Programme 🆕
🕐 20:00–22:30  ⏱ 2h30
📝 Description courte...
⏭ À 22:30 : Prochain titre
```

### Sport
```
🔴 20:00–22:30 ⏱ 2h30  Titre Match ⚠️
   📝 Description courte...
```

### Résultat Recherche
```
📺 **Chaîne**  🕐 01/01 20:00–22:30
▶️ Titre du Programme
   📝 Description...
```

---

## 🤝 Contribution

Les contributions sont bienvenues ! Pour contribuer :

1. Fork le repo
2. Créer une branche `feature/ma-feature`
3. Commit les changements
4. Push et créer une Pull Request

---

## 📄 License

MIT License — Libre d'utilisation

---

## 📧 Contact

- **Repository** : https://github.com/Deltek/MyEPG
- **Issues** : https://github.com/Deltek/MyEPG/issues

---

## 📝 Changelog

Voir [CHANGELOG.md](CHANGELOG.md) pour l'historique complet des versions.
