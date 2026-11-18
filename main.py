import uvicorn
import os
import sys

# Garante que o diretório backend esteja no sys.path
backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

if __name__ == "__main__":
    print("=" * 60)
    print("Iniciando Servidor Backend Whisper Subtitle Generator")
    print("Acesse a documentação da API em: http://127.0.0.1:8000/docs")
    print("=" * 60)
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True, app_dir=backend_dir)
