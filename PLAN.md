# AI_Tokamak - 디스코드 블록체인 뉴스봇 MVP 계획

## 개요
nanobot 프로젝트의 핵심 컴포넌트를 마이그레이션하여 디스코드 기반 블록체인/암호화폐 뉴스봇을 개발합니다.

## 핵심 기능
1. **채널 모니터링**: 지정 채널의 모든 메시지 수신 (멘션 불필요)
2. **사용자별 컨텍스트**: 사용자별 대화 기록 관리 및 활용
3. **랜덤 응답**: 확률 기반으로 응답 여부 결정 (자연스러운 대화 흐름)
4. **RSS 크롤링**: 블록체인/암호화폐 뉴스 주기적 수집
5. **자동 포스팅**: 지정 채널에 LLM 요약과 함께 뉴스 공유

---

## 프로젝트 구조

```
ai-tokamak/
├── pyproject.toml
├── config.example.json
├── .gitignore
├── data/                        # 런타임 데이터 (gitignore)
│   └── posted.json              # 게시된 뉴스 ID 저장
├── tokamak/
│   ├── __init__.py
│   ├── __main__.py              # CLI 진입점 (Typer 직접 구현)
│   │
│   ├── config/
│   │   ├── schema.py            # Pydantic 설정 스키마
│   │   └── loader.py            # 설정 로더
│   │
│   ├── bus/
│   │   ├── queue.py             # MessageBus (nanobot 복사)
│   │   └── events.py            # InboundMessage, OutboundMessage
│   │
│   ├── providers/
│   │   ├── base.py              # LLMProvider 추상 클래스
│   │   └── litellm_provider.py  # LiteLLM 구현
│   │
│   ├── agent/
│   │   ├── loop.py              # AgentLoop (간소화, 시스템 프롬프트 포함)
│   │   └── tools/
│   │       ├── __init__.py      # Tool, ToolRegistry export
│   │       ├── base.py          # Tool 추상 클래스
│   │       ├── registry.py      # ToolRegistry
│   │       ├── message.py       # MessageTool
│   │       └── web.py           # WebSearchTool, WebFetchTool (선택)
│   │
│   ├── channels/
│   │   ├── base.py              # BaseChannel (nanobot 복사)
│   │   └── discord.py           # DiscordChannel (신규)
│   │
│   ├── feeds/
│   │   ├── fetcher.py           # RSS 크롤러 + 중복 체크 (신규)
│   │   ├── summarizer.py        # LLM 요약 (신규)
│   │   └── sources.py           # 피드 소스 정의
│   │
│   ├── cron/
│   │   ├── service.py           # CronService (nanobot 복사)
│   │   └── types.py             # CronJob 타입
│   │
│   └── session/
│       └── manager.py           # SessionManager (메모리 기반)
```

---

## 마이그레이션 대상 (nanobot → tokamak)

### 그대로 복사
| 소스 파일 | 대상 | 비고 |
|-----------|------|------|
| `nanobot/bus/queue.py` | `tokamak/bus/queue.py` | import 경로만 변경 |
| `nanobot/bus/events.py` | `tokamak/bus/events.py` | 그대로 |
| `nanobot/channels/base.py` | `tokamak/channels/base.py` | import 경로만 변경 |
| `nanobot/cron/service.py` | `tokamak/cron/service.py` | import 경로만 변경 |
| `nanobot/cron/types.py` | `tokamak/cron/types.py` | 그대로 |
| `nanobot/providers/base.py` | `tokamak/providers/base.py` | 그대로 |
| `nanobot/providers/litellm_provider.py` | `tokamak/providers/litellm_provider.py` | import 경로만 변경 |
| `nanobot/agent/tools/base.py` | `tokamak/agent/tools/base.py` | 그대로 |
| `nanobot/agent/tools/registry.py` | `tokamak/agent/tools/registry.py` | import 경로만 변경 |
| `nanobot/agent/tools/message.py` | `tokamak/agent/tools/message.py` | import 경로만 변경 |

### 선택적 마이그레이션
| 소스 파일 | 대상 | 비고 |
|-----------|------|------|
| `nanobot/agent/tools/web.py` | `tokamak/agent/tools/web.py` | 웹 검색/크롤링 필요시 |

### 마이그레이션 제외
| 소스 파일 | 제외 사유 |
|-----------|-----------|
| `nanobot/agent/tools/filesystem.py` | 뉴스봇에서 파일 조작 불필요 |
| `nanobot/agent/tools/shell.py` | 뉴스봇에서 쉘 명령 불필요 |
| `nanobot/agent/tools/spawn.py` | 서브에이전트 기능 불필요 |

