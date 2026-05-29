# Gradient-Backend

### Для початку потрібно створити серидовище в яке будуть завантажуватись усі необхідні тули:
    python -m venv .venv

### Або можна використати таку команду якщо встановлено декілька версій пайтона:
    py -3.11 -m venv .venv

🔴 Примітка!
### Інтерпретатор має бути той що ми створили отож комбінацією Ctrl + Shift + P обираємо .venv\Scripts\python.exe. Цей інтерпретатор нам потрібний бо він не є системним. 

### Щоб перейти в серидовище потрібно вписати:
    .venv\Scripts\activate

### Для того щоб вийти з серидовища .venv потрібно вписати:
    deactivate
    
### І для інтеграції fastapi, в серидовищі .venv вписуємо:
    pip install fastapi uvicorn

### Якщо пропонує оновити версію pip, вписуємо:
    python -m pip install --upgrade pip

### Для запуску backend потрібна команда:
    uvicorn main:app --reload

### Для встановлення залежностей потрібно вписати:
    pip install -r requirements.txt

### А для того щоб створити залежності потрібно:
    pip freeze > requirements.txt

🔴 Примітка!
### Всі команди звязані з встановленням чи запуску проекту на python потрібно знаходитись в середивищі .venv, в терміналі має виглядає приблизно так:
    (.venv) PS D:\...\backend>

### Щоб зайти в термінал duckdb, скористаємось командою:
    .\duckdb.exe db\database.duckdb

### uvicorn main:app --reload
### python -m uvicorn main:app --reload
