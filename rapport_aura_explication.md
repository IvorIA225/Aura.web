# 📚 Comment fonctionne l'application Aura — Explication complète

> Ce rapport t'explique, en langage simple, **comment l'application Aura a été construite**, fichier par fichier, brique par brique.

---

## 🏗️ Vue d'ensemble : les 3 grandes parties d'une application web

Avant de plonger dans le code, comprends ceci : **toute application web est composée de 3 parties qui communiquent entre elles** :

```
┌─────────────────────────────────────────────────────┐
│                                                       │
│   1. FRONTEND        2. BACKEND         3. BASE DE    │
│   (ce que tu vois)   (le cerveau)       DONNÉES       │
│                                         (la mémoire)  │
│   HTML + CSS + JS  ←→  Python/FastAPI  ←→  SQLite /  │
│   (navigateur)         (serveur)           Supabase   │
│                                                       │
└─────────────────────────────────────────────────────┘
```

Le **Frontend** = l'interface que l'utilisateur voit et utilise.  
Le **Backend** = le programme Python qui reçoit les demandes, les traite et répond.  
La **Base de données** = là où on stocke les informations (utilisateurs, messages, profils).

---

## 📁 Structure des fichiers du projet

```
d:\Projets_IA\
│
├── api_aura.py          ← 🧠 LE CERVEAU (Backend Python)
├── database.py          ← 🗄️ LA MÉMOIRE (Gestion base de données)
├── .env                 ← 🔑 LES CLÉS SECRÈTES (mots de passe APIs)
├── requirements.txt     ← 📦 LA LISTE DES OUTILS nécessaires
├── run_aura_web.bat     ← 🚀 LE BOUTON DE DÉMARRAGE
│
└── static_aura/         ← 🎨 L'INTERFACE VISUELLE (Frontend)
    ├── index.html       ← La structure de la page
    ├── style.css        ← L'apparence visuelle (couleurs, animations)
    └── app.js           ← Le comportement (clics, envoi de messages)
```

---

## 🔑 Fichier `.env` — Les clés secrètes

```ini
GROQ_API_KEY=gsk_...        ← Clé pour utiliser l'IA (Llama 3.3)
ELEVENLABS_API_KEY=sk_...   ← Clé pour la synthèse vocale
ENCRYPTION_KEY=...          ← Clé pour chiffrer les données
```

**En clair :** Le `.env` c'est comme ton **carnet de mots de passe**. Il contient les clés pour accéder aux services externes (l'IA, la voix). On ne met JAMAIS ces clés directement dans le code — si quelqu'un vole ton code, il ne verra pas tes clés.

> [!CAUTION]
> Ne partage JAMAIS ton fichier `.env` publiquement (GitHub, etc.). Il contient des secrets sensibles.

---

## 📦 Fichier `requirements.txt` — Les outils nécessaires

```
fastapi       ← Le framework pour créer le serveur web
groq          ← Pour parler à l'IA Llama 3.3
python-dotenv ← Pour lire le fichier .env
requests      ← Pour faire des appels à d'autres sites web
supabase      ← Pour la base de données en ligne
aiofiles      ← Pour lire des fichiers de manière rapide
```

**En clair :** C'est la **liste de courses**. Avant de démarrer l'application, Python télécharge et installe tous ces outils. C'est comme installer des applications sur ton téléphone avant de les utiliser.

On les installe avec : `pip install -r requirements.txt`

---

## 🚀 Fichier `run_aura_web.bat` — Le bouton de démarrage

```batch
@echo off
if not exist .venv (
    python -m venv .venv          ← Crée un espace de travail isolé
)
call .venv\Scripts\activate.bat  ← Active cet espace
pip install -r requirements.txt  ← Installe les outils
python api_aura.py               ← Démarre l'application !
```

**En clair :** Ce fichier `.bat` est un **script automatique** qui fait tout en un clic :
1. Il crée un **environnement virtuel** (`.venv`) — imagine une boîte isolée pour ton projet, pour ne pas mélanger les outils de différents projets.
2. Il installe les dépendances.
3. Il lance le serveur.

---

## 🧠 Fichier `api_aura.py` — LE CŒUR DE L'APPLICATION

C'est le fichier le plus important. Il gère toute la logique.

### Étape 1 : Les imports et la configuration

```python
from fastapi import FastAPI
from groq import Groq
from dotenv import load_dotenv

load_dotenv()  # Lit le fichier .env
```

