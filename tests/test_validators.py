"""Tests for input validation utilities."""
from app.utils.validators import (
    validate_mobile,
    validate_email,
    validate_gstin,
    validate_pincode,
    validate_name,
    validate_customer,
    validate_business_profile,
)


class TestValidateMobile:
    def test_valid_10_digit(self):
        assert validate_mobile("9876543210") is None

    def test_valid_with_country_code(self):
        assert validate_mobile("919876543210") is None

    def test_valid_with_spaces(self):
        assert validate_mobile("98765 43210") is None

    def test_valid_with_dashes(self):
        assert validate_mobile("987-654-3210") is None

    def test_empty_is_valid(self):
        assert validate_mobile("") is None

    def test_none_is_valid(self):
        assert validate_mobile("  ") is None

    def test_too_short(self):
        assert validate_mobile("987654321") is not None

    def test_too_long(self):
        assert validate_mobile("98765432101") is not None

    def test_starts_with_5(self):
        assert validate_mobile("5876543210") is not None

    def test_starts_with_0(self):
        assert validate_mobile("0876543210") is not None

    def test_letters(self):
        assert validate_mobile("abcdefghij") is not None


class TestValidateEmail:
    def test_valid(self):
        assert validate_email("test@example.com") is None

    def test_valid_with_subdomain(self):
        assert validate_email("user@mail.example.co.in") is None

    def test_empty_is_valid(self):
        assert validate_email("") is None

    def test_none_is_valid(self):
        assert validate_email("  ") is None

    def test_no_at(self):
        assert validate_email("testexample.com") is not None

    def test_no_domain(self):
        assert validate_email("test@") is not None

    def test_no_tld(self):
        assert validate_email("test@example") is not None


class TestValidateGstin:
    def test_valid(self):
        assert validate_gstin("22AABCB1234F1Z5") is None

    def test_empty_is_valid(self):
        assert validate_gstin("") is None

    def test_too_short(self):
        assert validate_gstin("22AABCB1234") is not None

    def test_too_long(self):
        assert validate_gstin("22AABCB1234F1Z55") is not None

    def test_invalid_format(self):
        assert validate_gstin("22aabcB1234f1z5") is None  # case insensitive

    def test_wrong_state_code(self):
        assert validate_gstin("00AABCB1234F1Z5") is None  # 00 is technically valid format


class TestValidatePincode:
    def test_valid(self):
        assert validate_pincode("492001") is None

    def test_empty_is_valid(self):
        assert validate_pincode("") is None

    def test_too_short(self):
        assert validate_pincode("49200") is not None

    def test_too_long(self):
        assert validate_pincode("4920012") is not None

    def test_letters(self):
        assert validate_pincode("49200A") is not None


class TestValidateName:
    def test_valid(self):
        assert validate_name("John") is None

    def test_empty(self):
        assert validate_name("") is not None

    def test_single_char(self):
        assert validate_name("J") is not None

    def test_custom_field_name(self):
        err = validate_name("", "Business name")
        assert "Business name" in err


class TestValidateCustomer:
    def test_valid_customer(self):
        data = {
            "name": "Test Customer",
            "mobile": "9876543210",
            "email": "test@example.com",
            "gstin": "22AABCB1234F1Z5",
            "pincode": "492001",
        }
        errors = validate_customer(data)
        assert len(errors) == 0

    def test_missing_name(self):
        data = {"name": "", "mobile": "9876543210"}
        errors = validate_customer(data)
        assert len(errors) == 1
        assert errors[0].field == "name"

    def test_multiple_errors(self):
        data = {"name": "", "mobile": "123", "email": "invalid"}
        errors = validate_customer(data)
        assert len(errors) == 3

    def test_optional_fields_empty(self):
        data = {"name": "Test"}
        errors = validate_customer(data)
        assert len(errors) == 0


class TestValidateBusinessProfile:
    def test_valid_profile(self):
        data = {
            "business_name": "My Shop",
            "mobile": "9876543210",
            "email": "shop@example.com",
        }
        errors = validate_business_profile(data)
        assert len(errors) == 0

    def test_missing_business_name(self):
        data = {"business_name": ""}
        errors = validate_business_profile(data)
        assert len(errors) == 1
        assert errors[0].field == "business_name"