### 간소화하여 복사
| 소스 파일 | 변경 사항 |
|-----------|-----------|
| `nanobot/agent/loop.py` | 도구 시스템 제거, LLM 호출만 유지, 시스템 프롬프트 내장 |
| `nanobot/session/manager.py` | 메모리 기반으로 단순화 (파일 저장 제거) |
| `nanobot/config/schema.py` | Discord/Feeds 설정으로 대체 |

> **참고**: `nanobot/agent/context.py`는 마이그레이션하지 않음. 시스템 프롬프트는 `loop.py`에 직접 정의.

---

## 신규 개발 컴포넌트

### 1. DiscordChannel (`tokamak/channels/discord.py`)
```python
class DiscordChannel(BaseChannel):
    name = "discord"

    # 활성 대화 상태 관리
    # key: user_id, value: last_message_timestamp
    active_conversations: dict[str, float] = {}

    async def start(self):
        # discord.py Client 초기화
        # on_message 이벤트: 모든 메시지 수신 (모니터링 모드)
        # 봇 자신의 메시지는 무시

    async def _on_message(self, message):
        # 1. 봇 메시지 필터링
        # 2. 모니터링 채널 확인
        # 3. should_respond() 호출 - 대화 시작/지속 결정
        # 4. 응답 시 _handle_message() 호출 + 활성 대화 갱신
        # 5. 응답 안 해도 메시지 기록 (컨텍스트용)

    def should_respond(self, user_id: str, is_mention: bool) -> bool:
        """대화 시작/지속 여부 결정 + 타임스탬프 갱신"""

        # 1. 활성 대화 중인 사용자인지 확인
        if user_id in self.active_conversations:
            last_time = self.active_conversations[user_id]
            if time.time() - last_time < CONVERSATION_TIMEOUT:
                # 아직 타임아웃 안 됨 → 대화 지속 + 타임스탬프 갱신
                self.active_conversations[user_id] = time.time()  # ← 핵심!
                return True
            else:
                # 타임아웃 → 대화 종료
                del self.active_conversations[user_id]

        # 2. 멘션이면 항상 대화 시작
        if is_mention:
            self.active_conversations[user_id] = time.time()
            return True

        # 3. 랜덤 확률로 대화 시작 결정
        if random.random() < self.config.response_probability:
            self.active_conversations[user_id] = time.time()
            return True

        return False

    async def send(self, msg: OutboundMessage):
        # 일반 메시지 또는 Embed 전송

    async def send_news_embed(self, news: NewsItem, summary: str):
        # 뉴스용 Embed 포맷 (제목, 요약, 링크, 소스)
```

### 2. RSS 크롤러 (`tokamak/feeds/fetcher.py`)
```python
@dataclass
class NewsItem:
    id: str           # URL 해시
    title: str
    summary: str      # 원본 요약
    url: str
    source: str
    published: datetime

class FeedFetcher:
    """RSS 피드 수집 및 중복 관리

    중복 체크는 data/posted.json 파일로 관리:
    - 봇 재시작 후에도 같은 뉴스 재게시 방지
    - JSON 형식: {"posted_ids": ["id1", "id2", ...], "last_updated": "..."}
    """

    def __init__(self, data_dir: Path = Path("data")):
        self.posted_file = data_dir / "posted.json"
        self._posted_ids: set[str] = self._load_posted_ids()

    def _load_posted_ids(self) -> set[str]:
        """저장된 게시 ID 로드 (파일 없으면 빈 set)"""

    def _save_posted_ids(self) -> None:
        """게시 ID를 JSON 파일로 저장"""

    async def fetch_all(self) -> list[NewsItem]:
        """모든 소스에서 뉴스 수집"""

    async def get_new_items(self) -> list[NewsItem]:
        """중복 제외한 새 뉴스만 반환"""
        items = await self.fetch_all()
        return [item for item in items if item.id not in self._posted_ids]

    def mark_posted(self, item_id: str) -> None:
        """게시 완료 표시 및 파일 저장"""
        self._posted_ids.add(item_id)
        self._save_posted_ids()
```

### 3. LLM 요약기 (`tokamak/feeds/summarizer.py`)
```python
class NewsSummarizer:
    async def summarize(self, news: NewsItem) -> str:
        # LLM으로 뉴스 요약 (한국어, 2-3문장)
```

