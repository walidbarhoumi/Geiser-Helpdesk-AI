
@echo off
cd /d "C:\Users\bwali\Documents\geiser\frontend"
start "GEISER Frontend" cmd /k "npm.cmd run dev -- --host 127.0.0.1"
timeout /t 5 /nobreak >nul
call npm.cmd run tauri:dev
