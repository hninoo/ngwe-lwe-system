"""Centralized desktop UI theme constants."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    """Fusion dark palette used by PyQt dashboard surfaces."""

    bg_dark: str = "#1e1e2e"
    bg_sidebar: str = "#181825"
    bg_card: str = "#2a2a3e"
    bg_input: str = "#313244"
    border: str = "#313244"
    text_primary: str = "#cdd6f4"
    text_secondary: str = "#a6adc8"
    text_muted: str = "#6c7086"
    accent_blue: str = "#89b4fa"
    accent_green: str = "#a6e3a1"
    accent_red: str = "#f38ba8"
    accent_yellow: str = "#f9e2af"
    accent_mauve: str = "#cba6f7"
    accent_teal: str = "#94e2d5"


PALETTE = Palette()

BG_DARK = PALETTE.bg_dark
BG_SIDEBAR = PALETTE.bg_sidebar
BG_CARD = PALETTE.bg_card
BG_INPUT = PALETTE.bg_input
BORDER_COLOR = PALETTE.border
TEXT_PRIMARY = PALETTE.text_primary
TEXT_SECONDARY = PALETTE.text_secondary
TEXT_MUTED = PALETTE.text_muted
ACCENT_BLUE = PALETTE.accent_blue
ACCENT_GREEN = PALETTE.accent_green
ACCENT_RED = PALETTE.accent_red
ACCENT_YELLOW = PALETTE.accent_yellow
ACCENT_MAUVE = PALETTE.accent_mauve
ACCENT_TEAL = PALETTE.accent_teal
