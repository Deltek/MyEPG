# ============================================================
# CONFIG — Configuration globale du bot
# ============================================================

import os
import locale
from zoneinfo import ZoneInfo

BOT_TOKEN     = os.getenv("BOT_TOKEN")
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))
BOT_VERSION   = "1.0"

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN non défini dans l'environnement !")

CACHE_TTL        = 3600
PAGE_SIZE        = 20
SEARCH_PAGE_SIZE = 5
TZ_PARIS         = ZoneInfo("Europe/Paris")

try:
    locale.setlocale(locale.LC_TIME, "fr_FR.UTF-8")
except locale.Error:
    pass

EPG_SOURCES = {
    "fr": {
        "url":   "https://iptv-epg.org/files/epg-fr.xml.gz",
        "label": "🇫🇷 France",
        "vedettes": [
            "TF1.fr", "France2.fr", "France3.fr", "M6.fr",
            "Arte.fr", "C8.fr", "W9.fr", "TMC.fr",
            "NRJ12.fr", "BFMTV.fr", "CNews.fr",
        ],
    },
    "gb": {
        "url":   "https://iptv-epg.org/files/epg-gb.xml.gz",
        "label": "🇬🇧 United Kingdom",
        "vedettes": [
            "BBC1.uk", "BBC2.uk", "ITV.uk", "Channel4.uk",
            "Channel5.uk", "BBCNews.uk", "Sky1.uk", "SkyNews.uk",
            "Dave.uk", "E4.uk", "Film4.uk",
        ],
    },
}

CH_TNT_FR = [
    "TF1.fr", "France2.fr", "France3.fr", "France5.fr", "M6.fr",
    "Arte.fr", "C8.fr", "W9.fr", "TMC.fr", "TFX.fr", "NRJ12.fr",
    "LCP.fr", "France4.fr", "BFMTV.fr", "CNews.fr", "CStar.fr",
    "Gulli.fr", "TF1Series-Films.fr", "L'Equipe.fr", "6ter.fr",
    "RMCSTORY.fr", "RMCDecouverte.fr", "Cherie25.fr", "LCI.fr",
    "franceinfo.fr", "ParisPremiere.fr", "RTL9.fr",
]

CH_FTA_GB = [
    "BBC1.uk", "BBC2.uk", "ITV.uk", "Channel4.uk", "Channel5.uk",
    "BBC3.uk", "BBC4.uk", "ITV2.uk", "ITV3.uk", "ITV4.uk",
    "E4.uk", "Film4.uk", "More4.uk", "Dave.uk", "5Star.uk",
    "5USA.uk", "Quest.uk",
]

CH_SPORT_FR = [
    "L'Equipe.fr",
    "CANAL+SPORT360.fr", "C+SPORT.fr", "CANAL+FORMULA1.fr", "CANAL+TOP14.fr", "CANAL+MOTOGP.fr",
    "CANAL+LIVE1.fr", "CANAL+LIVE2.fr", "CANAL+LIVE3.fr", "CANAL+LIVE4.fr", "CANAL+LIVE5.fr",
    "CANAL+LIVE6.fr", "CANAL+LIVE7.fr", "CANAL+LIVE8.fr", "CANAL+LIVE9.fr", "CANAL+LIVE10.fr",
    "CANAL+LIVE11.fr", "CANAL+LIVE12.fr", "CANAL+LIVE13.fr", "CANAL+LIVE14.fr",
    "CANAL+LIVE15.fr", "CANAL+LIVE16.fr", "CANAL+LIVE17.fr", "CANAL+LIVE18.fr", "CANAL+LIVE19.fr",
    "EUROSPORT1.fr", "EUROSPORT2.fr",
    "Eurosport360_1.fr", "Eurosport360_2.fr", "Eurosport360_3.fr",
    "Eurosport360_4.fr", "Eurosport360_5.fr", "Eurosport360_6.fr",
    "Eurosport360_7.fr", "Eurosport360_8.fr",
    "beINSPORTS1.fr", "beINSPORTS2.fr", "beINSPORTS3.fr",
    "beINSPORTSMAX4.fr", "beINSPORTSMAX5.fr", "beINSPORTSMAX6.fr",
    "beINSPORTSMAX7.fr", "beINSPORTSMAX8.fr", "beINSPORTSMAX9.fr",
    "beINSPORTSMAX10.fr",
    "RMCSport1.fr", "RMCSport2.fr",
    "RMCSportLive3.fr", "RMCSportLive4.fr", "RMCSportLive5.fr",
    "RMCSportLive6.fr", "RMCSportLive7.fr", "RMCSportLive8.fr",
    "RMCSportLive9.fr", "RMCSportLive10.fr", "RMCSportLive11.fr",
    "RMCSportLive12.fr",
    "KombatSport.fr", "Equidia.fr", "OLTV.fr", "GolfeTV.fr",
]

CH_SPORT_GB = [
    "SkySportsMainEvent.uk", "SkySportsPremierLeague.uk",
    "SkySportsFootball.uk", "SkySportsArena.uk", "SkySportsCricket.uk",
    "SkySportsGolf.uk", "SkySportsF1.uk", "SkySportsTennis.uk",
    "SkySportsBoxing.uk",
    "TNTSports1.uk", "TNTSports2.uk", "TNTSports3.uk", "TNTSports4.uk",
    "Eurosport1.uk", "Eurosport2.uk",
]

CH_TNT_BY_COUNTRY   = {"fr": CH_TNT_FR,   "gb": CH_FTA_GB}
CH_SPORT_BY_COUNTRY = {"fr": CH_SPORT_FR, "gb": CH_SPORT_GB}

_SPORT_TITLES_BLACKLIST = (
    "a bientot sur eurosport", "chaine evenementielle", "chalet club",
    "bein sports, le plus grand", "ca se passe sur bein", "this is paris",
    "grandir par le sport", "bein zap", "salon vip", "nba extra",
    "europe arena", "avant-match", "bein squad", "terrains d'espoirs",
    "passion sous pression", "made in england", "bein story",
    "format boxe", "format one", "format mma", "format ufc",
    "baba versus", "fighter club", "ticket gagnant", "3 mn pronos",
    "le grand debrief", "lgd 100%", "resumes des derniers matchs",
    "autour du match", "la chaine officielle de l'olympique",
    "ligue 1 mcdonald's : live audio", "pause",
)

_NOUVEAUTES_BLACKLIST = (
    "jt ", "journal ", "meteo", "météo", "tirage du loto", "bonjour !",
    "le 12.45", "le 19.45", "telemat", "le 6h info", "les maternelles",
    "le mag de la sante", "c dans l'air", "c a vous", "le double expresso",
    "quotidien", "sens public", "l'equipe de choc", "l'equipe de greg",
    "l'equipe du soir", "la revue de presse", "stade 2 la quotidienne",
    "stade 2 ligue", "bonjour chez vous", "apolline matin",
    "les grandes gueules", "estelle midi", "good morning business",
    "le morning", "c dans l air invite", "petits plats en equilibre",
    "consomag", "basique, l'essentiel", "le dessous des cartes",
)

_GENERIC_SPORT_WORDS = frozenset({
    "football", "tennis", "basketball", "rugby", "natation",
    "handball", "volleyball", "cyclisme", "athletisme",
    "hockey", "boxe", "mma", "golf",
})

_EPG_PLACEHOLDER_DESCS = (
    "suivez un match d'une competition de football",
    "suivez un match d'une competition",
)