**En clair :** On charge les outils (comme sortir les ustensiles de cuisine avant de cuisiner).

---

### Étape 2 : La personnalité d'Aura (le "Prompt Système")

```python
PERSONA_FEMININE = """
Tu es Aura, une jeune femme chaleureuse...
Utilise : "je suis contente", "je suis désolée"...
"""

PERSONA_MASCULINE = """
Tu es Aura, un jeune homme posé...
Utilise : "je suis content", "je suis désolé"...
"""
```

**En clair :** Le "prompt système" c'est les **instructions secrètes** qu'on donne à l'IA avant qu'elle parle à l'utilisateur. C'est comme lui dire "tu joues le rôle de...". L'utilisateur ne voit jamais ces instructions.

Le `SYSTEM_PROMPT_BASE` contient les règles générales :
- Valider les émotions
- Poser une seule question à la fois
- Répondre en 3-4 phrases max
- Appeler l'étudiant par son prénom

---

### Étape 3 : Créer le serveur web

```python
app = FastAPI(title="Aura Web API")

app.add_middleware(CORSMiddleware, allow_origins=["*"])
```

**En clair :** `FastAPI` crée un **serveur web** — c'est comme ouvrir un restaurant. Le `CORSMiddleware` dit "tout le monde est le bienvenu" (on accepte les demandes de n'importe quelle adresse web).

---

### Étape 4 : Servir les fichiers visuels

```python
app.mount("/static", StaticFiles(directory="static_aura"), name="static")

@app.get("/")
async def root():
    return FileResponse("static_aura/index.html")
```

**En clair :** Quand tu ouvres `http://localhost:8000`, le serveur t'envoie le fichier `index.html`. C'est comme le serveur d'un restaurant qui t'apporte le menu.

---

### Étape 5 : Les "Routes" — Les portes de communication

Une **route** c'est une URL qui fait quelque chose. Voici les 3 routes principales :

#### 🚪 Route 1 : Démarrer une session

```python
@app.post("/api/session/start")
async def start_session(req: SessionStartRequest):
    # 1. Vérifie que le prénom est valide
    # 2. Vérifie que le code PIN (5 chiffres) est correct
    # 3. Trouve ou crée l'utilisateur en base de données
    # 4. Charge l'historique des conversations
    # 5. Si nouveau, génère un message de bienvenue avec l'IA
    # 6. Retourne tout ça au frontend
```

**En clair :** Quand tu cliques sur "Commencer", le frontend envoie ton prénom et ton PIN. Le backend vérifie, te reconnecte ou te crée un compte, et répond avec tes anciennes conversations.

---

#### 🚪 Route 2 : Envoyer un message

```python
@app.post("/api/chat")
async def chat(req: ChatRequest):
    # 1. Vérifie si l'utilisateur n'a pas dépassé 20 messages/jour
    # 2. Charge le profil et l'historique
    # 3. Enregistre le message de l'utilisateur
    # 4. Envoie tout à l'IA Groq (Llama 3.3)
    # 5. Reçoit la réponse d'Aura
    # 6. Enregistre la réponse
    # 7. (Optionnel) Génère l'audio avec ElevenLabs
    # 8. Retourne la réponse au frontend
```

**En clair :** C'est la route la plus utilisée. Elle fait office de **chef d'orchestre** : elle reçoit ton message, le transmet à l'IA, récupère la réponse, et te la renvoie.

---

#### 🚪 Route 3 : Effacer l'historique

```python
@app.delete("/api/history/{user_id}")
async def clear_history(user_id: str):
    database.supprimer_historique(user_id)
    return {"status": "success"}
```

**En clair :** Quand tu cliques "Effacer l'historique", une simple demande de suppression est envoyée.

---

### Étape 6 : La mise à jour du profil en arrière-plan

```python
background_tasks.add_task(mettre_a_jour_profil_ia, ...)
```

**En clair :** Après chaque message, l'application **analyse silencieusement** la conversation pour extraire des infos sur toi (tes défis, ton humeur, tes objectifs). Elle le fait **en arrière-plan** pour ne pas ralentir la réponse. C'est comme si le restaurant notait tes préférences pour ta prochaine visite.

---

## 🗄️ Fichier `database.py` — LA MÉMOIRE DE L'APPLICATION

### Les 2 modes de stockage

```python
USE_SUPABASE = bool(SUPABASE_URL and SUPABASE_KEY)
```

L'application peut stocker les données de **2 façons** :

