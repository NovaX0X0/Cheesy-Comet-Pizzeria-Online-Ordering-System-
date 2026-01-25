# Cheesy Comet Pizzeria – Local Run Instructions (FastAPI)

## 1) Open a terminal in this folder
You should be in the folder that contains **requirements.txt** and the **pizza_app** folder.

## 2) Create and activate a virtual environment (recommended)
**PowerShell (Windows):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**Command Prompt (Windows):**
```bat
python -m venv venv
venv\Scripts\activate
```

## 3) Install dependencies
```powershell
python -m pip install -r requirements.txt
```

## 4) Run the server
This project supports **either** module name:
- If you have `main.py`:
  ```powershell
  python -m uvicorn main:app --reload
  ```
- If you have `app.py`:
  ```powershell
  python -m uvicorn app:app --reload
  ```

## 5) Open in your browser
- Home: http://127.0.0.1:8000/
- Customize: http://127.0.0.1:8000/customize
- Checkout: http://127.0.0.1:8000/checkout
- Confirmation: http://127.0.0.1:8000/confirmation

## Stop the server
Press **CTRL + C** in the terminal.
