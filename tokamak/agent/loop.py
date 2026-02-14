"""Agent loop with tool support."""

import json
import re

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
        """Build system prompt with skills summary (no user-message patterns)."""
        return self._get_system_prompt()

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
        
        review_prompt = """Korean quality check. Fix ONLY these issues, return corrected text only:

1. Brand names: "토카막 네트워크" (NOT "토카막" alone). No typos: "토라막", "토큰막" 등
2. Token symbols stay English: TON, WTON, $TOKAMAK (NOT "톤", "더블유톤")
3. Max 2-3 emojis. No decorative emoji headers like "**🔍 제목**"
4. URLs: keep EXACTLY as-is, do NOT duplicate or add extra links
5. Remove trailing spaces at end of lines
6. Fix Korean particle errors (은/는, 이/가, 을/를 based on preceding character)
7. If English, return unchanged. No explanations, just the corrected text.

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
            
            # Check for URL changes (additions, modifications, or deletions)
            original_urls = set(re.findall(r'https?://[^\s<>]+', content))
            reviewed_urls = set(re.findall(r'https?://[^\s<>]+', reviewed))

            if reviewed_urls != original_urls:
                logger.warning(f"Korean review altered URLs, using original")
                return content
            
            logger.debug(f"Korean review applied: {len(content)} -> {len(reviewed)} chars")
            return reviewed
            
        except Exception as e:
            logger.error(f"Korean review failed: {e}")
            return content

    def _detect_korean(self, text: str) -> bool:
        """
        Detect if text contains Korean characters.

        Checks for Hangul syllables (U+AC00-U+D7AF) and Jamo (U+3131-U+318E).
        Returns True if Korean detected, False otherwise.
        """
        for char in text:
            if '\uAC00' <= char <= '\uD7AF':  # Hangul syllables (가-힣)
                return True
            if '\u3131' <= char <= '\u318E':  # Hangul Jamo (ㄱ-ㅎ, ㅏ-ㅣ)
                return True
        return False

    END_MARKER = "===END_CONVERSATION==="

    def _sanitize_input(self, text: str) -> str:
        """Remove conversation end markers from user input to prevent injection."""
        return text.replace(self.END_MARKER, "")

    def _get_system_prompt(self, user_message: str | None = None) -> str:
        """Build system prompt, optionally injecting relevant answer patterns."""
        if self._custom_system_prompt:
            return self._custom_system_prompt

        skills_summary = None
        if self.skills_loader:
            skills_summary = self.skills_loader.build_skills_summary()

        return build_system_prompt(skills_summary, user_message=user_message)

    def _build_messages(self, session: Session, current_message: str) -> list[dict]:
        """Build messages list for LLM call."""
        messages = [{"role": "system", "content": self._get_system_prompt(current_message)}]

        # Add history
        history = session.get_history(max_messages=self.max_history_messages)
        if history and history[-1]["role"] == "user" and history[-1]["content"] == current_message:
            history = history[:-1]
        # Sanitize user messages in history
        for msg in history:
            if msg["role"] == "user":
                msg = {**msg, "content": self._sanitize_input(msg["content"])}
            messages.append(msg)

        # Add current message (sanitized)
        messages.append({"role": "user", "content": self._sanitize_input(current_message)})
        return messages

    async def run(self, session: Session, message: str) -> str | None:
        """
        Process a message with tool support.

        Args:
            session: User session
            message: User message
        """
        if not message.strip():
            return None

        messages = self._build_messages(session, message)
        tool_definitions = self.tools.get_definitions() if self.tools else None

        logger.debug(f"AgentLoop: {len(messages)} messages, {len(tool_definitions or [])} tools")

        try:
            consecutive_tool_errors = 0

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
                    has_error = False
                    for tc in response.tool_calls:
                        logger.info(f"Tool call: {tc.name}({tc.arguments})")
                        result = await self.tools.execute(tc.name, tc.arguments)
                        logger.info(f"Tool result: {tc.name} -> {result[:200]}{'...' if len(result) > 200 else ''}")
                        if '"error"' in result[:50]:
                            has_error = True
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": result
                        })

                    if has_error:
                        consecutive_tool_errors += 1
                    else:
                        consecutive_tool_errors = 0

                    if consecutive_tool_errors >= 3:
                        logger.warning("3 consecutive tool errors, stopping loop")
                        return "죄송합니다, 정보를 가져오는 중 문제가 발생했어요. 잠시 후 다시 시도해주세요.\nSorry, there was an issue retrieving information. Please try again shortly."

                    continue  # Next iteration

                # No tool calls, return response
                content = response.content
                if content:
                    content = content.strip()

                    # Check for conversation end marker
                    if self.END_MARKER in content:
                        logger.info("Conversation end requested by agent")
                        session.end()
                        # Return only the message before the marker
                        content = content.split(self.END_MARKER)[0].strip()
                        return content if content else "대화를 종료합니다. 다시 대화하고 싶으시면 언제든지 말씀해주세요!\nConversation ended. Feel free to mention me anytime to start a new one!"

                    # Apply Korean quality review if output contains Korean
                    if self._detect_korean(content):
                        content = await self._review_korean_quality(content)
                    else:
                        logger.debug("Skipping Korean review (English output)")

                    logger.info(f"AgentLoop response ({len(content)} chars):\n{content}")
                    return content
                return None

            # Max iterations reached
            logger.warning("Max iterations reached")
            return "죄송합니다, 처리 중 문제가 발생했어요. 잠시 후 다시 시도해주세요.\nSorry, something went wrong. Please try again shortly."

        except Exception as e:
            logger.error(f"AgentLoop error: {e}")
            return None

    async def run_with_retry(
        self,
        session: Session,
        message: str,
        max_retries: int = 1,
    ) -> str | None:
        """Process a message with retry on failure."""
        for attempt in range(max_retries + 1):
            result = await self.run(session, message)
            if result:
                return result
            if attempt < max_retries:
                logger.warning(f"Retry {attempt + 1}/{max_retries}")
        return None
