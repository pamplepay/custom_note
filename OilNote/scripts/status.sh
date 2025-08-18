#!/bin/bash

# 프로젝트 루트 디렉토리 설정
PROJECT_ROOT="/home/oilnote/custom_note/OilNote"

# Django 서버 상태 확인
if [ -f "$PROJECT_ROOT/server.pid" ]; then
    PID=$(cat "$PROJECT_ROOT/server.pid")
    if ps -p "$PID" > /dev/null; then
        echo "Django 서버: 실행 중 (PID: $PID)"
    else
        echo "Django 서버: 비정상 종료됨"
        rm "$PROJECT_ROOT/server.pid"
    fi
else
    echo "Django 서버: 중지됨"
fi

# Caddy 시스템 서비스 상태 확인
echo -e "\nCaddy 시스템 서비스 상태:"
sudo systemctl status caddy --no-pager | grep "Active:"

# 접속 정보 표시
echo -e "\n접속 정보:"
echo "Django 관리자: https://oilnote.co.kr/admin"
echo "서비스 접속: https://oilnote.co.kr"
echo "또는: https://www.oilnote.co.kr" 