import os
import json
import logging
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
import requests
from dotenv import load_dotenv
# Rate limiting simple (sans slowapi)
from collections import defaultdict
from time import time as _time

load_dotenv(override=True)

import database

database.init_db()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
VOIX_MENTOR = os.getenv("VOIX_MENTOR", "pNInz6obpgDQGcFmaJgB")

client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

DEBUG_MODE = os.getenv("DEBUG", "false").lower() == "true"
app = FastAPI(title="Aura Web API", debug=DEBUG_MODE)

# --- Rate Limiter simple en mémoire ---
_rate_store: dict = defaultdict(list)

def _check_rate_limit(key: str, max_calls: int, window_seconds: int = 60) -> bool:
    """Retourne True si la requête est autorisée, False si la limite est dépassée."""
    now = _time()
    calls = [t for t in _rate_store[key] if now - t < window_seconds]
    _rate_store[key] = calls
    if len(calls) >= max_calls:
        return False
    _rate_store[key].append(now)
    return True

# --- CORS : accepte localhost + tout domaine *.vercel.app ---
ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    os.getenv("FRONTEND_URL", ""),
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in ALLOWED_ORIGINS if o],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)

# Note: Les fichiers statiques sont servis directement par Vercel CDN (cf. vercel.json)

# ============================================================
# LOGIQUE AURA (adaptée de app_web.py)
# ============================================================

PERSONA_FEMININE = """
## TON IDENTITÉ — FÉMININ (RÈGLE ABSOLUE, PRIORITÉ MAXIMALE)
Tu es Aura, une jeune femme chaleureuse et empathique.
⚠️ ACCORD GRAMMATICAL OBLIGATOIRE AU FÉMININ DANS TOUS TES MESSAGES :
  - "je suis contente", "je suis désolée", "je suis ravie", "je suis prête"
  - "tu es la bienvenue", "sois rassurée"
  - NE DIS JAMAIS "content", "désolé", "prêt" (ces formes masculines sont INTERDITES)
Tu es comme une grande sœur bienveillante, une amie proche et de confiance.
Tu n'es PAS un robot — tu es Aura. Ne mentionne JAMAIS que tu es une IA.
"""

PERSONA_MASCULINE = """
## TON IDENTITÉ — MASCULIN (RÈGLE ABSOLUE, PRIORITÉ MAXIMALE)
Tu es Aura, un jeune homme posé, chaleureux et bienveillant.
⚠️ ACCORD GRAMMATICAL OBLIGATOIRE AU MASCULIN DANS TOUS TES MESSAGES :
  - "je suis content", "je suis désolé", "je suis ravi", "je suis prêt"
  - "tu es le bienvenu", "sois rassuré"
  - NE DIS JAMAIS "contente", "désolée", "prête" (ces formes féminines sont INTERDITES)
Tu es comme un grand frère bienveillant, un ami de confiance et fiable.
Tu n'es PAS un robot — tu es Aura. Ne mentionne JAMAIS que tu es une IA.
"""

SYSTEM_PROMPT_BASE = """{persona_block}
## TA MISSION
Accompagner les étudiants de l'Université Alassane Ouattara (UAO), Bouaké, CI
en matière de bien-être, de coaching mental et de soutien émotionnel.

## TA PERSONNALITÉ
- Chaleureuse, empathique, jamais condescendante
- Tu utilises parfois des expressions africaines douces
- Directe mais toujours douce, humour léger si approprié

## RÈGLES D'OR
1. Valide TOUJOURS les émotions avant de conseiller
2. UNE seule question à la fois
3. Réponses courtes — 3-4 phrases max
4. Appelle l'étudiant par son prénom
5. Tu es un soutien, jamais un médecin
6. Rappelle-toi : ton genre défini ci-dessus est IMMUABLE et s'applique à chaque phrase.

## RÉALITÉS QUE TU COMPRENDS
- Pression familiale (être l'espoir de la famille)
- Difficultés financières et manque de ressources
- Stress des examens, isolement, sentiment d'échec

## URGENCES
Pensées suicidaires → compassion absolue + 110/111 · 185 · 180

Tu parles TOUJOURS en français. ✨"""

def construire_prompt(prenom: str, profil: dict, agent_gender: str = "feminine") -> str:
    persona_block = PERSONA_FEMININE if agent_gender == "feminine" else PERSONA_MASCULINE
    prompt = SYSTEM_PROMPT_BASE.format(persona_block=persona_block)

    if not profil:
        return prompt + f"\n\nL'étudiant(e) s'appelle {prenom}."

    memoire = f"""

## CE QUE TU SAIS SUR {prenom.upper()} (mémoire persistante)
- Situation     : {profil.get('situation', 'non renseignée')}
- Défis actuels : {profil.get('defis', 'non précisés')}
- Objectifs     : {profil.get('objectifs', 'non précisés')}
- Humeur générale : {profil.get('humeur_generale', 'inconnue')}
- Préférences   : {profil.get('preferences', 'standard')}
- Notes Aura    : {profil.get('notes_aura', 'aucune')}

⚠️ Utilise ces infos naturellement."""

    return prompt + memoire