### 4. 설정 스키마 (`tokamak/config/schema.py`)
```python
class DiscordConfig(BaseModel):
    token: str
    news_channel_id: int           # 뉴스 포스팅 채널
    monitor_channel_ids: list[int] # 대화 모니터링 채널들
    allow_guilds: list[int] = []
    response_probability: float = 0.1  # 랜덤 대화 시작 확률 (10%)
    conversation_timeout_seconds: int = 300  # 대화 타임아웃 (5분)

class FeedsConfig(BaseModel):
    sources: list[str]
    post_interval_minutes: int = 30
    max_posts_per_cycle: int = 5

class SessionConfig(BaseModel):
    max_messages: int = 100  # 사용자별 최대 메시지 저장 수량

class Config(BaseSettings):
    discord: DiscordConfig
    session: SessionConfig
    feeds: FeedsConfig
    providers: ProvidersConfig
```

### 5. 사용자별 대화 기록 관리 (Session)

> **MVP 저장소 전략**: 메모리 기반 (봇 재시작 시 세션 초기화)
> - 단순함 우선, 파일/DB 저장은 필요시 추가
> - asyncio 단일 스레드이므로 동시성 이슈 없음

```python
# 세션 키 형식: discord:{guild_id}:{user_id}
# 예: discord:123456789:987654321

# SessionManager 활용 (nanobot에서 복사 + 수정)
session = session_manager.get_or_create(f"discord:{guild_id}:{user_id}")

# === 메시지 저장 (사용자 + 봇 모두) ===

# 1. 사용자 메시지 저장
session.add_message(role="user", content="사용자가 보낸 메시지")

# 2. 봇 응답 저장
session.add_message(role="assistant", content="봇이 응답한 메시지")

# 3. 세션 영속화
session_manager.save(session)

# === 과거 대화 조회 ===
# LLM 호출 시 컨텍스트로 전달
history = session.get_history(max_messages=20)
# 결과: [
#   {"role": "user", "content": "이전 질문"},
#   {"role": "assistant", "content": "이전 답변"},
#   {"role": "user", "content": "최근 질문"},
#   ...
# ]
```

### 6. 세션 메시지 수량 제한 (Rolling Window)
```python
class Session:
    MAX_MESSAGES = 100  # 설정 가능 (config.session.maxMessages)

    def add_message(self, role: str, content: str, **kwargs):
        msg = {"role": role, "content": content, "timestamp": ..., **kwargs}
        self.messages.append(msg)

        # 최대 수량 초과 시 가장 오래된 메시지 제거
        if len(self.messages) > self.MAX_MESSAGES:
            self.messages = self.messages[-self.MAX_MESSAGES:]

        self.updated_at = datetime.now()
```

**설정 예시 (config.json):**
```json
{
  "session": {
    "max_messages": 100
  }
}
```

**동작:**
- 새 메시지 추가 시 `MAX_MESSAGES` 초과하면 가장 오래된 메시지부터 제거
- FIFO (First In, First Out) 방식
- 저장 시 자동으로 trim됨

**중요**: 응답 여부와 관계없이 모든 사용자 메시지를 저장합니다.
- 응답 O → 사용자 메시지 저장 + LLM 호출 + 봇 응답 저장
- 응답 X → 사용자 메시지만 저장 (추후 컨텍스트로 활용)

### 7. 도구 시스템 (`tokamak/agent/tools/`)

#### 핵심 구조 (nanobot에서 복사)
```python
# base.py - Tool 추상 클래스
class Tool(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]: ...

    @abstractmethod
    async def execute(self, **kwargs: Any) -> str: ...

    def to_schema(self) -> dict[str, Any]:
        """OpenAI function schema 형식으로 변환"""

# registry.py - ToolRegistry
class ToolRegistry:
    def register(self, tool: Tool) -> None
    def get(self, name: str) -> Tool | None
    def get_definitions(self) -> list[dict[str, Any]]  # LLM에 전달
    async def execute(self, name: str, params: dict) -> str
```

#### MessageTool (nanobot에서 복사)
```python
class MessageTool(Tool):
    name = "message"
    description = "Send a message to the user."

    def set_context(self, channel: str, chat_id: str) -> None:
        """현재 메시지 컨텍스트 설정 (DiscordChannel에서 호출)"""

    async def execute(self, content: str, **kwargs) -> str:
        """OutboundMessage 생성 및 전송"""
```

#### 도구 활용 흐름
```
사용자 메시지 수신
    │
    ▼
DiscordChannel._on_message()
    │
    ├─ MessageTool.set_context(channel="discord", chat_id=user_id)
    │
    ▼
AgentLoop.run()
    │
    ├─ ToolRegistry.get_definitions() → LLM에 도구 목록 전달
    │
    ▼
LLM 응답 (tool_calls 포함 가능)
    │
    ├─ tool_calls 있으면 → ToolRegistry.execute() 호출
    │     └─ MessageTool.execute() → OutboundMessage → Discord 전송
    │
    └─ tool_calls 없으면 → 일반 텍스트 응답
```

