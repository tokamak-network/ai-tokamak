"""Tests for system prompt building and pattern matching."""

from tokamak.agent.prompts import (
    build_system_prompt,
    get_all_patterns,
    get_matching_patterns,
    ANSWER_PATTERNS,
)


class TestGetMatchingPatterns:
    """Tests for keyword-based pattern matching."""

    def test_returns_matching_pattern_for_korean_keyword(self):
        result = get_matching_patterns("스테이킹 방법 알려주세요")
        assert "스테이킹" in result
        assert "COPY THIS ANSWER EXACTLY" in result

    def test_returns_matching_pattern_for_english_keyword(self):
        result = get_matching_patterns("What is Tokamak Network?")
        assert "tokamak" in result.lower() or "Tokamak" in result

    def test_tokamak_alone_does_not_match_intro_pattern(self):
        """P0-1: '토카막' alone should NOT trigger the intro pattern."""
        result = get_matching_patterns("토카막 스테이킹 방법 알려주세요")
        # Should match staking pattern, but NOT the intro "뭔가요" pattern
        assert "스테이킹 방법" in result
        assert "토카막 네트워크가 뭔가요" not in result

    def test_specific_intro_keywords_still_match(self):
        """P0-1: Specific intro questions should still match."""
        assert get_matching_patterns("토카막이 뭐예요?") != ""
        assert get_matching_patterns("토카막 네트워크가 뭔가요?") != ""
        assert get_matching_patterns("What is Tokamak Network?") != ""

    def test_returns_empty_for_unmatched_keywords(self):
        result = get_matching_patterns("오늘 날씨 어때요?")
        assert result == ""

    def test_returns_multiple_patterns_for_multiple_keywords(self):
        # "거래" matches DEX pattern, "구매" matches buy pattern
        result = get_matching_patterns("TON 구매하고 DEX에서 거래하고 싶어요")
        assert result.count("COPY THIS ANSWER EXACTLY") >= 2

    def test_case_insensitive_matching(self):
        result_lower = get_matching_patterns("staking")
        result_upper = get_matching_patterns("STAKING")
        assert result_lower == result_upper


class TestGetAllPatterns:
    """Tests for get_all_patterns."""

    def test_returns_all_patterns(self):
        result = get_all_patterns()
        # Should contain content from every pattern
        for pattern in ANSWER_PATTERNS:
            # Each pattern's content should be in the result
            assert pattern["content"] in result

    def test_returns_more_than_matching(self):
        matched = get_matching_patterns("스테이킹")
        all_patterns = get_all_patterns()
        assert len(all_patterns) > len(matched)


class TestBuildSystemPrompt:
    """Tests for build_system_prompt."""

    def test_base_prompt_contains_identity(self):
        result = build_system_prompt()
        assert "AI_Tokamak" in result

    def test_base_prompt_contains_knowledge(self):
        result = build_system_prompt()
        assert "Tokamak Network Knowledge Base" in result

    def test_without_user_message_has_no_answer_patterns_section(self):
        result = build_system_prompt()
        assert "Answer Patterns (for this question)" not in result

    def test_with_user_message_injects_matching_patterns(self):
        result = build_system_prompt(user_message="스테이킹 방법 알려주세요")
        assert "Answer Patterns (for this question)" in result
        assert "스테이킹" in result

    def test_with_unmatched_user_message_has_no_patterns_section(self):
        result = build_system_prompt(user_message="오늘 날씨 어때요?")
        assert "Answer Patterns (for this question)" not in result

    def test_include_all_patterns_adds_all(self):
        result = build_system_prompt(include_all_patterns=True)
        assert "All Answer Patterns" in result
        # Should include patterns from multiple topics
        assert "스테이킹" in result
        assert "Titan" in result
        assert "GranTON" in result

    def test_include_all_patterns_overrides_user_message(self):
        # include_all_patterns should take precedence
        result = build_system_prompt(
            user_message="스테이킹",
            include_all_patterns=True,
        )
        assert "All Answer Patterns" in result
        assert "Answer Patterns (for this question)" not in result


class TestAnswerPatternSpeechLevel:
    """P0-3: All Korean answer patterns should use 해요체 consistently."""

    # 합니다체 endings that should NOT appear in Korean answer patterns
    FORMAL_ENDINGS = ["입니다.", "습니다.", "됩니다.", "갑니다."]

    def test_no_formal_endings_in_copy_exactly_patterns(self):
        """Patterns marked COPY EXACTLY should use 해요체, not 합니다체."""
        violations = []
        for pattern in ANSWER_PATTERNS:
            content = pattern["content"]
            if "COPY THIS ANSWER EXACTLY" not in content:
                continue
            # Extract the Korean text inside ``` blocks
            import re
            code_blocks = re.findall(r"```\n(.*?)```", content, re.DOTALL)
            for block in code_blocks:
                for ending in self.FORMAL_ENDINGS:
                    if ending in block:
                        # Find the line with the violation
                        for line in block.split("\n"):
                            if ending in line:
                                violations.append(f"  '{line.strip()}' contains '{ending}'")
        assert not violations, (
            f"합니다체 found in COPY EXACTLY patterns (should be 해요체):\n"
            + "\n".join(violations)
        )