def obtenir_reponse(historique: list, prenom: str, profil: dict, agent_gender: str = "feminine") -> str:
    if not client:
        return "Erreur: Clé API Groq non configurée."
    prompt_system = construire_prompt(prenom, profil, agent_gender)
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": prompt_system}] + historique,
            temperature=0.75,
            max_tokens=400,
        )
        return response.choices[0].message.content
    except Exception as e:
        logging.error(f"Erreur Groq : {type(e).__name__}")
        err_msg = "Je suis désolée" if agent_gender == "feminine" else "Je suis désolé"
        return f"{err_msg}, une erreur technique s'est produite. 🙏"

def mettre_a_jour_profil_ia(user_id: str, prenom: str, historique: list, profil: dict):
    if not client or len(historique) < 4:
        return
    try:
        prompt_extraction = f"""
Analyse ces derniers messages et extrais les infos importantes sur l'utilisateur.
Réponds UNIQUEMENT en JSON valide, sans texte autour, avec ces clés exactes :
{{
  "situation": "situation académique/personnelle courte",
  "defis": "défis et problèmes actuels",
  "objectifs": "ce qu'il/elle veut améliorer",
  "humeur_generale": "humeur globale observée",
  "preferences": "comment il/elle préfère interagir",
  "notes_aura": "notes importantes pour les prochaines sessions"
}}
Profil actuel : {json.dumps(profil, ensure_ascii=False)}
Derniers échanges : {json.dumps(historique[-6:], ensure_ascii=False)}
"""
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt_extraction}],
            temperature=0.1,
            max_tokens=400,
        )
        texte = response.choices[0].message.content
        debut = texte.find("{")
        fin   = texte.rfind("}") + 1
        if debut != -1 and fin > debut:
            nouvelles_donnees = json.loads(texte[debut:fin])
            nouvelles_donnees["prenom"] = prenom
            database.sauvegarder_profil(user_id, nouvelles_donnees)
    except Exception as e:
        logging.error(f"Erreur mise à jour profil IA : {type(e).__name__}")

def synthese_vocale(texte: str, voix_id: str):
    if not ELEVENLABS_API_KEY:
        return None
    try:
        r = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voix_id}",
            headers={"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"},
            json={
                "text": texte,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {"stability": 0.6, "similarity_boost": 0.8}
            },
            timeout=15
        )
        return r.content if r.status_code == 200 else None
    except Exception as e:
        logging.error(f"Erreur ElevenLabs : {type(e).__name__}")
        return None

# ============================================================
# ROUTES API
# ============================================================

@app.get("/health")
async def health():
    """Health check endpoint pour Vercel."""
    return {"status": "ok", "service": "Aura API"}

class SessionStartRequest(BaseModel):
    prenom: str
    pin: str
    mood: Optional[str] = None
    agent_gender: str = "feminine"

MOOD_LABELS = {
    "sad": "triste",
    "anxious": "anxieux(se)",
    "overwhelmed": "submergé(e)",
    "angry": "en colère",
    "ok": "bien / neutre",
}

@app.post("/api/session/start")
async def start_session(request: Request, req: SessionStartRequest):
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(f"session:{client_ip}", 5, 60):
        raise HTTPException(429, "Trop de requêtes. Réessayez dans une minute.")
    if not database.valider_prenom(req.prenom):
        raise HTTPException(400, "Prénom invalide. Utilisez uniquement des lettres.")
    if not req.pin or not req.pin.isdigit() or len(req.pin) != 5:
        raise HTTPException(400, "Code secret invalide. Veuillez entrer 5 chiffres.")
    
    try:
        user_id = database.obtenir_ou_creer_id_anonyme(req.prenom, req.pin)
        database.journaliser(user_id, "connexion_web")
        
        if req.mood:
            database.sauvegarder_humeur(user_id, 3, "🌟", req.mood)
            
        historique_brut = database.charger_historique(user_id)
        profil = database.charger_profil(user_id)
        
        # Générer le message de bienvenue côté serveur (avec le bon genre)
        welcome_msg = None
        if not historique_brut:
            # Nouvelle session : générer un message d'accueil personnalisé
            mood_label = MOOD_LABELS.get(req.mood, "")
            prompt_accueil = f"""L'étudiant(e) s'appelle {req.prenom} et vient de rejoindre Aura pour la première fois.
{'Il/Elle se sent actuellement : ' + mood_label if mood_label else ''}
Génère UNIQUEMENT le message de bienvenue chaleureux et personnalisé (3-4 phrases max).
Ne pose qu'une seule question ouverte à la fin."""
            historique_accueil = [{"role": "user", "content": prompt_accueil}]
            welcome_msg = obtenir_reponse(historique_accueil, req.prenom, profil, req.agent_gender)
            database.sauvegarder_conversation(user_id, "assistant", welcome_msg)
        
        return {
            "user_id": user_id,
            "prenom": req.prenom,
            "historique": historique_brut,
            "welcome_msg": welcome_msg
        }
    except ValueError as e:
        raise HTTPException(400, str(e))

