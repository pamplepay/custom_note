#!/bin/bash

# 프로젝트 루트 디렉토리 설정
PROJECT_ROOT="/home/oilnote/custom_note/OilNote"

# 서버 PID 파일
PID_FILE="$PROJECT_ROOT/server.pid"

# 로그 디렉토리 생성
mkdir -p "$PROJECT_ROOT/logs"

# 이미 실행 중인 서버가 있는지 확인
if [ -f "$PID_FILE" ]; then
    if ps -p $(cat $PID_FILE) > /dev/null 2>&1; then
        echo "서버가 이미 실행 중입니다. (PID: $(cat $PID_FILE))"
        exit 1
    else
        rm -f $PID_FILE
    fi
fi

# Django collectstatic 실행
cd $PROJECT_ROOT
python3 manage.py collectstatic --noinput

# 서버 시작
nohup python3 manage.py runserver 0.0.0.0:8000 > "$PROJECT_ROOT/logs/server.log" 2>&1 & echo $! > $PID_FILE

# 실행 확인
sleep 2
if [ -f "$PID_FILE" ]; then
    echo "서버가 성공적으로 시작되었습니다. (PID: $(cat $PID_FILE))"
    echo "서비스 접근: https://oilnote.co.kr"
else
    echo "서버 시작 실패"
    exit 1
fi
