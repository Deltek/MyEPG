# Changelog

Toutes les modifications notables sont documentées ici.
Format basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/).

---

## [Unreleased]

### Changed
- +33 tests unitaires sur les fonctions pures jusqu'ici non couvertes : `format_programme` (#72), `is_epg_placeholder`/`get_categories`/`now_paris` (#73), getters `epg_loader` + `reset_cache` (#74), branche index-cache de `epg_query` (#75), fenêtre nuit de `build_nuit_results` (#76) — 137 tests au total

---

## [1.10.0] - 2026-06-30

### Fixed
- Troncature des messages longs : coupure sur fin de ligne dans 5 handlers (`/live`, `/resume`, `/soir5`, `/doublons`, sport en cours) — plus de span MarkdownV2 cassé (#40)
- `/sport gb` : le pays était ignoré (parsing fragile du `callback_data`) (#44)
- `/recherche` : `search_mot` nettoyé entre deux recherches — plus de pollution de session (#45)

### Changed
- `/doublons` et `/trending` utilisent l'index EPG — O(n) → O(1) par chaîne (#41)
- `/recherche` met ses résultats en cache (`user_data`) — pagination instantanée dès la 2e page (#42)
- `get_channels(root)` lu depuis le cache EPG dans tous les handlers (#43)
- Helper `make_fns(query)` — élimine ~9 paires de lambdas dupliquées dans `callbacks.py` (#46)
- Recherche extraite dans `epg_search.py` (module neutre) — fin des imports circulaires lazy (#47)
- Logiques `/doublons`, `/trending`, `/recherche` extraites dans `analytics.py` (testable) + 19 tests sur les bornes de fenêtre (#49)
- `_iter_progs` promu en `builders.iter_progs` (réutilisable) (#49)

### Docs
- README à jour : commandes v1.9.0, suppression des commandes fantômes, `httpx` (#65)

---

## [1.9.0] - 2026-06-30

### Fixed
- `/maintenant <chaine>` : suggestions fuzzy si le nom est inconnu (#38)
- `/sporttnt` : l'en-tête affiche désormais le nombre de programmes (#39)
- `import difflib` / `CH_ALIASES` déplacés en haut de `handlers_public.py` (#48)
- `/film gb` et `/series gb` : paramètre pays pris en compte (#54)
- `SEARCH_PAGE_SIZE` porté de 5 à 8 (#61)

---

## [1.8.0] - 2026-06-29

### Fixed
- `/sport` : l'en-tête affiche désormais le nombre de programmes trouvés (#24)
- `/chaine` : suggestions fuzzy via `difflib` si le nom saisi est inconnu (#25)

---

## [1.7.0] - 2026-06-29

### Added
- 13 tests unitaires pour `builders.py` : fenêtres horaires, filtres fillers, nouveautés, sport, live en cours (#26)
- 11 tests unitaires pour `senders.py` : blocs vides, débordement multi-messages, tags inédits (#27)

---

## [1.6.0] - 2026-06-29

### Changed
- Index EPG par `channel_id` construit une fois au chargement — tous les builders passent de O(n×nb_chaînes) à O(nb_chaînes)
- `/resume` : 27 scans O(n) → 27 lookups O(1) dans l'index
- `/soir5` : 5 scans complets → itération directe par chaîne
- `get_channels()` n'est plus reconstruit à chaque commande — lu depuis le cache
- `import httpx` déplacé en lazy import dans `load_epg()` (ne casse plus les tests)

---

## [1.5.0] - 2026-06-29

### Fixed
- `BOT_VERSION` mis à jour `1.1` → `1.4.0` (affiché dans `/version` et `/admin`)
- Suppression de `import requests` inutilisé dans `handlers_admin.py`
- Suppression des doubles `logger.exception()` dans les blocs `except`
- Pagination `/recherche` : `callback_data` ne contient plus le mot-clé — plus de risque de dépasser la limite Telegram de 64 bytes
- Troncature des messages longs : coupure sur fin de ligne pour éviter de couper un span MarkdownV2
- `/trending` : les émissions déjà commencées sont désormais incluses dans le comptage

---

## [1.4.0] - 2026-06-29

### Added
- `/sporttnt` — Sport du jour sur les chaînes TNT FR (détection par catégorie EPG)

---

## [1.3.1] - 2026-06-29

### Fixed
- `epg_loader` : `httpx` ne suivait pas les redirects HTTP 302 du serveur EPG — toutes les commandes renvoyaient une erreur

---

## [1.3.0] - 2026-06-29

### Added
- 12 tests unitaires pour `builders.py` (fenêtres horaires, filtres fillers, nouveautés)

### Changed
- Migration `MarkdownV2` : tous les messages Telegram — formatage fiable même sur les titres avec caractères spéciaux
- `/aide` reorganisée par catégorie (Maintenant, Soirée, Genre, Recherche, Tendances)
- Erreurs internes loggées et masquées à l'utilisateur (message générique)

---

## [1.2.4] - 2026-06-29

### Changed
- `epg_loader` : passage de `requests` (synchrone) à `httpx` async — le bot ne bloque plus l'event loop pendant le rechargement EPG

---

## [1.2.3] - 2026-06-29

### Changed
- Suppression de l'emoji `🕐` répété sur chaque ligne de programme (lisibilité)
- Durée et temps restant déplacés en fin de ligne en italique
- Séparateur de chaîne uniformisé dans tous les messages

---

## [1.2.2] - 2026-06-29

### Fixed
- Commandes publiques désormais visibles en premier dans le menu admin (BotFather scope)

---

## [1.2.1] - 2026-06-29

### Fixed
- Suppression des 7 commandes fantômes déclarées dans BotFather sans handler (`couverture`, `manquantes`, `chainesorphelines`, `cherche_id`, `debug`, `blacklist`, `diff`)

---

## [1.2] - 2026-06-29

### Added
- 49 tests unitaires pytest couvrant `utils.py` et `epg_query.py`
- GitHub Actions CI : pipeline de tests automatique sur push/PR vers `main` et `develop`

---

## [1.1] - 2026-06-29

### Added
- `/prime [pays]` — Prime time 20h–22h30
- `/demain` — Programme de demain soir (raccourci direct)
- `/nuit` — Programme de la nuit 00h–06h
- `/resume` — Résumé compact des chaînes TNT en ce moment
- `/soir5` — Aperçu des 5 prochains soirs (vedettes TNT)
- `/doublons` — Programmes en doublon sur la TNT (6h glissantes)
- `/trending` — Titres diffusés plusieurs fois dans les 24h
- `/chaine <nom>` — Prochains programmes d'une chaîne
- `/chaines` — Parcourir toutes les chaînes (paginé, FR/GB)
- `/recherche <mot>` — Recherche full-text dans l'EPG (paginée, FR/GB/Tous)
- `build_maintenant_sport()`, `build_nouveautes_tnt()`, `build_prime_results()`, `build_nuit_results()` dans `builders.py`

### Fixed
- Crash sur `/recherche` et la pagination de recherche (`_do_recherche` manquante)

### Changed
- Builders EPG centralisés dans `builders.py` (suppression des boucles EPG inline dans `handlers_public` et `callbacks`)
- `callback_admin_logs` déplacée de `handlers_admin` → `callbacks`
- `format_programme` déplacée de `epg_query` → `senders`
- `CH_ALIASES` déplacé de `utils` → `config`
- `.replace("FR - ", "").strip()` remplacé par `clean_name()` dans `builders`

### Removed
- Notification Telegram dans `epg_loader` (découplage loader / bot)
- `set_app()` / `get_app()` supprimés de `epg_loader`

---

## [1.0] - 2026-06-29

### Added
- Architecture modulaire : `config`, `epg_loader`, `epg_query`, `builders`, `senders`, `keyboards`, `handlers_public`, `handlers_admin`, `callbacks`, `state`, `decorators`, `logger_utils`, `utils`
- Support EPG France 🇫🇷 (27 chaînes TNT + 60+ chaînes sport)
- Support EPG Royaume-Uni 🇬🇧 (17 chaînes FTA + 15+ chaînes sport)
- Cache EPG avec TTL 1h et snapshot diff
- Logging en mémoire circulaire
- 20+ commandes utilisateur : `/maintenant`, `/soir`, `/film`, `/series`, `/sport`, `/live`, `/nouveautes`
- 25+ commandes admin : monitoring, cache, statistiques, debugging