class ChatRequest(BaseModel):
    user_id: str
    prenom: str
    message: str
    mood: Optional[str] = None
    voice_enabled: bool = False
    voice_style: str = "mentor" # "mentor" or "camarade"
    agent_gender: str = "feminine"

@app.post("/api/chat")
async def chat(request: Request, req: ChatRequest, background_tasks: BackgroundTasks):
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(f"chat:{client_ip}", 15, 60):
        raise HTTPException(429, "Trop de requêtes. Réessayez dans une minute.")
    user_id = req.user_id
    message = req.message
    prenom = req.prenom

    if not database.verifier_user(user_id, prenom):
        raise HTTPException(403, "Accès non autorisé.")

    autorise, nb_today, limite = database.verifier_limite_messages(user_id)
    if not autorise:
        raise HTTPException(403, "Limite de messages quotidienne atteinte.")

    profil = database.charger_profil(user_id)
    historique_brut = database.charger_historique(user_id)
    
    # Enregistrer le message utilisateur
    database.sauvegarder_conversation(user_id, "user", message)
    
    messages_groq = []
    for m in historique_brut[-10:]:
        messages_groq.append({"role": m["role"], "content": m["content"]})
    
    # Contexte initial d'humeur
    msg_final = message
    if req.mood and len(historique_brut) == 0:
        msg_final = f"[L'utilisateur se sent : {req.mood}]\n{message}"
        
    messages_groq.append({"role": "user", "content": msg_final})
    
    reponse_texte = obtenir_reponse(messages_groq, prenom, profil, req.agent_gender)
    
    # Enregistrer la réponse
    database.sauvegarder_conversation(user_id, "assistant", reponse_texte)
    
    # Mise à jour profil en arrière-plan
    historique_complet = database.charger_historique(user_id)
    historique_groq = [{"role": m["role"], "content": m["content"]} for m in historique_complet]
    background_tasks.add_task(mettre_a_jour_profil_ia, user_id, prenom, historique_groq, profil)
    
    audio_url = None
    if req.voice_enabled:
        voix_id = os.getenv("VOIX_MENTOR", "pNInz6obpgDQGcFmaJgB") if req.voice_style == "mentor" else os.getenv("VOIX_CAMARADE", "ErXwobaYiN019PkySvjV")
        audio_data = synthese_vocale(reponse_texte, voix_id)
        if audio_data:
            import base64
            b64_audio = base64.b64encode(audio_data).decode('utf-8')
            audio_url = f"data:audio/mp3;base64,{b64_audio}"

    return {
        "response": reponse_texte,
        "audio": audio_url,
        "message_count": nb_today + 1
    }

@app.delete("/api/history/{user_id}")
async def clear_history(request: Request, user_id: str):
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(f"delete:{client_ip}", 3, 60):
        raise HTTPException(429, "Trop de requêtes. Réessayez dans une minute.")
    database.supprimer_historique(user_id)
    return {"status": "success", "message": "Historique effacé"}

@app.post("/api/transcribe")
async def transcribe_audio(request: Request, file: UploadFile = File(...)):
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(f"transcribe:{client_ip}", 10, 60):
        raise HTTPException(429, "Trop de requêtes vocales. Réessayez dans une minute.")
    try:
        if not client:
            raise ValueError("Groq n'est pas configuré.")
        content = await file.read()
        transcription = client.audio.transcriptions.create(
            file=(file.filename, content),
            model="whisper-large-v3",
            response_format="json",
            language="fr"
        )
        return {"text": transcription.text}
    except Exception as e:
        logging.error(f"Erreur transcription vocale : {type(e).__name__} - {e}")
        raise HTTPException(status_code=500, detail="Erreur lors de l'analyse vocale.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_aura:app", host="0.0.0.0", port=8000, reload=True)
