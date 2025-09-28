#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PktMask GUI架构改进 - 其他GUI框架实现示例
展示如何轻松切换到不同的GUI框架
"""

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any, Dict, Optional

# 导入接口定义
# from .gui_architecture_interfaces import IMainView, AppState, ProcessingProgress, ProcessingResult


# ============================================================================
# 1. Tkinter View实现示例
# ============================================================================


class TkinterMainView(tk.Tk):  # 实际应该继承 IMainView
    """Tkinter主View实现 - 展示GUI框架切换的简易性"""

    def __init__(self):
        super().__init__()
        self._presenter = None
        self._setup_ui()
        self._connect_events()

    def set_presenter(self, presenter):
        """设置Presenter"""
        self._presenter = presenter

    # ========================================================================
    # IView 接口实现 (简化版本)
    # ========================================================================

    def show_main_window(self) -> None:
        """显示主窗口"""
        self.deiconify()
        self.lift()
        self.focus_force()

    def close_application(self) -> None:
        """关闭应用程序"""
        self.quit()
        self.destroy()

    def update_app_state(self, state) -> None:  # state: AppState
        """更新应用程序状态显示"""
        # 更新目录显示
        if state.input_directory:
            self.input_dir_var.set(os.path.basename(state.input_directory))
        else:
            self.input_dir_var.set("Select input directory")

        if state.output_directory:
            self.output_dir_var.set(os.path.basename(state.output_directory))
        else:
            self.output_dir_var.set("Select output directory")

        # 更新选项
        if state.processing_options:
            self.remove_dupes_var.set(
                state.processing_options.get("remove_dupes", False)
            )
            self.anonymize_ips_var.set(
                state.processing_options.get("anonymize_ips", False)
            )
            self.mask_payloads_var.set(
                state.processing_options.get("mask_payloads", False)
            )

    def update_progress(self, progress) -> None:  # progress: ProcessingProgress
        """更新处理进度显示"""
        self.progress_var.set(progress.percentage)
        self.current_file_var.set(
            f"Processing: {os.path.basename(progress.current_file)}"
        )

        # 更新日志
        log_message = (
            f"[{progress.stage_name}] {os.path.basename(progress.current_file)}"
        )
        self.log_text.insert(tk.END, log_message + "\n")
        self.log_text.see(tk.END)

    def show_error(self, title: str, message: str) -> None:
        """显示错误信息"""
        messagebox.showerror(title, message)

    def show_warning(self, title: str, message: str) -> None:
        """显示警告信息"""
        messagebox.showwarning(title, message)

    def show_info(self, title: str, message: str) -> None:
        """显示信息提示"""
        messagebox.showinfo(title, message)

    def prompt_directory_selection(
        self, title: str, initial_dir: str = ""
    ) -> Optional[str]:
        """提示用户选择目录"""
        directory = filedialog.askdirectory(title=title, initialdir=initial_dir)
        return directory if directory else None

    # ========================================================================
    # UI设置方法
    # ========================================================================

    def _setup_ui(self) -> None:
        """设置UI界面"""
        self.title("PktMask - Packet Processing Tool (Tkinter)")
        self.geometry("800x600")

        # 创建变量
        self.input_dir_var = tk.StringVar(value="Select input directory")
        self.output_dir_var = tk.StringVar(value="Select output directory")
        self.remove_dupes_var = tk.BooleanVar()
        self.anonymize_ips_var = tk.BooleanVar()
        self.mask_payloads_var = tk.BooleanVar()
        self.progress_var = tk.DoubleVar()
        self.current_file_var = tk.StringVar(value="Ready")

        # 创建主框架
        main_frame = ttk.Frame(self, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 配置网格权重
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)

        row = 0

        # 目录选择区域
        self._create_directory_section(main_frame, row)
        row += 2

        # 选项区域
        self._create_options_section(main_frame, row)
        row += 1

        # 进度区域
        self._create_progress_section(main_frame, row)
        row += 2

        # 日志区域
        self._create_log_section(main_frame, row)
        row += 1

        # 控制区域
        self._create_control_section(main_frame, row)

    def _create_directory_section(self, parent, start_row) -> None:
        """创建目录选择区域"""
        # 输入目录
        ttk.Label(parent, text="Input Directory:").grid(
            row=start_row, column=0, sticky=tk.W, pady=2
        )
        input_frame = ttk.Frame(parent)
        input_frame.grid(row=start_row, column=1, sticky=(tk.W, tk.E), pady=2)
        input_frame.columnconfigure(0, weight=1)

        ttk.Button(input_frame, text="Browse", command=self._on_input_dir_clicked).grid(
            row=0, column=1, padx=(5, 0)
        )
        ttk.Label(input_frame, textvariable=self.input_dir_var).grid(
            row=0, column=0, sticky=(tk.W, tk.E)
        )

        # 输出目录
        ttk.Label(parent, text="Output Directory:").grid(
            row=start_row + 1, column=0, sticky=tk.W, pady=2
        )
        output_frame = ttk.Frame(parent)
        output_frame.grid(row=start_row + 1, column=1, sticky=(tk.W, tk.E), pady=2)
        output_frame.columnconfigure(0, weight=1)

        ttk.Button(
            output_frame, text="Browse", command=self._on_output_dir_clicked
        ).grid(row=0, column=1, padx=(5, 0))
        ttk.Label(output_frame, textvariable=self.output_dir_var).grid(
            row=0, column=0, sticky=(tk.W, tk.E)
        )

    def _create_options_section(self, parent, row) -> None:
        """创建选项区域"""
        options_frame = ttk.LabelFrame(parent, text="Processing Options", padding="5")
        options_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)

        ttk.Checkbutton(
            options_frame,
            text="Remove Duplicates",
            variable=self.remove_dupes_var,
            command=self._on_options_changed,
        ).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(
            options_frame,
            text="Anonymize IPs",
            variable=self.anonymize_ips_var,
            command=self._on_options_changed,
        ).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(
            options_frame,
            text="Mask Payloads",
            variable=self.mask_payloads_var,
            command=self._on_options_changed,
        ).pack(side=tk.LEFT, padx=5)

    def _create_progress_section(self, parent, start_row) -> None:
        """创建进度区域"""
        progress_frame = ttk.LabelFrame(parent, text="Progress", padding="5")
        progress_frame.grid(
            row=start_row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5
        )
        progress_frame.columnconfigure(0, weight=1)

        self.progress_bar = ttk.Progressbar(
            progress_frame, variable=self.progress_var, maximum=100
        )
        self.progress_bar.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=2)

        ttk.Label(progress_frame, textvariable=self.current_file_var).grid(
            row=1, column=0, sticky=tk.W, pady=2
        )

    def _create_log_section(self, parent, row) -> None:
        """创建日志区域"""
        log_frame = ttk.LabelFrame(parent, text="Log", padding="5")
        log_frame.grid(
            row=row, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5
        )
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        # 创建文本框和滚动条
        text_frame = ttk.Frame(log_frame)
        text_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)

        self.log_text = tk.Text(text_frame, height=8, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(
            text_frame, orient=tk.VERTICAL, command=self.log_text.yview
        )
        self.log_text.configure(yscrollcommand=scrollbar.set)

        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

    def _create_control_section(self, parent, row) -> None:
        """创建控制区域"""
        control_frame = ttk.Frame(parent)
        control_frame.grid(
            row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10
        )

        self.start_button = ttk.Button(
            control_frame, text="Start Processing", command=self._on_start_clicked
        )
        self.start_button.pack(side=tk.RIGHT, padx=5)

        ttk.Button(control_frame, text="Clear Log", command=self._clear_log).pack(
            side=tk.RIGHT, padx=5
        )

    def _connect_events(self) -> None:
        """连接事件"""
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    # ========================================================================
    # 事件处理方法
    # ========================================================================

    def _on_input_dir_clicked(self) -> None:
        """输入目录按钮点击"""
        if self._presenter:
            self._presenter.select_input_directory()

    def _on_output_dir_clicked(self) -> None:
        """输出目录按钮点击"""
        if self._presenter:
            self._presenter.select_output_directory()

    def _on_options_changed(self) -> None:
        """处理选项变更"""
        if self._presenter:
            options = {
                "remove_dupes": self.remove_dupes_var.get(),
                "anonymize_ips": self.anonymize_ips_var.get(),
                "mask_payloads": self.mask_payloads_var.get(),
            }
            self._presenter.update_processing_options(options)

    def _on_start_clicked(self) -> None:
        """开始按钮点击"""
        if self._presenter:
            if self._presenter.is_processing():
                self._presenter.stop_processing()
            else:
                self._presenter.start_processing()

    def _clear_log(self) -> None:
        """清空日志"""
        self.log_text.delete(1.0, tk.END)

    def _on_closing(self) -> None:
        """窗口关闭事件"""
        if self._presenter:
            self._presenter.shutdown()
        else:
            self.destroy()


# ============================================================================
# 2. Web GUI实现示例 (使用Flask + HTML)
# ============================================================================


class WebMainView:  # 实际应该继承 IMainView
    """Web GUI实现示例 - 展示跨平台GUI的可能性"""

    def __init__(self):
        self._presenter = None
        self._app_state = None
        self._setup_web_server()

    def set_presenter(self, presenter):
        """设置Presenter"""
        self._presenter = presenter

    def _setup_web_server(self):
        """设置Web服务器"""
        # 这里可以使用Flask, FastAPI等框架
        # 实现RESTful API和WebSocket通信
        pass

    def show_main_window(self) -> None:
        """显示主窗口 (打开浏览器)"""
        import webbrowser

        webbrowser.open("http://localhost:8080")

    def update_app_state(self, state) -> None:
        """更新应用程序状态 (通过WebSocket推送)"""
        self._app_state = state
        # 通过WebSocket推送状态更新到前端
        self._push_state_update(state)

    def _push_state_update(self, state):
        """推送状态更新到Web前端"""
        # 实现WebSocket推送逻辑
        pass


# ============================================================================
# 3. CLI View实现示例
# ============================================================================


class CLIMainView:  # 实际应该继承 IMainView
    """CLI View实现 - 展示命令行界面的统一"""

    def __init__(self):
        self._presenter = None

    def set_presenter(self, presenter):
        """设置Presenter"""
        self._presenter = presenter

    def show_main_window(self) -> None:
        """显示主界面 (CLI交互)"""
        print("=== PktMask CLI Interface ===")
        self._run_cli_loop()

    def _run_cli_loop(self):
        """运行CLI交互循环"""
        while True:
            print("\nOptions:")
            print("1. Select input directory")
            print("2. Select output directory")
            print("3. Configure processing options")
            print("4. Start processing")
            print("5. Exit")

            choice = input("Enter your choice (1-5): ").strip()

            if choice == "1":
                self._select_input_directory()
            elif choice == "2":
                self._select_output_directory()
            elif choice == "3":
                self._configure_options()
            elif choice == "4":
                self._start_processing()
            elif choice == "5":
                break
            else:
                print("Invalid choice. Please try again.")

    def _select_input_directory(self):
        """选择输入目录"""
        directory = input("Enter input directory path: ").strip()
        if os.path.exists(directory):
            if self._presenter:
                # 这里需要适配Presenter接口
                print(f"Input directory set to: {directory}")
        else:
            print("Directory does not exist.")

    def update_progress(self, progress) -> None:
        """更新处理进度"""
        print(f"Progress: {progress.percentage:.1f}% - {progress.current_file}")

    def show_error(self, title: str, message: str) -> None:
        """显示错误信息"""
        print(f"ERROR: {message}")

    def show_info(self, title: str, message: str) -> None:
        """显示信息"""
        print(f"INFO: {message}")


# ============================================================================
# 4. 应用程序工厂
# ============================================================================


def create_application(gui_type: str = "pyqt6"):
    """创建应用程序 - 支持多种GUI框架"""

    # 创建事件总线和Presenter (GUI无关)
    # event_bus = EventBus()
    # presenter = MainPresenter()
    # presenter.set_event_bus(event_bus)

    # 根据类型创建不同的View
    if gui_type.lower() == "tkinter":
        view = TkinterMainView()
    elif gui_type.lower() == "web":
        view = WebMainView()
    elif gui_type.lower() == "cli":
        view = CLIMainView()
    else:  # 默认PyQt6
        from .gui_architecture_pyqt6_view import PyQt6MainView

        view = PyQt6MainView()

    # 连接组件
    # presenter.set_view(view)
    # view.set_presenter(presenter)

    return view  # , presenter, event_bus


if __name__ == "__main__":
    import sys

    # 从命令行参数选择GUI类型
    gui_type = sys.argv[1] if len(sys.argv) > 1 else "tkinter"

    if gui_type == "tkinter":
        view = create_application("tkinter")
        view.mainloop()
    elif gui_type == "cli":
        view = create_application("cli")
        view.show_main_window()
    else:
        print(f"Unsupported GUI type: {gui_type}")
        print("Supported types: tkinter, cli")