#### MVP에서의 도구 사용
뉴스봇 MVP에서는 도구 시스템을 **최소한으로** 사용합니다:
- **message**: 메시지 전송 (필수)
- **web_search/web_fetch**: 추후 뉴스 상세 정보 검색용 (선택)

LLM이 도구를 호출하지 않고 직접 텍스트로 응답해도 됩니다.
AgentLoop에서 응답 텍스트를 추출하여 Discord로 전송합니다.

---

## 데이터 흐름

### 대화 모니터링 흐름
```
Discord 채널 메시지 (user_id, content, is_mention)
    │
    ▼
사용자 세션 로드 (discord:guild:user)
    │
    ▼
사용자 메시지 저장 (role="user") ←── 항상 저장
    │
    ▼
should_respond(user_id, is_mention)
    │
    ├─ [활성 대화 중 + 타임아웃 전]
    │     → 타임스탬프 갱신 ←── 핵심! 대화 지속 시간 연장
    │     → 대화 지속 ─────────────────────────────┐
    │                                              │
    ├─ [활성 대화 중 + 타임아웃]                   │
    │     → 대화 종료 (active_conversations에서 삭제)
    │                                              │
    ├─ [멘션]                                      │
    │     → 타임스탬프 설정 (대화 시작) ───────────┤
    │                                              │
    ├─ [랜덤 확률 당첨]                            │
    │     → 타임스탬프 설정 (대화 시작) ───────────┤
    │                                              │
    └─ [응답 안 함] → 세션 저장 후 종료 (메시지는 이미 저장됨)
                                                   │
    ┌──────────────────────────────────────────────┘
    ▼
과거 대화 기록 조회 (session.get_history)
    → MessageBus 발행
    → AgentLoop → LLM (사용자+봇 히스토리 포함)
    → 봇 응답 저장 (role="assistant")
    → 세션 저장
    → MessageBus → Discord 응답 전송
```

### 자동 포스팅 흐름
```
CronService (30분) → FeedFetcher.get_new_items() → NewsSummarizer → DiscordChannel.send_news_embed()
```

---

## 설정 파일 예시 (`config.json`)
```json
{
  "discord": {
    "token": "YOUR_BOT_TOKEN",
    "news_channel_id": 123456789,
    "monitor_channel_ids": [111111111, 222222222],
    "allow_guilds": [],
    "response_probability": 0.1,
    "conversation_timeout_seconds": 300
  },
  "session": {
    "max_messages": 100
  },
  "feeds": {
    "sources": [
      "https://www.coindesk.com/arc/outboundfeeds/rss/",
      "https://cointelegraph.com/rss"
    ],
    "post_interval_minutes": 30,
    "max_posts_per_cycle": 5
  },
  "providers": {
    "openrouter": {
      "api_key": "sk-or-xxx"
    }
  },
  "agent": {
    "model": "anthropic/claude-sonnet-4"
  }
}
```

> **참고**: JSON 키는 Python snake_case와 일치시켜 Pydantic alias 없이 직접 매핑.

---

## 의존성 (`pyproject.toml`)
```toml
dependencies = [
    "discord.py>=2.0.0",       # Discord API
    "litellm>=1.0.0",          # LLM 통합
    "pydantic>=2.0.0",         # 설정
    "pydantic-settings>=2.0.0",
    "loguru>=0.7.0",           # 로깅
    "croniter>=2.0.0",         # 스케줄링
    "httpx>=0.25.0",           # HTTP
    "feedparser>=6.0.0",       # RSS 파싱
    "typer>=0.9.0",            # CLI
    "rich>=13.0.0",
]

# 선택적 의존성 (web.py 도구 사용시)
[project.optional-dependencies]
web-tools = [
    "readability-lxml>=0.8.0", # WebFetchTool용 HTML → 텍스트 변환
]
```

**환경 변수 (선택적 도구용):**
- `BRAVE_API_KEY`: WebSearchTool 사용시 필요 (Brave Search API)

---

## 구현 순서

### Phase 1: 프로젝트 셋업
- [ ] 프로젝트 디렉토리 및 pyproject.toml 생성
- [ ] .gitignore 생성 (config.json, data/, __pycache__, .venv 등)
- [ ] config.example.json 생성
- [ ] data/ 디렉토리 생성
- [ ] nanobot에서 핵심 컴포넌트 복사 (bus, cron, providers, channels/base)
- [ ] nanobot에서 도구 시스템 복사 (agent/tools/base, registry, message)
- [ ] import 경로 수정 (nanobot → tokamak)

