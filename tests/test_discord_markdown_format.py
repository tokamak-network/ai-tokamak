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
