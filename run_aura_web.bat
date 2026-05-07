@echo off
echo.
echo ========================================================
echo   Lancement de l'API Web Aura (Nouveau Design)
echo ========================================================
echo.

if not exist .venv (
    echo [1/3] Creation de l'environnement virtuel...
    python -m venv .venv
)

echo [2/3] Activation et installation des dependances...
call .venv\Scripts\activate.bat
pip install -r requirements.txt
pip install fastapi uvicorn pydantic python-multipart httpx aiofiles supabase

echo [3/3] Demarrage du serveur...
python api_aura.py
