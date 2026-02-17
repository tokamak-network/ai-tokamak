NEWS_SUMMARY_PROMPT = """You are a cryptocurrency and blockchain translation specialist.

Summarize these news articles in both Korean and English.

Important guidelines:
- Keep technical terms in English (e.g., DeFi, staking, liquidity, Layer 2, rollup, validator, governance, smart contract)
- Do NOT translate or transliterate technical terms - use them as-is
- Preserve original meaning while making it accessible

Focus on:
- Major market movements and price trends
- Regulatory updates
- DeFi, L2, and Ethereum ecosystem news
- Any Tokamak Network related news

News articles:
{news_content}

Respond in this exact format:

## 📰 주요 뉴스
[3-5 bullet points in Korean, each on a new line starting with •]

## 📰 Top News
[3-5 bullet points in English, each on a new line starting with •]

Keep each bullet point concise (1-2 sentences)."""


NEWS_NO_UPDATE_MESSAGE = """## 📰 뉴스 업데이트

새로운 주요 뉴스가 없습니다.

## 📰 News Update

No significant new news at this time."""
