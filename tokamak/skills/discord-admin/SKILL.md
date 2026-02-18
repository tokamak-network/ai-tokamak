---
name: discord-admin
description: "Discord 서버 관리 기능. 사용자 타임아웃, 채널 메시지 전송, 사용자/채널 검색 등."
metadata: {"nanobot":{"requires":{"env":["DISCORD_TOKEN"]}}}
---

# Discord Admin Skill

Discord API를 사용하여 서버 관리 작업을 수행합니다.

## 도구 구분

- **web_fetch**: GET 요청용 (데이터 조회)
- **web_post**: POST/PUT/PATCH/DELETE 요청용 (데이터 수정)

## 인증

모든 Discord API 호출에 `auth_provider: "discord"`를 설정하면 Bot 토큰이 자동으로 주입됩니다.

## Base URL

```
https://discord.com/api/v10
```

## Guild ID

서버 관리 작업에는 Guild ID가 필요합니다. System Prompt에 포함되어 있습니다.

---

## 사용자 검색

### 이름으로 멤버 검색 (권장)

사용자 이름, 닉네임의 일부로 검색합니다.

```json
{
  "name": "web_fetch",
  "arguments": {
    "url": "https://discord.com/api/v10/guilds/{guild_id}/members/search",
    "params": {"query": "홍길동", "limit": "5"},
    "auth_provider": "discord"
  }
}
```

### ID로 멤버 조회

```json
{
  "name": "web_fetch",
  "arguments": {
    "url": "https://discord.com/api/v10/guilds/{guild_id}/members/{user_id}",
    "auth_provider": "discord"
  }
}
```

---

## 타임아웃

### 타임아웃 설정

사용자의 `communication_disabled_until` 필드를 ISO8601 형식으로 설정합니다.

```json
{
  "name": "web_post",
  "arguments": {
    "url": "https://discord.com/api/v10/guilds/{guild_id}/members/{user_id}",
    "method": "PATCH",
    "body": {"communication_disabled_until": "2024-01-01T12:00:00.000Z"},
    "auth_provider": "discord"
  }
}
```

**타임아웃 시간 계산:**
- 현재 시간 + N분을 ISO8601 포맷으로 변환
- 최대 7일 (10080분)

### 타임아웃 해제

```json
{
  "name": "web_post",
  "arguments": {
    "url": "https://discord.com/api/v10/guilds/{guild_id}/members/{user_id}",
    "method": "PATCH",
    "body": {"communication_disabled_until": null},
    "auth_provider": "discord"
  }
}
```

---

## 채널 작업

### 채널 목록 조회

```json
{
  "name": "web_fetch",
  "arguments": {
    "url": "https://discord.com/api/v10/guilds/{guild_id}/channels",
    "auth_provider": "discord"
  }
}
```

### 채널에 메시지 전송

```json
{
  "name": "web_post",
  "arguments": {
    "url": "https://discord.com/api/v10/channels/{channel_id}/messages",
    "method": "POST",
    "body": {"content": "메시지 내용"},
    "auth_provider": "discord"
  }
}
```

### Embed 메시지

```json
{
  "name": "web_post",
  "arguments": {
    "url": "https://discord.com/api/v10/channels/{channel_id}/messages",
    "method": "POST",
    "body": {"embeds": [{"title": "제목", "description": "설명", "color": 3447003}]},
    "auth_provider": "discord"
  }
}
```

---

## 사용 예시

### "홍길동 사용자 1시간 타임아웃"

1. 사용자 검색:
```json
{
  "name": "web_fetch",
  "arguments": {
    "url": "https://discord.com/api/v10/guilds/{guild_id}/members/search",
    "params": {"query": "홍길동", "limit": "5"},
    "auth_provider": "discord"
  }
}
```

2. 검색 결과에서 user_id 확인

3. 타임아웃 설정 (현재 + 60분):
```json
{
  "name": "web_post",
  "arguments": {
    "url": "https://discord.com/api/v10/guilds/{guild_id}/members/{user_id}",
    "method": "PATCH",
    "body": {"communication_disabled_until": "2024-01-15T13:00:00.000Z"},
    "auth_provider": "discord"
  }
}
```

### "공지 채널에 메시지 보내기"

1. 채널 목록에서 channel_id 확인:
```json
{
  "name": "web_fetch",
  "arguments": {
    "url": "https://discord.com/api/v10/guilds/{guild_id}/channels",
    "auth_provider": "discord"
  }
}
```

2. 메시지 전송:
```json
{
  "name": "web_post",
  "arguments": {
    "url": "https://discord.com/api/v10/channels/{channel_id}/messages",
    "method": "POST",
    "body": {"content": "공지사항 내용입니다."},
    "auth_provider": "discord"
  }
}
```

---

## 주의사항

- 타임아웃은 봇이 대상 사용자보다 높은 권한을 가질 때만 작동합니다
- Rate Limit: Discord API는 요청 제한이 있습니다. 429 응답 시 `retry_after`를 확인하세요
- 권한: 봇이 필요한 권한(Manage Roles, Moderate Members 등)을 가졌는지 확인하세요

## 전체 멤버 목록 주의

`/guilds/{guild_id}/members` (전체 목록) API는 Discord Developer Portal에서 "Server Members Intent"가 활성화되어야만 작동합니다.

활성화되지 않은 경우 403 Forbidden (code 40333) 에러가 발생합니다. 특정 사용자 검색 시 `members/search` API를 사용하세요.