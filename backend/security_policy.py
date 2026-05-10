COMMON_PASSWORDS = {
    "password",
    "password123",
    "123456",
    "12345678",
    "123456789",
    "admin",
    "admin123",
    "owner",
    "qwerty",
    "ngwe_lwe",
}


def validate_password_strength(password: str) -> None:
    if len(password) < 10:
        raise ValueError("Password must be at least 10 characters long.")
    lowered = password.strip().lower()
    if lowered in COMMON_PASSWORDS:
        raise ValueError("Password is too common.")
    categories = [
        any(c.islower() for c in password),
        any(c.isupper() for c in password),
        any(c.isdigit() for c in password),
        any(not c.isalnum() for c in password),
    ]
    if sum(categories) < 3:
        raise ValueError(
            "Password must include at least three of: lowercase, uppercase, number, symbol."
        )


def validate_pin(pin: str) -> None:
    if len(pin) != 6 or not pin.isdigit():
        raise ValueError("PIN must be exactly 6 digits.")
    if len(set(pin)) == 1 or pin in {"123456", "654321", "000000"}:
        raise ValueError("PIN is too easy to guess.")

