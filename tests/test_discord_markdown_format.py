"""Tests for Discord message formatting."""

from tokamak.channels.discord import format_discord_message


class TestFormatDiscordMessage:
    """Tests for format_discord_message link handling."""

    def test_masked_link_converted_to_angle_bracket_format(self):
        result = format_discord_message("[공식 문서](https://docs.tokamak.network)")
        assert result == "[공식 문서](<https://docs.tokamak.network>)"

    def test_bare_url_wrapped(self):
        result = format_discord_message("Visit https://docs.tokamak.network for docs")
        assert "Visit <https://docs.tokamak.network>" in result

    def test_already_wrapped_url_unchanged(self):
        result = format_discord_message("Visit <https://docs.tokamak.network>")
        assert "<https://docs.tokamak.network>" in result
        assert "<<" not in result

    def test_mixed_masked_and_bare(self):
        result = format_discord_message(
            "[Docs](https://docs.tokamak.network) and https://tokamak.network"
        )
        assert "[Docs](<https://docs.tokamak.network>)" in result
        assert "<https://tokamak.network>" in result

    def test_multiple_masked_links(self):
        content = (
            "🔗 [TON 구매 가이드](https://docs.tokamak.network/home/information/get-ton)\n"
            "🔗 [Etherscan](https://etherscan.io/token/0x2be5e8c109e2197D077D13A82dAead6a9b3433C5)"
        )
        result = format_discord_message(content)
        assert "[TON 구매 가이드](<https://docs.tokamak.network/home/information/get-ton>)" in result
        assert "[Etherscan](<https://etherscan.io/token/0x2be5e8c109e2197D077D13A82dAead6a9b3433C5>)" in result

    def test_already_angle_bracket_link_not_double_wrapped(self):
        result = format_discord_message("[Docs](<https://docs.tokamak.network>)")
        assert result == "[Docs](<https://docs.tokamak.network>)"
        assert "<<" not in result

    def test_horizontal_rule_removed(self):
        result = format_discord_message("above\n---\nbelow")
        assert "---" not in result

    def test_multiple_newlines_collapsed(self):
        result = format_discord_message("a\n\n\n\nb")
        assert result == "a\n\nb"


class TestUrlWithKoreanParticle:
    """Tests for URL formatting when Korean particles are attached (LLM output patterns)."""

    # LLM이 백틱으로 감싼 URL 뒤에 한국어 조사가 붙는 패턴들
    # 예: `https://example.com`은 -> `<https://example.com`은> (깨짐)
    BROKEN_CASES = [
        # (입력, 깨진 출력에 포함되면 안 되는 패턴, 설명)
        (
            "`https://staking-community-version.vercel.app`은 토카막 네트워크의 공식 스테이킹 커뮤니티 버전 인터페이스입니다.",
            "`은>",
            "백틱+URL 뒤에 조사 '은' 붙은 경우",
        ),
        (
            "`https://staking-community-version.vercel.app/`을 확인해보세요.",
            "`을>",
            "백틱+URL(trailing slash) 뒤에 조사 '을' 붙은 경우",
        ),
        (
            "`https://docs.tokamak.network`에서 확인할 수 있습니다.",
            "`에서>",
            "백틱+URL 뒤에 조사 '에서' 붙은 경우",
        ),
        (
            "`https://tokamak.network`로 이동하세요.",
            "`로>",
            "백틱+URL 뒤에 조사 '로' 붙은 경우",
        ),
        (
            "https://staking-community-version.vercel.app은 토카막 네트워크의 스테이킹 페이지입니다.",
            "app은>",
            "백틱 없이 bare URL 뒤에 조사 '은' 바로 붙은 경우",
        ),
    ]

    def test_url_not_merged_with_korean_particle(self):
        """URL과 한국어 조사가 합쳐져서 깨지는 경우가 없는지 5번 반복 확인."""
        failures = []
        for run in range(5):
            for input_text, broken_pattern, desc in self.BROKEN_CASES:
                result = format_discord_message(input_text)
                if broken_pattern in result:
                    failures.append(
                        f"[Run {run+1}] {desc}\n"
                        f"  Input:  {input_text}\n"
                        f"  Output: {result}\n"
                        f"  Found broken pattern: '{broken_pattern}'"
                    )

        if failures:
            failure_msg = "\n\n".join(failures)
            raise AssertionError(
                f"URL이 한국어 조사와 합쳐져서 깨지는 케이스 {len(failures)}건 발견:\n\n{failure_msg}"
            )

    def test_backtick_url_with_particle_eun(self):
        """백틱 URL + '은' 조사: `https://...`은 -> 깨지면 안 됨."""
        result = format_discord_message(
            "`https://staking-community-version.vercel.app`은 토카막 네트워크의 공식 스테이킹 커뮤니티 버전 인터페이스입니다."
        )
        # URL이 조사와 합쳐지면 안 됨
        assert "`은>" not in result, f"URL과 조사가 합쳐짐: {result}"
        # URL은 angle bracket으로 올바르게 감싸져야 함
        assert "<https://staking-community-version.vercel.app>" in result or \
               "`https://staking-community-version.vercel.app`" in result, \
               f"URL이 올바르게 포맷되지 않음: {result}"

    def test_backtick_url_with_particle_eul(self):
        """백틱 URL + '을' 조사: `https://...`을 -> 깨지면 안 됨."""
        result = format_discord_message(
            "`https://staking-community-version.vercel.app/`을 확인해보세요."
        )
        assert "`을>" not in result, f"URL과 조사가 합쳐짐: {result}"

    def test_backtick_url_with_particle_eseo(self):
        """백틱 URL + '에서' 조사: `https://...`에서 -> 깨지면 안 됨."""
        result = format_discord_message(
            "`https://docs.tokamak.network`에서 확인할 수 있습니다."
        )
        assert "`에서>" not in result, f"URL과 조사가 합쳐짐: {result}"

    def test_bare_url_with_particle_attached(self):
        """bare URL 바로 뒤에 조사가 붙은 경우도 URL만 올바르게 감싸야 함."""
        result = format_discord_message(
            "https://staking-community-version.vercel.app은 토카막 네트워크의 스테이킹 페이지입니다."
        )
        assert "app은>" not in result, f"URL과 조사가 합쳐짐: {result}"
