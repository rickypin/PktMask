#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
本模块定义了应用的动态样式表系统。
它能够根据浅色/深色模式生成统一的视觉样式。
"""

# --- 设计规范 ---

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
    "LOG_FONT_FAMILY": "Menlo, Consolas, Monaco, monospace"
}


def generate_stylesheet(mode: str) -> str:
    """
    根据给定的模式（'light' 或 'dark'）生成完整的QSS样式表。
    """
    palette = DARK_PALETTE if mode == 'dark' else LIGHT_PALETTE

    qss = f"""
        QMainWindow {{
            background-color: {palette['WINDOW_BG']};
        }}

        QGroupBox {{
            background-color: {palette['PANEL_BG']};
            border: 1px solid {palette['BORDER_COLOR']};
            border-radius: 8px;
            margin-top: 1ex; /* 为标题留出空间 */
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

        /* --- 特殊的 QLabel 样式 --- */
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
            border-radius: 4px;
            text-align: center;
            background-color: {palette['PROGRESS_BAR_BG']};
            color: {palette['PRIMARY_TEXT']};
        }}

        QProgressBar::chunk {{
            background-color: {palette['PRIMARY_BUTTON_BG']};
            width: 10px;
            margin: 0.5px;
        }}

        QCheckBox {{
            font-family: {FONTS['FONT_FAMILY']};
            font-size: {FONTS['BODY']};
            color: {palette['PRIMARY_TEXT']};
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