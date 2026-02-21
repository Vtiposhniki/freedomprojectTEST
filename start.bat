@echo off
chcp 65001 >nul

echo 🚀 Поднимаем инфраструктуру (БД, API, Дашборд и NGROK)...
docker-compose up -d --build

echo ⏳ Ждем 15 секунд, пока база данных инициализируется...
timeout /t 15 /nobreak >nul

echo 📥 Загружаем исходные данные из CSV в базу...
docker-compose exec api python -c "from db import load_csv; load_csv()"

echo 🧠 Запускаем AI-анализ и маршрутизацию тикетов (run.py)...
docker-compose exec api python run.py

echo 📊 Собираем аналитику и генерируем отчет (analyze.py)...
docker-compose exec api python analyze.py

echo =======================================================
echo ✅ ПРОЕКТ УСПЕШНО ЗАПУЩЕН!
echo ⚙️  API (FastAPI, локально):      http://localhost:8000/docs
echo 📊 Дашборд (Streamlit, локально): http://localhost:8501
echo =======================================================

echo 🌐 Получаем публичную ссылку Ngrok...
timeout /t 3 /nobreak >nul
docker-compose exec api python -c "import urllib.request, json; try: print('\n✨ ТВОЯ ПУБЛИЧНАЯ ССЫЛКА:', json.loads(urllib.request.urlopen('http://ngrok:4040/api/tunnels').read().decode('utf-8'))['tunnels'][0]['public_url'], '\n'); except Exception: print('\nНе удалось получить ссылку. Зайди на http://localhost:4040\n')"
echo =======================================================
pause