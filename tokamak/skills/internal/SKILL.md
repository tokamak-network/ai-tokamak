---
name: internal
description: "봇 내부 상태 관리. 세션 조회, 봇 상태 확인, 세션 삭제 등."
---

# Internal Bot Management

봇의 내부 상태를 관리합니다. `internal_state` 도구를 사용하여 세션과 봇 상태를 조회합니다.

## 사용 가능한 작업

### 봇 상태 확인

```json
{"action": "get_status"}
```

반환 값:
```json
{
  "success": true,
  "active_sessions": 5,
  "active_conversations": 3,
  "news_feed": "활성"
}
```

### 세션 목록 조회

```json
{"action": "list_sessions", "limit": 10}
```

반환 값:
```json
{
  "success": true,
  "sessions": [
    {"key": "discord:123:456", "message_count": 15, "status": "active"},
    {"key": "discord:789:012", "message_count": 8, "status": "ended"}
  ]
}
```

### 세션 삭제

```json
{"action": "delete_session", "session_key": "discord:123:456"}
```

반환 값:
```json
{
  "success": true,
  "message": "세션이 삭제되었습니다: `discord:123:456`"
}
```

## 세션 키 형식

세션 키는 `discord:{guild_id}:{user_id}` 형식입니다.

## 활용 예시

1. "현재 세션 몇 개야?" → `{"action": "get_status"}`
2. "활성 세션 목록 보여줘" → `{"action": "list_sessions"}`
3. "discord:123:456 세션 삭제해" → `{"action": "delete_session", "session_key": "discord:123:456"}`