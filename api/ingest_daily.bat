@echo off
cd /d C:\Users\dayshawn\Desktop\SportAppV2\api

echo [%date% %time%] Starting daily ingest >> logs\ingest_daily.log

echo [%date% %time%] STEP START livetennis >> logs\ingest_daily.log
.venv\Scripts\python -m app.ingest.livetennis --days-back 1 --days-ahead 1 >> logs\ingest_daily.log 2>&1
echo [%date% %time%] STEP END livetennis >> logs\ingest_daily.log

echo [%date% %time%] STEP START prizepicks >> logs\ingest_daily.log
.venv\Scripts\python -m app.ingest.prizepicks >> logs\ingest_daily.log 2>&1
echo [%date% %time%] STEP END prizepicks >> logs\ingest_daily.log

echo [%date% %time%] STEP START odds_api >> logs\ingest_daily.log
.venv\Scripts\python -m app.ingest.odds_api >> logs\ingest_daily.log 2>&1
echo [%date% %time%] STEP END odds_api >> logs\ingest_daily.log

echo [%date% %time%] STEP START player_stats >> logs\ingest_daily.log
.venv\Scripts\python -m app.ingest.player_stats --today-only --match-days-back 0 --match-days-ahead 1 --skip-computed-today >> logs\ingest_daily.log 2>&1
echo [%date% %time%] STEP END player_stats >> logs\ingest_daily.log

echo [%date% %time%] Done >> logs\ingest_daily.log