### Phase 2: 설정 시스템
- [ ] config/schema.py - Discord, Feeds 설정 정의
- [ ] config/loader.py - JSON 로더

### Phase 3: Discord 채널 + 세션 관리
- [ ] channels/discord.py - DiscordChannel 구현
- [ ] 모니터링 채널 메시지 수신
- [ ] should_respond() 확률 기반 응답 결정
- [ ] 사용자별 세션 키 생성 (discord:guild:user)
- [ ] session/manager.py - 사용자별 컨텍스트 저장/로드
- [ ] OutboundMessage → 디스코드 전송

### Phase 4: RSS 크롤러
- [ ] feeds/sources.py - 기본 소스 정의
- [ ] feeds/fetcher.py - RSS 수집 및 중복 체크
- [ ] data/posted.json 저장/로드 로직 구현
- [ ] feeds/summarizer.py - LLM 요약

### Phase 5: 에이전트 루프
- [ ] agent/loop.py - 간소화된 AgentLoop (시스템 프롬프트 내장)

### Phase 6: 통합 및 에러 처리
- [ ] CronService + FeedFetcher 연동
- [ ] __main__.py에 CLI 명령어 구현 (run, test-feed, test-discord)
- [ ] 기본 에러 처리:
  - Discord 연결 끊김 → discord.py 자동 재연결 활용
  - LLM API 실패 → 1회 재시도 후 로깅
  - RSS 파싱 실패 → 해당 소스 스킵, 로깅

---

## 설계 결정 사항

### 저장소 전략
| 데이터 | 저장소 | 사유 |
|--------|--------|------|
| 사용자 세션 | 메모리 | MVP 단순화. 재시작 시 초기화 허용 |
| 게시된 뉴스 ID | JSON 파일 (`data/posted.json`) | 재시작 후에도 중복 방지 필요 |

### 에러 처리 전략
| 상황 | 대응 |
|------|------|
| Discord 연결 끊김 | discord.py 내장 자동 재연결 |
| LLM API 실패 | 1회 재시도, 실패 시 로깅 후 스킵 |
| RSS 파싱 실패 | 해당 소스 스킵, 로깅 |
| 뉴스 요약 실패 | 원본 요약 사용 (LLM 요약 스킵) |

### Rate Limiting (MVP에서는 최소한으로)
- **Discord**: discord.py 내장 rate limiter 사용
- **LLM API**: 별도 제한 없음 (대화량 적을 것으로 예상)
- **RSS 크롤링**: `post_interval_minutes` 설정으로 간접 제어

### 동시성
- asyncio 단일 스레드 환경이므로 `active_conversations` dict 접근 시 race condition 없음

---

## 검증 방법

1. **Discord 연결 테스트**: `tokamak test-discord` - 봇 로그인 및 테스트 메시지
2. **RSS 크롤링 테스트**: `tokamak test-feed` - 피드 수집 및 파싱 확인
3. **멘션 응답 테스트**: @봇 멘션 → 항상 대화 시작
4. **랜덤 응답 테스트**: 일반 메시지 여러 개 → 확률적 대화 시작
5. **대화 지속 테스트**: 대화 시작 후 멘션 없이 메시지 → 계속 응답
6. **타임아웃 테스트**: 5분 대기 후 메시지 → 응답 없음 (활성 대화 종료)
7. **컨텍스트 테스트**: 같은 사용자와 여러 번 대화 → 과거 대화 참조 확인
8. **자동 포스팅 테스트**: `tokamak run` 실행 후 30분 대기 또는 수동 트리거

---

## 핵심 파일 (구현 시 참조)

- `[NANOBOT_PATH]/nanobot/bus/queue.py` - MessageBus
- `[NANOBOT_PATH]/nanobot/channels/base.py` - BaseChannel
- `[NANOBOT_PATH]/nanobot/channels/telegram.py` - 채널 구현 패턴 참조
- `[NANOBOT_PATH]/nanobot/cron/service.py` - CronService
- `[NANOBOT_PATH]/nanobot/agent/loop.py` - AgentLoop 참조
- `[NANOBOT_PATH]/nanobot/providers/litellm_provider.py` - LLM 연동
- `[NANOBOT_PATH]/nanobot/agent/tools/base.py` - Tool 추상 클래스
- `[NANOBOT_PATH]/nanobot/agent/tools/registry.py` - ToolRegistry
- `[NANOBOT_PATH]/nanobot/agent/tools/message.py` - MessageTool
- `[NANOBOT_PATH]/nanobot/agent/tools/web.py` - WebSearchTool, WebFetchTool (선택)
