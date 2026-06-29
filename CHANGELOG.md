# Changelog

Toutes les modifications notables sont documentées ici.
Format basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/).

---

## [Unreleased]

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
