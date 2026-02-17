# Railway 배포 가이드

## 사전 준비

배포 전 아래 항목을 준비하세요.

| 항목 | 발급처 |
|---|---|
| Discord Bot Token | https://discord.com/developers/applications → Bot 탭 → Token |
| OpenRouter API Key | https://openrouter.ai/keys |
| 모니터링 채널 ID | 디스코드 채널 우클릭 → 채널 ID 복사 |
| 서버(길드) ID (선택) | 디스코드 서버 이름 우클릭 → 서버 ID 복사 |

> 채널/서버 ID 복사를 위해 디스코드 **설정** > **고급** > **개발자 모드**를 활성화하세요.

## 배포 순서

1. GitHub에 코드 push
2. [Railway](https://railway.app) 프로젝트 생성 → GitHub 레포 연결
3. **Variables** 탭에서 환경변수 설정 (아래 표 참고)
4. 자동 배포 시작 (이후 push할 때마다 자동 재배포)

## 환경변수

### 필수

| 변수 | 설명 | 예시 |
|---|---|---|
| `DISCORD_TOKEN` | 디스코드 봇 토큰 | `MTIzNDU2Nzg5...` |
| `OPENROUTER_API_KEY` | OpenRouter API 키 | `sk-or-v1-abc...` |
| `MONITOR_CHANNEL_IDS` | 봇이 모니터링할 채널 ID (쉼표 구분) | `123456789,987654321` |

### 선택

| 변수 | 설명 | 기본값 |
|---|---|---|
| `ALLOW_GUILDS` | 봇이 동작할 서버 ID (쉼표 구분). 비어있으면 모든 서버 허용 | _(빈 값 = 모든 서버)_ |
| `AGENT_MODEL` | LLM 모델 식별자 | `qwen3-235b` |
| `OPENROUTER_API_BASE` | API 엔드포인트 URL. 다른 OpenAI 호환 서버(LiteLLM, vLLM 등) 사용 시 설정 | _(OpenRouter 기본값)_ |
| `CONVERSATION_TIMEOUT_SECONDS` | 대화 타임아웃 (초). 마지막 메시지 이후 이 시간이 지나면 대화 종료 | `300` |
| `MAX_MESSAGES` | 세션당 저장할 최대 메시지 수 | `100` |
| `LOG_LEVEL` | 로그 레벨 (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `INFO` |

### 뉴스 피드 (선택)

| 변수 | 설명 | 기본값 |
|---|---|---|
| `NEWS_FEED_ENABLED` | 뉴스 피드 기능 활성화 | `false` |
| `NEWS_FEED_INTERVAL_SECONDS` | 뉴스 수집 주기 (초) | `300` (5분) |
| `NEWS_KOREAN_CHANNEL_ID` | 한국어 요약 전송할 디스코드 채널 ID | _(없음)_ |
| `NEWS_ENGLISH_CHANNEL_ID` | 영어 요약 전송할 디스코드 채널 ID | _(없음)_ |
| `NEWS_SOURCES` | RSS 피드 URL (쉼표 구분) | CoinDesk RSS |
| `NEWS_MAX_PER_FETCH` | 한 번에 처리할 최대 뉴스 수 | `15` |

> 뉴스 피드를 활성화하려면 `NEWS_FEED_ENABLED=true`로 설정하고, 최소 하나의 채널 ID를 지정해야 합니다.

## 동작 방식

```
git push origin main
    ↓
Railway가 push 감지 → Nixpacks 빌드 (Python 3.11)
    ↓
python scripts/create_config.py  (환경변수 → config.json 생성)
    ↓
tokamak run  (봇 시작)
```

- 빌드 설정은 `railway.toml`에 정의되어 있음
- 실패 시 최대 10회 자동 재시작
- 배포/재시작 시 SIGTERM → graceful shutdown 처리됨

## 로그 확인

Railway 대시보드 → **Deployments** → 배포 선택 → **Logs** 탭

정상 시작 시 아래 메시지가 출력됩니다:

```
✓ config.json created successfully from environment variables
INFO     | Starting Tokamak bot...
INFO     | Discord bot logged in as AI_Tokamak#1234
```

디버깅이 필요하면 `LOG_LEVEL`을 `DEBUG`로 변경하세요.

## 로컬 테스트

Railway에 배포하기 전 로컬에서 테스트할 수 있습니다:

```bash
export DISCORD_TOKEN="your_token"
export OPENROUTER_API_KEY="your_key"
export MONITOR_CHANNEL_IDS="123456789"

python scripts/create_config.py && tokamak run
```

## 문제 해결

| 증상 | 확인 사항 |
|---|---|
| 봇이 시작하지 않음 | Railway 로그에서 환경변수 누락 에러 확인 |
| 채널 모니터링 안 됨 | `MONITOR_CHANNEL_IDS` 형식 확인, 봇의 채널 접근 권한 확인 |
| 특정 서버에서 응답 안 함 | `ALLOW_GUILDS`에 해당 서버 ID가 포함되어 있는지 확인 |
| 재배포 후 대화 초기화 | 정상 동작 (세션이 인메모리 저장이므로 재배포 시 초기화됨) |

## 참고 사항

- `config.json`은 `.gitignore`에 포함되어 있어 GitHub에 올라가지 않습니다
- API 키는 Railway 환경변수에만 저장되므로 코드에 노출되지 않습니다
- 세션 데이터는 인메모리 저장이므로 재배포 시 대화 히스토리가 초기화됩니다