| Mode | Quand ? | Avantage |
|------|---------|----------|
| **SQLite** (fichier local) | En développement | Simple, pas besoin d'internet |
| **Supabase** (cloud) | En production (Vercel) | Accessible partout |

**En clair :** SQLite c'est un fichier `.db` sur ton ordinateur. Supabase c'est une base de données en ligne. L'application détecte automatiquement lequel utiliser.

---

### Les 5 tables de la base de données

```
┌─────────────┐    ┌──────────────┐    ┌──────────────┐
│   users     │    │   messages   │    │   profils    │
│─────────────│    │──────────────│    │──────────────│
│ id (UUID)   │◄───│ user_id      │    │ user_id      │
│ real_name   │    │ role         │    │ situation    │
│ pin         │    │ content      │    │ defis        │
│ is_premium  │    │ timestamp    │    │ objectifs    │
└─────────────┘    └──────────────┘    │ humeur       │
                                       │ notes_aura   │
┌─────────────┐    ┌──────────────┐    └──────────────┘
│   humeurs   │    │ logs_acces   │
│─────────────│    │──────────────│
│ user_id     │    │ user_id      │
│ score       │    │ action       │
│ emoji       │    │ timestamp    │
│ note        │    └──────────────┘
└─────────────┘
```

**En clair :**
- `users` → Qui tu es (prénom, PIN, premium ou non)
- `messages` → Tout ce que toi et Aura vous avez dit
- `profils` → Ce qu'Aura a appris sur toi (mémoire longue durée)
- `humeurs` → Tes émotions enregistrées
- `logs_acces` → Quand tu t'es connecté

---

### Le système d'identité anonyme

```python
def obtenir_ou_creer_id_anonyme(prenom, pin):
    # Si le prénom existe → vérifie le PIN → retourne l'ID
    # Sinon → crée un nouvel utilisateur avec un UUID unique
```

**En clair :** L'ID d'un utilisateur est un **UUID** (une chaîne de caractères aléatoire comme `a3f1-b2c3-...`). Jamais ton vrai nom n'est utilisé comme identifiant — c'est la protection de ta vie privée.

---

## 🎨 Frontend — L'interface visuelle (3 fichiers)

### `index.html` — La structure

C'est le **squelette** de la page. Il définit ce qui existe sur la page.

```
L'application a 2 écrans :
│
├── ÉCRAN 1 : "mood-screen" (l'accueil / login)
│   ├── Logo Aura ✨
│   ├── Formulaire : prénom + PIN
│   ├── Choix du genre d'Aura (féminin/masculin)
│   └── Sélecteur d'humeur (😊🌧️🦋🌊🔥)
│
└── ÉCRAN 2 : "chat-screen" (la conversation)
    ├── Barre latérale (sidebar) avec paramètres
    └── Zone de chat (messages + zone de saisie)
```

**En clair :** HTML c'est comme le **plan d'un appartement**. Il dit "là il y a un mur, là il y a une porte, là il y a une fenêtre". Mais pas la couleur ni la décoration.

---

### `style.css` — L'apparence

C'est tout ce qui est **visuel** : couleurs, polices, animations, effets de verre (glassmorphism), disposition.

Les techniques utilisées dans Aura :
- **Variables CSS** (`--color-primary`, etc.) → Pour changer les couleurs facilement
- **Glassmorphism** → Effet de verre dépoli (fond flou, transparent)
- **Animations** → Les points qui pulsent quand Aura "écrit"
- **Responsive design** → S'adapte aux téléphones et ordinateurs

---

### `app.js` — Le comportement (la logique côté navigateur)

C'est ce qui **fait bouger** les choses quand tu cliques ou écris.

```javascript
// 1. Au démarrage, on "attrape" tous les éléments HTML importants
const loginBtn = document.getElementById('login-btn');
const chatInput = document.getElementById('chat-input');

// 2. On "écoute" les actions de l'utilisateur
loginBtn.addEventListener('click', () => {
    // Vérifier les champs, puis afficher l'écran suivant
});

// 3. Pour parler au serveur, on utilise "fetch"
const res = await fetch('/api/chat', {
    method: 'POST',
    body: JSON.stringify({ message: text, ... })
});
const data = await res.json();
// Afficher la réponse
```

**En clair :** JavaScript c'est le **chef de salle** du restaurant. Il accueille le client (écoute les clics), transmet la commande en cuisine (envoie au backend), et apporte le plat (affiche la réponse).

Le mot clé `async/await` permet d'**attendre** la réponse du serveur sans bloquer toute la page.

