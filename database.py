import os
import re
import uuid
import hashlib
import datetime
import sqlite3
import logging
from dotenv import load_dotenv
from cryptography.fernet import Fernet

load_dotenv(override=True)

# --- Chiffrement des messages ---
_RAW_KEY = os.getenv("ENCRYPTION_KEY", "")
try:
    cipher = Fernet(_RAW_KEY.encode()) if _RAW_KEY else None
except Exception:
    cipher = None

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
USE_SUPABASE = bool(SUPABASE_URL and SUPABASE_KEY)

if USE_SUPABASE:
    try:
        from supabase import create_client, Client
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        logging.error(f"Erreur init Supabase: {e}")
        USE_SUPABASE = False
        supabase = None
else:
    supabase = None

DB_NAME = "aura_data.db"

def init_db():
    if USE_SUPABASE:
        return # Sur Supabase, les tables sont créées via l'interface SQL
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            real_name TEXT UNIQUE,
            created_at TIMESTAMP,
            is_premium INTEGER DEFAULT 0
        )
    """)
    try:
        c.execute("ALTER TABLE users ADD COLUMN pin TEXT")
    except sqlite3.OperationalError:
        pass
    c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            message_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            role TEXT,
            content TEXT,
            timestamp TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS profils (
            user_id TEXT PRIMARY KEY,
            prenom TEXT,
            situation TEXT,
            defis TEXT,
            objectifs TEXT,
            humeur_generale TEXT,
            preferences TEXT,
            notes_aura TEXT,
            derniere_maj TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS humeurs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            score INTEGER,
            emoji TEXT,
            note TEXT,
            date TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS logs_acces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            action TEXT,
            timestamp TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def valider_prenom(prenom):
    if not prenom: return False
    return bool(re.match("^[a-zA-ZÀ-ÿ -]+$", prenom))

def hasher_pin(pin: str) -> str:
    """Hash le PIN avec SHA-256 (irréversible)."""
    return hashlib.sha256(pin.encode()).hexdigest()

def chiffrer(texte: str) -> str:
    """Chiffre un texte avant de le stocker en base."""
    if not cipher:
        return texte
    return cipher.encrypt(texte.encode()).decode()

def dechiffrer(texte: str) -> str:
    """Déchiffre un texte récupéré depuis la base."""
    if not cipher:
        return texte
    try:
        return cipher.decrypt(texte.encode()).decode()
    except Exception:
        return texte  # Texte ancien non chiffré → retourner tel quel

def verifier_user(user_id: str, prenom: str) -> bool:
    """Vérifie que le user_id appartient bien au prénom fourni."""
    if USE_SUPABASE:
        res = supabase.table("users").select("id").eq("id", user_id).ilike("real_name", prenom.strip()).execute()
        return bool(res.data and len(res.data) > 0)
    else:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT 1 FROM users WHERE id = ? AND LOWER(real_name) = ?",
                  (user_id, prenom.strip().lower()))
        ok = c.fetchone() is not None
        conn.close()
        return ok

def obtenir_ou_creer_id_anonyme(prenom, pin=None):
    prenom_clean = prenom.strip()
    pin_hash = hasher_pin(pin) if pin else None
    if USE_SUPABASE:
        res = supabase.table("users").select("id, pin").ilike("real_name", prenom_clean).execute()
        if res.data and len(res.data) > 0:
            user = res.data[0]
            if pin_hash is not None and user.get("pin") and user.get("pin") != pin_hash:
                raise ValueError("Code secret incorrect. ❌")
            return user['id']
        else:
            new_id = str(uuid.uuid4())
            supabase.table("users").insert({
                "id": new_id,
                "real_name": prenom_clean,
                "is_premium": 0,
                "pin": pin_hash
            }).execute()
            return new_id
    else:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT id, pin FROM users WHERE LOWER(real_name) = ?", (prenom_clean.lower(),))
        row = c.fetchone()
        if row:
            user_id = row[0]
            db_pin = row[1]
            if pin_hash is not None and db_pin and db_pin != pin_hash:
                conn.close()
                raise ValueError("Code secret incorrect. ❌")
            if pin_hash is not None and not db_pin:
                c.execute("UPDATE users SET pin = ? WHERE id = ?", (pin_hash, user_id))
                conn.commit()
        else:
            user_id = str(uuid.uuid4())
            c.execute("INSERT INTO users (id, real_name, created_at, is_premium, pin) VALUES (?, ?, ?, ?, ?)",
                      (user_id, prenom_clean, datetime.datetime.now(), 0, pin_hash))
        conn.commit()
        conn.close()
        return user_id

def est_premium(user_id):
    if USE_SUPABASE:
        res = supabase.table("users").select("is_premium").eq("id", user_id).execute()
        if res.data:
            return res.data[0]['is_premium'] == 1
        return False
    else:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT is_premium FROM users WHERE id = ?", (user_id,))
        row = c.fetchone()
        conn.close()
        return row and row[0] == 1

def sauvegarder_conversation(user_id, role, message):
    contenu = chiffrer(message)
    if USE_SUPABASE:
        supabase.table("messages").insert({
            "user_id": user_id,
            "role": role,
            "content": contenu
        }).execute()
    else:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("INSERT INTO messages (user_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                  (user_id, role, contenu, datetime.datetime.now()))
        conn.commit()
        conn.close()

def charger_historique(user_id):
    if USE_SUPABASE:
        res = supabase.table("messages").select("role, content").eq("user_id", user_id).order("timestamp").execute()
        if not res.data:
            return []
        return [{"role": m["role"], "content": dechiffrer(m["content"])} for m in res.data]
    else:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT role, content FROM messages WHERE user_id = ? ORDER BY timestamp ASC", (user_id,))
        rows = c.fetchall()
        conn.close()
        return [{"role": row[0], "content": dechiffrer(row[1])} for row in rows]

def supprimer_historique(user_id):
    if USE_SUPABASE:
        supabase.table("messages").delete().eq("user_id", user_id).execute()
    else:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("DELETE FROM messages WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()

def compter_messages(user_id):
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    if USE_SUPABASE:
        res = supabase.table("messages").select("message_id", count="exact").eq("user_id", user_id).eq("role", "user").gte("timestamp", f"{today_str}T00:00:00").execute()
        return res.count if res.count else 0
    else:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM messages WHERE user_id = ? AND role = 'user' AND DATE(timestamp) = ?", (user_id, today_str))
        count = c.fetchone()[0]
        conn.close()
        return count

def verifier_limite_messages(user_id):
    premium = est_premium(user_id)
    limite = 100 if premium else 20
    count = compter_messages(user_id)
    return (count < limite, count, limite)

def charger_profil(user_id):
    if USE_SUPABASE:
        res = supabase.table("profils").select("*").eq("user_id", user_id).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]
        return {}
    else:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT prenom, situation, defis, objectifs, humeur_generale, preferences, notes_aura FROM profils WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        conn.close()
        if row:
            return {
                "prenom": row[0], "situation": row[1], "defis": row[2], 
                "objectifs": row[3], "humeur_generale": row[4], 
                "preferences": row[5], "notes_aura": row[6]
            }
        return {}

def sauvegarder_profil(user_id, data):
    now = datetime.datetime.now().isoformat()
    if USE_SUPABASE:
        payload = {
            "user_id": user_id,
            "prenom": data.get('prenom', ''),
            "situation": data.get('situation', ''),
            "defis": data.get('defis', ''),
            "objectifs": data.get('objectifs', ''),
            "humeur_generale": data.get('humeur_generale', ''),
            "preferences": data.get('preferences', ''),
            "notes_aura": data.get('notes_aura', ''),
            "derniere_maj": now
        }
        supabase.table("profils").upsert(payload).execute()
    else:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute("SELECT 1 FROM profils WHERE user_id = ?", (user_id,))
        if c.fetchone():
            c.execute("""
                UPDATE profils SET
                prenom = ?, situation = ?, defis = ?, objectifs = ?, humeur_generale = ?, preferences = ?, notes_aura = ?, derniere_maj = ?
                WHERE user_id = ?
            """, (
                data.get('prenom', ''), data.get('situation', ''), data.get('defis', ''), 
                data.get('objectifs', ''), data.get('humeur_generale', ''), 
                data.get('preferences', ''), data.get('notes_aura', ''), now_str, user_id
            ))
        else:
            c.execute("""
                INSERT INTO profils (user_id, prenom, situation, defis, objectifs, humeur_generale, preferences, notes_aura, derniere_maj)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id, data.get('prenom', ''), data.get('situation', ''), data.get('defis', ''), 
                data.get('objectifs', ''), data.get('humeur_generale', ''), 
                data.get('preferences', ''), data.get('notes_aura', ''), now_str
            ))
        conn.commit()
        conn.close()

def sauvegarder_humeur(user_id, score, emoji, note):
    if USE_SUPABASE:
        supabase.table("humeurs").insert({
            "user_id": user_id,
            "score": score,
            "emoji": emoji,
            "note": note
        }).execute()
    else:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("INSERT INTO humeurs (user_id, score, emoji, note, date) VALUES (?, ?, ?, ?, ?)",
                  (user_id, score, emoji, note, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()

def journaliser(user_id, action):
    if USE_SUPABASE:
        supabase.table("logs_acces").insert({
            "user_id": user_id,
            "action": action
        }).execute()
    else:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("INSERT INTO logs_acces (user_id, action, timestamp) VALUES (?, ?, ?)",
                  (user_id, action, datetime.datetime.now()))
        conn.commit()
        conn.close()
