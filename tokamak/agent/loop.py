"""Agent loop with tool support."""

import json

from loguru import logger

from tokamak.agent.prompts import build_system_prompt
from tokamak.agent.skills import SkillsLoader
from tokamak.agent.tools import ToolRegistry
from tokamak.providers import LLMProvider
from tokamak.session import Session


class AgentLoop:
    """Agent loop with tool calling support."""

    def __init__(
        self,
        provider: LLMProvider,
        tools: ToolRegistry | None = None,
        skills_loader: SkillsLoader | None = None,
        model: str | None = None,
        system_prompt: str | None = None,
        max_history_messages: int = 20,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        max_iterations: int = 10,
        enable_korean_review: bool = True,
        korean_review_model: str | None = None,
    ):
        self.provider = provider
        self.tools = tools
        self.skills_loader = skills_loader
        self.model = model
        self._custom_system_prompt = system_prompt
        self.max_history_messages = max_history_messages
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.max_iterations = max_iterations
        self.enable_korean_review = enable_korean_review
        self.korean_review_model = korean_review_model

    @property
    def system_prompt(self) -> str:
        """Build system prompt with skills summary if available."""
        # Use custom prompt if provided, otherwise build default
        if self._custom_system_prompt:
            return self._custom_system_prompt

        # Build system prompt with skills
        skills_summary = None
        if self.skills_loader:
            skills_summary = self.skills_loader.build_skills_summary()

        return build_system_prompt(skills_summary)

    async def _review_korean_quality(self, content: str) -> str:
        """Review and correct Korean language quality issues.
        
        Args:
            content: Original response text
            
        Returns:
            Reviewed and corrected text, or original if review fails
        """
        if not self.enable_korean_review:
            return content
        
        if not content or len(content) < 10:
            return content
        
        review_prompt = """Review and correct this Discord message for Korean language quality.

CRITICAL CHECKS:

1. **Brand Name Accuracy - HIGHEST PRIORITY**:
   - ✅ ALWAYS use "토카막 네트워크" when referring to Tokamak Network (NOT just "토카막")
   - ❌ NEVER use typos: "토라막", "토큰막", "토까막"
   - ✅ Verify spelling of ALL official names:
     * "토카막 네트워크" (Tokamak Network)
     * "Tokamak Rollup Hub" / "TRH"
     * "GranTON"
     * "Titan"
   - ✅ **Token Symbols - NEVER translate**:
     * ✅ CORRECT: "TON", "WTON", "$TOKAMAK"
     * ❌ WRONG: "톤", "더블유톤", "토카막 토큰"
   - 🚨 Brand name errors are UNACCEPTABLE - double-check every occurrence

2. **Emoji Usage**: Limit to 2-3 emojis per response
   - BAD: `**🔍 핵심 특징**`, `**💼 중앙화 거래소**` (decorative emoji headers)
   - GOOD: `**핵심 특징**`, `🔗 **공식 리소스**` (emoji only for key info like links/warnings)

3. **Terminology Consistency**:
   - BAD: "전직(FT)", "시간제(PT)", "seigniorage 리워드"
   - GOOD: "풀타임" or "상근", "파트타임" or "비상근", "스테이킹 보상"
   - Remove unnecessary English in parentheses: "DAO 후보(Candidate)" → "DAO 후보"

4. **Natural Korean Expressions**:
   - BAD: "보안 기능으로 인해", "L2 ↔ L2 간", "자유롭게 전환 가능"
   - GOOD: "특별한 보안 설계로", "L2 체인끼리 직접", "컨트랙트를 통해 1:1 교환"
   - Omit pronouns naturally rather than literal "그", "그녀", "그것"

5. **Section Header Style**:
   - BAD: Multiple decorative emoji headers throughout response
   - GOOD: Simple bold `**제목**:` or single emoji `🔗 **제목**` for important sections only

6. **Discord Markdown**: Remove unsupported syntax:
   - BAD: `####` headers (Discord doesn't support these)
   - GOOD: Use **bold text** or blank lines for sections

CRITICAL - URL HANDLING:
- Keep URLs EXACTLY as they appear
- DO NOT duplicate or repeat URLs
- DO NOT add extra links
- If you see "🔗 <url> text", keep it as "🔗 <url> text" (single occurrence)

IMPORTANT:
- If the message is in English, return it unchanged
- Only output the corrected message text (no explanations)
- If no corrections needed, return the original text exactly
- Preserve all code blocks
- Focus on fixing terminology and natural Korean flow

Original message:
"""
        
        try:
            messages = [
                {"role": "user", "content": review_prompt + content}
            ]
            
            review_model = self.korean_review_model or self.model
            
            response = await self.provider.chat(
                messages=messages,
                model=review_model,
                max_tokens=self.max_tokens,
                temperature=0.3,  # Lower temperature for consistent corrections
            )
            
            if response.finish_reason == "error" or not response.content:
                logger.warning("Korean review failed, using original")
                return content
            
            reviewed = response.content.strip()
            
            # Sanity check: reviewed text should be similar length
            if len(reviewed) < len(content) * 0.5 or len(reviewed) > len(content) * 2:
                logger.warning("Korean review produced suspicious output, using original")
                return content
            
            # Check for URL duplication
            import re
            original_urls = re.findall(r'https?://[^\s<>]+', content)
            reviewed_urls = re.findall(r'https?://[^\s<>]+', reviewed)
            
            # If reviewed has more URLs than original, likely duplicated
            if len(reviewed_urls) > len(original_urls):
                logger.warning(f"Korean review duplicated URLs ({len(original_urls)} -> {len(reviewed_urls)}), using original")
                return content
            
            logger.debug(f"Korean review applied: {len(content)} -> {len(reviewed)} chars")
            return reviewed
            
        except Exception as e:
            logger.error(f"Korean review failed: {e}")
            return content

    def _detect_korean(self, text: str) -> bool:
        """
        Detect if text contains Korean characters.

        Simple heuristic: checks for Hangul characters (U+AC00 to U+D7AF).
        Returns True if Korean detected, False otherwise.
        """
        for char in text:
            if '\uAC00' <= char <= '\uD7AF':  # Hangul syllables
                return True
        return False

    def _build_messages(self, session: Session, current_message: str) -> list[dict]:
        """Build messages list for LLM call."""
        messages = [{"role": "system", "content": self.system_prompt}]

        # Add history
        history = session.get_history(max_messages=self.max_history_messages)
        if history and history[-1]["role"] == "user" and history[-1]["content"] == current_message:
            history = history[:-1]
        messages.extend(history)

        # Add current message
        messages.append({"role": "user", "content": current_message})
        return messages

    async def run(self, session: Session, message: str, skip_korean_review: bool = False) -> str | None:
        """
        Process a message with tool support.

        Args:
            session: User session
            message: User message
            skip_korean_review: If True, skip Korean review (for English inputs)
        """
        if not message.strip():
            return None

        messages = self._build_messages(session, message)
        tool_definitions = self.tools.get_definitions() if self.tools else None

        logger.debug(f"AgentLoop: {len(messages)} messages, {len(tool_definitions or [])} tools")

        try:
            for iteration in range(self.max_iterations):
                response = await self.provider.chat(
                    messages=messages,
                    tools=tool_definitions,
                    model=self.model,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                )

                if response.finish_reason == "error":
                    logger.error(f"LLM error: {response.content}")
                    return None

                # Handle tool calls
                if response.has_tool_calls and self.tools:
                    # Add assistant message with tool calls
                    assistant_msg = {"role": "assistant", "content": response.content}
                    assistant_msg["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments)
                            }
                        }
                        for tc in response.tool_calls
                    ]
                    messages.append(assistant_msg)

                    # Execute tools and add results
                    for tc in response.tool_calls:
                        logger.debug(f"Executing tool: {tc.name}")
                        result = await self.tools.execute(tc.name, tc.arguments)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": result
                        })

                    continue  # Next iteration

                # No tool calls, return response
                content = response.content
                if content:
                    content = content.strip()

                    # Check for conversation end marker
                    if "===END_CONVERSATION===" in content:
                        logger.info("Conversation end requested by agent")
                        session.end()
                        # Return only the message before the marker
                        content = content.split("===END_CONVERSATION===")[0].strip()
                        return content if content else "대화를 종료합니다. 다시 대화하고 싶으시면 언제든지 말씀해주세요!"

                    # Apply Korean quality review if enabled
                    if not skip_korean_review:
                        content = await self._review_korean_quality(content)
                    else:
                        logger.debug("Skipping Korean review (English input detected)")

                    logger.debug(f"AgentLoop response: {content[:100]}...")
                    return content
                return None

            # Max iterations reached
            logger.warning("Max iterations reached")
            return "죄송합니다, 처리 중 문제가 발생했습니다."

        except Exception as e:
            logger.error(f"AgentLoop error: {e}")
            return None

    async def run_with_retry(
        self,
        session: Session,
        message: str,
        max_retries: int = 1,
        skip_korean_review: bool = False
    ) -> str | None:
        """Process a message with retry on failure."""
        for attempt in range(max_retries + 1):
            result = await self.run(session, message, skip_korean_review=skip_korean_review)
            if result:
                return result
            if attempt < max_retries:
                logger.warning(f"Retry {attempt + 1}/{max_retries}")
        return None