---

## 🔄 Le flux complet d'une conversation

Voici ce qui se passe quand tu envoies un message à Aura :

```
TOI                    FRONTEND (JS)              BACKEND (Python)         IA (Groq)
 │                         │                           │                      │
 │── Tu cliques "Envoyer" ─►│                           │                      │
 │                         │── fetch('/api/chat') ────►│                      │
 │                         │                           │── Charge ton profil  │
 │                         │                           │── Prépare le prompt  │
 │                         │                           │──────────────────────►│
 │                         │                           │                      │ Génère
 │                         │                           │◄─────────────────────│ la réponse
 │                         │                           │── Sauvegarde en DB   │
 │                         │◄── Retourne la réponse ───│                      │
 │◄── Affiche le message ──│                           │                      │
 │                         │                           │── (arrière-plan) ────►│
 │                         │                           │   Met à jour profil  │
```

---

## 🌐 Les APIs externes utilisées

### 1. Groq (l'intelligence artificielle)

```python
client = Groq(api_key=GROQ_API_KEY)
response = client.chat.completions.create(
    model="llama-3.3-70b-versatile",  ← Le modèle IA
    messages=[...],                    ← La conversation
    temperature=0.75,                  ← Créativité (0=rigide, 1=créatif)
    max_tokens=400                     ← Longueur max de la réponse
)
```

**En clair :** On envoie à Groq la conversation entière + les instructions (prompt système), et il nous retourne la réponse d'Aura. `temperature=0.75` signifie qu'Aura est un peu créative mais reste cohérente.

### 2. ElevenLabs (la voix)

```python
requests.post(
    f"https://api.elevenlabs.io/v1/text-to-speech/{voix_id}",
    json={"text": texte, "model_id": "eleven_multilingual_v2"}
)
```

**En clair :** On envoie le texte à ElevenLabs, et ils nous retournent un fichier audio MP3. On encode ce fichier en **base64** (une façon de transformer un fichier en texte) pour l'envoyer dans la réponse JSON.

---

## 🛡️ Les mécanismes de sécurité

| Mécanisme | Où ? | Rôle |
|-----------|------|------|
| **PIN à 5 chiffres** | `database.py` | Protège le compte de chaque utilisateur |
| **UUID** | `database.py` | ID anonyme, jamais le vrai nom en base |
| **Limite 20 messages/jour** | `database.py` | Évite l'abus d'utilisation |
| **Validation du prénom** | `database.py` | Bloque les caractères dangereux |
| **Variables d'environnement** | `.env` | Clés API jamais dans le code source |

---

## 🎓 Résumé — Ce que tu as appris à construire

```
┌─────────────────────────────────────────────────────────────┐
│                     APPLICATION AURA                         │
│                                                              │
│  Frontend          Backend              Services externes    │
│  ─────────         ───────              ──────────────────   │
│  HTML              FastAPI (Python)     Groq (IA Llama 3.3) │
│  CSS               SQLite / Supabase    ElevenLabs (voix)   │
│  JavaScript        python-dotenv                            │
│                    pydantic (validation)                     │
│                                                              │
│  Concepts maîtrisés :                                        │
│  ✅ Architecture client-serveur                              │
│  ✅ API REST (GET, POST, DELETE)                             │
│  ✅ Base de données relationnelle (tables, FOREIGN KEY)      │
│  ✅ Prompt engineering (instructions à l'IA)                 │
│  ✅ Environnement virtuel Python                             │
│  ✅ Variables d'environnement (sécurité)                     │
│  ✅ fetch() / async-await (JavaScript)                       │
│  ✅ Background tasks (tâches en arrière-plan)                │
└─────────────────────────────────────────────────────────────┘
```

---

## 📖 Prochaines étapes pour approfondir

1. **Python + FastAPI** → [fastapi.tiangolo.com](https://fastapi.tiangolo.com)
2. **SQL (bases de données)** → Cours SQLite sur W3Schools
3. **JavaScript moderne** → [javascript.info](https://javascript.info) (en anglais mais excellent)
4. **APIs et HTTP** → Comprendre GET, POST, PUT, DELETE
5. **Déploiement** → Vercel (pour le frontend) + Railway (pour le backend Python)

> [!TIP]
> La meilleure façon d'apprendre est de **modifier l'application existante** : change une couleur dans le CSS, ajoute une règle au prompt, ajoute un nouveau champ dans la base de données. Chaque modification t'apprend quelque chose de concret.
