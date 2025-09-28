#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This module defines the application's dynamic stylesheet system.
It can generate unified visual styles based on light/dark mode.
"""

# --- Design Specifications ---

LIGHT_PALETTE = {
    "WINDOW_BG": "#F0F0F0",
    "PANEL_BG": "#FFFFFF",
    "PRIMARY_TEXT": "#1D1D1F",
    "SECONDARY_TEXT": "#6E6E73",
    "PRIMARY_BUTTON_BG": "#007AFF",
    "PRIMARY_BUTTON_HOVER_BG": "#0062CC",
    "SECONDARY_BUTTON_BG": "#E9E9E9",
    "SECONDARY_BUTTON_HOVER_BG": "#DCDCDC",
    "BORDER_COLOR": "#DCDCDC",
    "PROGRESS_BAR_BG": "#E0E0E0",
}

DARK_PALETTE = {
    "WINDOW_BG": "#1C1C1E",
    "PANEL_BG": "#2C2C2E",
    "PRIMARY_TEXT": "#F5F5F7",
    "SECONDARY_TEXT": "#8D8D92",
    "PRIMARY_BUTTON_BG": "#0A84FF",
    "PRIMARY_BUTTON_HOVER_BG": "#0069D9",
    "SECONDARY_BUTTON_BG": "#3A3A3C",
    "SECONDARY_BUTTON_HOVER_BG": "#545456",
    "BORDER_COLOR": "#3A3A3C",
    "PROGRESS_BAR_BG": "#424242",
}

FONTS = {
    "H1": "16pt",
    "H2": "13pt",
    "BODY": "11pt",
    "KPI": "24pt",
    "KPI_LABEL": "10pt",
    "LOG": "10pt",
    "FONT_FAMILY": "Inter, -apple-system, Segoe UI, sans-serif",
    "LOG_FONT_FAMILY": "Menlo, Consolas, Monaco, monospace",
}


def generate_stylesheet(mode: str) -> str:
    """
    Generate complete QSS stylesheet based on given mode ('light' or 'dark').
    """
    palette = DARK_PALETTE if mode == "dark" else LIGHT_PALETTE

    qss = f"""
        QMainWindow {{
            background-color: {palette['WINDOW_BG']};
        }}

        QGroupBox {{
            background-color: {palette['PANEL_BG']};
            border: 1px solid {palette['BORDER_COLOR']};
            border-radius: 8px;
            margin-top: 1ex; /* Leave space for title */
            font-family: {FONTS['FONT_FAMILY']};
            font-size: {FONTS['H2']};
            font-weight: 600;
            color: {palette['PRIMARY_TEXT']};
        }}

        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 10px;
            left: 10px;
        }}

        QLabel {{
            font-family: {FONTS['FONT_FAMILY']};
            color: {palette['SECONDARY_TEXT']};
            background-color: transparent;
            font-size: {FONTS['BODY']};
        }}

        /* --- Special QLabel Styles --- */
        #DirPathLabel {{
            color: {palette['PRIMARY_BUTTON_BG']};
            font-size: 13pt;
            font-weight: 600;
        }}
        #FilesProcessedLabel, #IpsMaskedLabel, #DupesRemovedLabel {{
            color: {palette['PRIMARY_TEXT']};
            font-family: {FONTS['FONT_FAMILY']};
            font-size: {FONTS['KPI']};
            font-weight: 600;
        }}

        QPushButton {{
            font-family: {FONTS['FONT_FAMILY']};
            background-color: {palette['PRIMARY_BUTTON_BG']};
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            font-size: {FONTS['BODY']};
            font-weight: 500;
        }}

        QPushButton:hover {{
            background-color: {palette['PRIMARY_BUTTON_HOVER_BG']};
        }}

        QPushButton#ResetButton {{
            background-color: {palette['SECONDARY_BUTTON_BG']};
            color: {palette['PRIMARY_TEXT']};
        }}

        QPushButton#ResetButton:hover {{
            background-color: {palette['SECONDARY_BUTTON_HOVER_BG']};
        }}

        QTextEdit {{
            background-color: {palette['PANEL_BG']};
            color: {palette['PRIMARY_TEXT']};
            border: 1px solid {palette['BORDER_COLOR']};
            border-radius: 8px;
            font-family: {FONTS['LOG_FONT_FAMILY']};
            font-size: {FONTS['LOG']};
        }}

        QProgressBar {{
            border: 1px solid {palette['BORDER_COLOR']};
            border-radius: 6px;
            text-align: center;
            background-color: {palette['PROGRESS_BAR_BG']};
            color: {palette['PRIMARY_TEXT']};
            font-size: 10px;
            font-weight: 500;
            min-height: 18px;
            max-height: 18px;
        }}

        QProgressBar::chunk {{
            background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                stop: 0 {palette['PRIMARY_BUTTON_BG']},
                stop: 0.5 {palette['PRIMARY_BUTTON_HOVER_BG']},
                stop: 1 {palette['PRIMARY_BUTTON_BG']});
            background-image: repeating-linear-gradient(
                45deg,
                transparent,
                transparent 4px,
                rgba(255,255,255,0.1) 4px,
                rgba(255,255,255,0.1) 8px
            );
            border-radius: 5px;
            margin: 1px;
        }}

        QCheckBox {{
            font-family: {FONTS['FONT_FAMILY']};
            font-size: {FONTS['BODY']};
            color: {palette['PRIMARY_TEXT']};
            spacing: 6px;
        }}

        QCheckBox::indicator {{
            width: 14px;
            height: 14px;
            border-radius: 3px;
            border: 1px solid {palette['BORDER_COLOR']};
            background-color: {palette['PANEL_BG']};
        }}

        QCheckBox::indicator:hover {{
            border-color: {palette['PRIMARY_BUTTON_BG']};
            background-color: rgba(0, 122, 255, 0.1);
        }}

        QCheckBox::indicator:checked {{
            background-color: {palette['PRIMARY_BUTTON_BG']};
            border-color: {palette['PRIMARY_BUTTON_BG']};
            color: white;
        }}

        QCheckBox::indicator:checked:hover {{
            background-color: {palette['PRIMARY_BUTTON_HOVER_BG']};
            border-color: {palette['PRIMARY_BUTTON_HOVER_BG']};
        }}

        QSplitter::handle {{
            background: {palette['WINDOW_BG']};
        }}
        QSplitter::handle:horizontal {{
            width: 2px;
        }}
        QSplitter::handle:vertical {{
            height: 2px;
        }}
    """
    return qss
