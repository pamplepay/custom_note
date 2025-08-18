#!/bin/bash

# 프로젝트 루트 디렉토리 설정
PROJECT_ROOT="/home/oilnote/custom_note/OilNote"

# PID 파일 확인
if [ ! -f "$PROJECT_ROOT/server.pid" ]; then
    echo "서버가 실행 중이 아닙니다."
    exit 0
fi

# PID 읽기
PID=$(cat "$PROJECT_ROOT/server.pid")

# 프로세스 종료
if ps -p "$PID" > /dev/null; then
    echo "서버 프로세스(PID: $PID) 종료 중..."
    kill "$PID"
    sleep 2
    
    # 프로세스가 여전히 실행 중인지 확인
    if ps -p "$PID" > /dev/null; then
        echo "정상 종료 실패. 강제 종료 시도..."
        kill -9 "$PID"
        sleep 1
    fi
    
    if ps -p "$PID" > /dev/null; then
        echo "서버 종료 실패!"
        exit 1
    else
        echo "서버가 성공적으로 종료되었습니다."
    fi
else
    echo "서버 프로세스가 이미 종료되어 있습니다."
fi

# PID 파일 제거
rm -f "$PROJECT_ROOT/server.pid" 