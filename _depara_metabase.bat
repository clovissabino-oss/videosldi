@echo off
chcp 65001 >nul
cd /d "%~dp0"
py depara_metabase.py %*
