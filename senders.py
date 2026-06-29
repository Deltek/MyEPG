# ============================================================
# SENDERS — Formatage & envoi des messages Telegram
# ============================================================

from datetime import datetime, timezone
from collections import defaultdict

from config import TZ_PARIS, CH_TNT_FR
from utils import sanitize_md, clean_name

def format_programme(prog: dict) -> str:
    """Formate un programme dict pour affichage Telegram."""
    now     = datetime.now(tz=timezone.utc)
    h_start = prog["start"].astimezone(TZ_PARIS).strftime("%H:%M")
    h_stop  = prog["stop"].astimezone(TZ_PARIS).strftime("%H:%M")
    en_cours = "🔴 " if prog["start"] <= now < prog["stop"] else ""
    new_tag  = " 🆕" if prog.get("new") else ""
    texte    = f"{en_cours}🕐 *{h_start}–{h_stop}*  {sanitize_md(prog['title'])}{new_tag}\n"
    if prog.get("cat"):
        texte += f"   📂 _{sanitize_md(prog['cat'])}_\n"
    if prog.get("desc"):
        texte += f"   📝 {sanitize_md(prog['desc'])}\n"
    return texte

async def send_soir_blocs(results, channels, jour_label, now_utc, send_fn, edit_fn):
    """Envoie les résultats soirée par bloc de chaînes."""
    if not results:
        await edit_fn(f"❌ Aucun programme de soirée trouvé pour la TNT ({jour_label}).")
        return
    
    ch_order = {ch: i for i, ch in enumerate(CH_TNT_FR)}
    results.sort(key=lambda x: (ch_order.get(x["ch_id"], 99), x["start"]))
    grouped  = defaultdict(list)
    for r in results:
        grouped[r["ch_id"]].append(r)
    
    lines = []
    for ch_id in CH_TNT_FR:
        if ch_id not in grouped:
            continue
        nom     = sanitize_md(clean_name(channels.get(ch_id, ch_id)))
        bloc_ch = f"━━━━━━━━━━━━━\n📺 *{nom}*\n"
        for r in grouped[ch_id]:
            h_start  = r["start"].astimezone(TZ_PARIS).strftime("%H:%M")
            h_stop   = r["stop"].astimezone(TZ_PARIS).strftime("%H:%M")
            en_cours = "🔴 " if r["start"] <= now_utc < r["stop"] else ""
            new_tag  = " 🆕" if r.get("new") else ""
            bloc_ch += f"{en_cours}🕐 {h_start}–{h_stop}  {sanitize_md(r['title'])}{new_tag}\n"
            if r.get("desc"):
                bloc_ch += f"   📝 {sanitize_md(r['desc'])}\n"
        lines.append(bloc_ch)
    
    bloc  = f"🌃 *Programme TV de la soirée*\n📅 {jour_label} – 19h à 00h – TNT FR\n\n"
    first = True
    for line in lines:
        if len(bloc) + len(line) > 4000:
            if first:
                await edit_fn(bloc)
                first = False
            else:
                await send_fn(bloc)
            bloc = ""
        bloc += line + "\n"
    if bloc.strip():
        if first:
            await edit_fn(bloc)
        else:
            await send_fn(bloc)

async def send_type_blocs(results, jour_label, now_utc, header: str,
                          edit_fn, send_fn, ch_order_list: list = None):
    """Envoie les résultats filtrés (films, séries, sport) par bloc."""
    if not results:
        await edit_fn(f"❌ Aucun résultat trouvé pour le {jour_label}.")
        return
    
    ref_list = ch_order_list or CH_TNT_FR
    ch_order = {ch: i for i, ch in enumerate(ref_list)}
    results.sort(key=lambda x: (ch_order.get(x["ch_id"], 99), x["start"]))
    grouped     = defaultdict(list)
    for r in results:
        grouped[r["ch_id"]].append(r)
    
    ordered_ids = [ch for ch in ref_list if ch in grouped]
    extras      = sorted([ch for ch in grouped if ch not in ch_order],
                         key=lambda c: grouped[c][0]["start"])
    ordered_ids += extras
    
    lines = []
    for ch_id in ordered_ids:
        nom     = sanitize_md(grouped[ch_id][0]["channel"])
        bloc_ch = f"━━━━━━━━━━━━━\n📺 *{nom}*\n"
        for r in grouped[ch_id]:
            h_start  = r["start"].astimezone(TZ_PARIS).strftime("%H:%M")
            h_stop   = r["stop"].astimezone(TZ_PARIS).strftime("%H:%M")
            en_cours = "🔴 " if r["start"] <= now_utc < r["stop"] else ""
            ph_tag   = " ⚠️" if r.get("placeholder") else ""
            new_tag  = " 🆕" if r.get("new") else ""
            bloc_ch += f"{en_cours}🕐 {h_start}–{h_stop}  ⏱ {r['duree']}  {sanitize_md(r['title'])}{ph_tag}{new_tag}\n"
            if r.get("desc") and not r.get("placeholder"):
                bloc_ch += f"   📝 {sanitize_md(r['desc'])}\n"
        lines.append(bloc_ch)
    
    bloc  = f"{header}\n📅 {jour_label}\n\n"
    first = True
    for line in lines:
        if len(bloc) + len(line) > 4000:
            if first:
                await edit_fn(bloc)
                first = False
            else:
                await send_fn(bloc)
            bloc = ""
        bloc += line + "\n"
    if bloc.strip():
        if first:
            await edit_fn(bloc)
        else:
            await send_fn(bloc)
