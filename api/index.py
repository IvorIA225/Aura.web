import os
import sys

# Ajouter la racine du projet au path pour que database.py soit trouvé
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api_aura import app  # noqa: F401  — Vercel cherche `app` dans ce module
