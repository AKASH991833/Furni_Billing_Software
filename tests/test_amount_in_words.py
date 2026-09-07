"""Tests for amount_in_words — Indian numbering system edge cases.

Run with:  python -m pytest tests/test_amount_in_words.py -q
"""
import pytest

from app.utils.calculations import amount_in_words


# ---------------------------------------------------------------------------
# Basic amounts
# ---------------------------------------------------------------------------

class TestBasicAmounts:
    def test_zero(self):
        result = amount_in_words(0)
        assert "Zero" in result
        assert "Rupees" in result

    def test_one_rupee(self):
        result = amount_in_words(1)
        assert "One" in result
        assert "Rupee Only" in result

    def test_single_digit(self):
        result = amount_in_words(5)
        assert "Five" in result

    def test_teen(self):
        result = amount_in_words(15)
        assert "Fifteen" in result

    def test_ten(self):
        result = amount_in_words(10)
        assert "Ten" in result

    def test_twenty(self):
        result = amount_in_words(20)
        assert "Twenty" in result

    def test_complex_under_100(self):
        result = amount_in_words(76)
        assert "Seventy Six" in result


# ---------------------------------------------------------------------------
# Hundreds
# ---------------------------------------------------------------------------

class TestHundreds:
    def test_exact_hundred(self):
        result = amount_in_words(100)
        assert "One Hundred" in result

    def test_hundred_and_ones(self):
        result = amount_in_words(123)
        assert "One Hundred Twenty Three" in result


# ---------------------------------------------------------------------------
# Thousands
# ---------------------------------------------------------------------------

class TestThousands:
    def test_one_thousand(self):
        result = amount_in_words(1000)
        assert "One Thousand" in result

    def test_complex_thousand(self):
        result = amount_in_words(1234)
        assert "One Thousand Two Hundred Thirty Four" in result


# ---------------------------------------------------------------------------
# Lakhs
# ---------------------------------------------------------------------------

class TestLakhs:
    def test_one_lakh(self):
        result = amount_in_words(100000)
        assert "One Lakh" in result

    def test_complex_lakh(self):
        result = amount_in_words(123456)
        assert "One Lakh Twenty Three Thousand Four Hundred Fifty Six" in result


# ---------------------------------------------------------------------------
# Crores
# ---------------------------------------------------------------------------

class TestCrores:
    def test_one_crore(self):
        result = amount_in_words(10000000)
        assert "One Crore" in result

    def test_complex_crore(self):
        result = amount_in_words(12345678)
        assert "One Crore" in result
        assert "Twenty Three Lakh" in result


# ---------------------------------------------------------------------------
# Paise
# ---------------------------------------------------------------------------

class TestPaise:
    def test_with_paise(self):
        result = amount_in_words(10.50)
        assert "Paise" in result
        assert "and" in result

    def test_exact_rupees_no_paise(self):
        result = amount_in_words(100.00)
        assert "Paise" not in result
        assert "Only" in result

    def test_small_paise(self):
        result = amount_in_words(0.99)
        assert "Ninety Nine Paise" in result

    def test_one_paise(self):
        result = amount_in_words(0.01)
        assert "One Paisa" in result

    def test_paise_rounds_to_100(self):
        """0.999 rounds to 1.00 → should show as 1 Rupee."""
        result = amount_in_words(0.999)
        assert "One Rupee" in result


# ---------------------------------------------------------------------------
# Negative amounts
# ---------------------------------------------------------------------------

class TestNegative:
    def test_negative_amount(self):
        result = amount_in_words(-500)
        assert "Minus" in result
        assert "Five Hundred" in result

    def test_negative_with_paise(self):
        result = amount_in_words(-10.50)
        assert "Minus" in result
        assert "Paise" in result


# ---------------------------------------------------------------------------
# Large numbers
# ---------------------------------------------------------------------------

class TestLargeNumbers:
    def test_million(self):
        result = amount_in_words(1000000)
        assert "Ten Lakh" in result

    def test_10_crore(self):
        result = amount_in_words(100000000)
        assert "Ten Crore" in result

    def test_very_large(self):
        result = amount_in_words(99999999.99)
        assert "Crore" in result
        assert "Lakh" in result
        assert "Paise" in result


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_string_input(self):
        result = amount_in_words("500")
        assert "Five Hundred" in result

    def test_invalid_input(self):
        result = amount_in_words("abc")
        assert "Zero" in result

    def test_none_input(self):
        result = amount_in_words(None)
        assert "Zero" in result

    def test_float_string(self):
        result = amount_in_words("1234.56")
        assert "One Thousand" in result
        assert "Paise" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
