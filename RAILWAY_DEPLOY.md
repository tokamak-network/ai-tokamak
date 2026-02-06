# Railway 배포 가이드

이 문서는 AI_Tokamak Discord 봇을 Railway에 배포하는 방법을 설명합니다.

## 사전 준비

1. [Railway](https://railway.app) 계정 생성
2. GitHub 저장소에 프로젝트 푸시
3. Discord 봇 토큰 및 OpenRouter API 키 준비

## 배포 단계

### 1. Railway 프로젝트 생성

1. Railway 대시보드에서 "New Project" 클릭
2. "Deploy from GitHub repo" 선택
3. 저장소 선택 및 연결

### 2. 환경 변수 설정

Railway 프로젝트 설정에서 다음 환경 변수를 추가:

```bash
# Discord 설정
DISCORD_TOKEN=your_discord_bot_token_here
MONITOR_CHANNEL_IDS=111111111,222222222  # 쉼표로 구분

# OpenRouter API 키
OPENROUTER_API_KEY=your_openrouter_api_key_here

# Agent 설정 (선택사항)
AGENT_MODEL=qwen3-235b
RESPONSE_PROBABILITY=0.1
```

### 3. config.json 생성 스크립트 추가

Railway에서 config.json을 환경 변수로부터 생성하도록 설정합니다.

`railway.toml`의 startCommand를 다음과 같이 수정:

```toml
[deploy]
startCommand = "python scripts/create_config.py && tokamak run"
```

그리고 `scripts/create_config.py` 파일 생성:

```python
import json
import os

config = {
    "discord": {
        "token": os.environ.get("DISCORD_TOKEN", ""),
        "monitor_channel_ids": [
            int(x.strip())
            for x in os.environ.get("MONITOR_CHANNEL_IDS", "").split(",")
            if x.strip()
        ],
        "allow_guilds": [],
        "response_probability": float(os.environ.get("RESPONSE_PROBABILITY", "0.1")),
        "conversation_timeout_seconds": 300
    },
    "session": {
        "max_messages": 100
    },
    "providers": {
        "openrouter": {
            "api_key": os.environ.get("OPENROUTER_API_KEY", "")
        }
    },
    "agent": {
        "model": os.environ.get("AGENT_MODEL", "qwen3-235b"),
        "enable_korean_review": True,
        "korean_review_model": None
    }
}

with open("config.json", "w") as f:
    json.dump(config, f, indent=2)

print("✓ config.json created from environment variables")
```

### 4. 배포

설정이 완료되면 Railway가 자동으로 빌드 및 배포를 시작합니다.

## 배포 확인

Railway 로그에서 다음 메시지를 확인:

```
✓ config.json created from environment variables
Bot is ready!
Logged in as YourBotName
```

## 문제 해결

### 봇이 시작하지 않는 경우

1. Railway 로그 확인
2. 환경 변수가 올바르게 설정되었는지 확인
3. Discord 토큰이 유효한지 확인

### 채널 모니터링이 작동하지 않는 경우

1. `MONITOR_CHANNEL_IDS`가 올바른 형식인지 확인 (쉼표로 구분된 숫자)
2. 봇이 해당 채널에 접근 권한이 있는지 확인

## 로컬 테스트

Railway에 배포하기 전 로컬에서 테스트:

```bash
# 환경 변수 설정
export DISCORD_TOKEN="your_token"
export MONITOR_CHANNEL_IDS="111111111,222222222"
export OPENROUTER_API_KEY="your_key"

# config.json 생성 및 실행
python scripts/create_config.py
tokamak run
```

## 추가 정보

- Railway는 자동으로 Python 환경을 감지하고 `requirements.txt` 기반으로 의존성 설치
- `Procfile` 또는 `railway.toml`의 startCommand로 시작 명령 정의
- 무료 플랜에서는 월 500시간 실행 가능 (약 20일)
- 배포 시 자동으로 다시 시작되므로 인메모리 세션 데이터는 초기화됨
