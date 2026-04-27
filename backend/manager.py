#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
悠米 AI 桌面管理应用 (PySide6 版本)
功能：配置端口、启动/停止 FastAPI 服务、实时日志查看、主题与背景设置、预览对话网站
"""

import sys
import os
import json
import subprocess
import webbrowser
from pathlib import Path
from datetime import datetime

from PySide6.QtCore import (
    Qt, QTimer, QProcess, QThread, Signal, QUrl
)
from PySide6.QtGui import (
    QFont, QColor, QPalette, QPixmap, QIcon, QBrush, QLinearGradient
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit, QTabWidget,
    QFileDialog, QMessageBox, QSplitter, QFrame, QStackedWidget,
    QListWidget, QListWidgetItem, QGroupBox, QFormLayout,
    QColorDialog, QStyleFactory, QSizePolicy, QScrollBar,
    QComboBox
)

# ---------------------------- 路径配置 ----------------------------
BACKEND_DIR = Path(__file__).parent.absolute()
ROOT_DIR = BACKEND_DIR.parent
CONFIG_PATH = BACKEND_DIR / "config.json"
LOG_DIR = ROOT_DIR / "logs"
LOG_FILE = LOG_DIR / "backend.log"


def load_config():
    """加载配置文件"""
    default = {
        "port": 8000,
        "model": "qwen3.5:4b",
        "theme_color": "#6C63FF",
        "background_image": "",
        "logs_dir": "logs",
        "log_file": "backend.log"
    }
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        for k, v in default.items():
            cfg.setdefault(k, v)
        return cfg
    return default.copy()


def save_config(config):
    """保存配置文件"""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)


# ---------------------------- 主窗口 ----------------------------
class YumiManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.process = None
        self.init_ui()
        self.apply_theme()
        self.start_log_timer()

    # ---------- UI 构建 ----------
    def init_ui(self):
        self.setWindowTitle("悠米 AI 管理控制台")
        self.resize(1000, 680)
        self.setMinimumSize(800, 550)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # ---- 左侧导航栏 ----
        self.nav_list = QListWidget()
        self.nav_list.setFixedWidth(170)
        self.nav_list.setObjectName("navList")
        items = [
            ("⚡ 服务管理", 0),
            ("📋 实时日志", 1),
            ("🎨 外观设置", 2),
            ("🌐 预览网站", 3),
        ]
        for text, idx in items:
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, idx)
            self.nav_list.addItem(item)
        self.nav_list.setCurrentRow(0)
        self.nav_list.currentRowChanged.connect(self.switch_page)

        # ---- 右侧内容区 ----
        self.stack = QStackedWidget()

        self.page_service = self.create_service_page()
        self.stack.addWidget(self.page_service)

        self.page_log = self.create_log_page()
        self.stack.addWidget(self.page_log)

        self.page_appearance = self.create_appearance_page()
        self.stack.addWidget(self.page_appearance)

        self.page_preview = self.create_preview_page()
        self.stack.addWidget(self.page_preview)

        # 分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.nav_list)
        splitter.addWidget(self.stack)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setHandleWidth(0)
        main_layout.addWidget(splitter)

        # 底部状态栏
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("就绪")
        self.status_label = QLabel("服务未运行")
        self.status_bar.addPermanentWidget(self.status_label)

    # ---------- 服务管理页面 ----------
    def create_service_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)

        self.service_tabs = QTabWidget()
        tab_config = QWidget()
        tab_config_layout = QFormLayout(tab_config)
        tab_config_layout.setSpacing(12)

        self.port_edit = QLineEdit(str(self.config["port"]))
        self.port_edit.setPlaceholderText("输入端口号，例如 8000")
        self.port_edit.setToolTip("服务监听端口，重启服务后生效")

        # 模型选择 - 下拉菜单 + 自定义输入
        self.model_combo = QComboBox()
        self.model_combo.setEditable(False)
        self.model_combo.addItem("qwen3.5:4b", "qwen3.5:4b")
        self.model_combo.addItem("deepseek-r1:1.5b", "deepseek-r1:1.5b")
        self.model_combo.addItem("🤖 自定义...", "custom")
        
        self.model_custom_edit = QLineEdit()
        self.model_custom_edit.setPlaceholderText("输入自定义模型或API配置")
        self.model_custom_edit.setEnabled(False)
        self.model_custom_edit.hide()
        
        self.model_combo.currentIndexChanged.connect(self.on_model_combo_changed)
        
        current_model = self.config["model"]
        if current_model in ["qwen3.5:4b", "deepseek-r1:1.5b"]:
            index = self.model_combo.findData(current_model)
            if index >= 0:
                self.model_combo.setCurrentIndex(index)
        else:
            self.model_combo.setCurrentIndex(self.model_combo.findData("custom"))
            self.model_custom_edit.setText(current_model)
            self.model_custom_edit.setEnabled(True)
            self.model_custom_edit.show()

        self.save_config_btn = QPushButton("保存配置")
        self.save_config_btn.clicked.connect(self.save_current_config)

        model_layout = QVBoxLayout()
        model_layout.addWidget(self.model_combo)
        model_layout.addWidget(self.model_custom_edit)

        tab_config_layout.addRow("端口号:", self.port_edit)
        tab_config_layout.addRow("模型:", model_layout)
        tab_config_layout.addRow("", self.save_config_btn)

        tab_control = QWidget()
        control_layout = QVBoxLayout(tab_control)
        control_layout.setSpacing(14)

        self.start_btn = QPushButton("▶ 启动服务")
        self.stop_btn = QPushButton("⏹ 停止服务")
        self.stop_btn.setEnabled(False)
        self.restart_btn = QPushButton("↻ 重启服务")

        self.start_btn.clicked.connect(self.start_service)
        self.stop_btn.clicked.connect(self.stop_service)
        self.restart_btn.clicked.connect(self.restart_service)

        control_layout.addWidget(self.start_btn)
        control_layout.addWidget(self.stop_btn)
        control_layout.addWidget(self.restart_btn)
        control_layout.addStretch()

        self.service_tabs.addTab(tab_config, "配置")
        self.service_tabs.addTab(tab_control, "控制")

        layout.addWidget(self.service_tabs)
        return page

    # ---------- 日志页面 ----------
    def create_log_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFont(QFont("Consolas", 10))
        self.log_view.setPlaceholderText("等待日志...")

        btn_layout = QHBoxLayout()
        self.clear_log_btn = QPushButton("清空日志")
        self.clear_log_btn.clicked.connect(self.clear_log)
        self.auto_scroll_cb = QPushButton("自动滚动: 开")
        self.auto_scroll_cb.setCheckable(True)
        self.auto_scroll_cb.setChecked(True)
        self.auto_scroll_cb.toggled.connect(lambda checked:
            self.auto_scroll_cb.setText("自动滚动: 开" if checked else "自动滚动: 关"))

        btn_layout.addWidget(self.clear_log_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.auto_scroll_cb)

        layout.addWidget(self.log_view)
        layout.addLayout(btn_layout)
        return page

    # ---------- 外观设置页面 ----------
    def create_appearance_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)

        color_group = QGroupBox("主题颜色")
        color_layout = QHBoxLayout(color_group)
        self.color_preview = QLabel()
        self.color_preview.setFixedSize(36, 36)
        self.color_preview.setStyleSheet(f"background-color: {self.config['theme_color']}; border-radius: 8px;")
        self.color_btn = QPushButton("选择颜色")
        self.color_btn.clicked.connect(self.choose_color)
        color_layout.addWidget(self.color_preview)
        color_layout.addWidget(self.color_btn)
        color_layout.addStretch()

        bg_group = QGroupBox("背景图片")
        bg_layout = QVBoxLayout(bg_group)
        self.bg_path_label = QLabel(self.config.get("background_image", "") or "未设置")
        self.bg_path_label.setWordWrap(True)
        bg_btn_layout = QHBoxLayout()
        self.choose_bg_btn = QPushButton("选择图片")
        self.choose_bg_btn.clicked.connect(self.choose_bg_image)
        self.clear_bg_btn = QPushButton("清除背景")
        self.clear_bg_btn.clicked.connect(self.clear_bg_image)
        bg_btn_layout.addWidget(self.choose_bg_btn)
        bg_btn_layout.addWidget(self.clear_bg_btn)
        bg_btn_layout.addStretch()
        bg_layout.addWidget(self.bg_path_label)
        bg_layout.addLayout(bg_btn_layout)

        self.apply_theme_btn = QPushButton("应用主题设置")
        self.apply_theme_btn.clicked.connect(self.apply_theme_settings)

        layout.addWidget(color_group)
        layout.addWidget(bg_group)
        layout.addWidget(self.apply_theme_btn)
        layout.addStretch()
        return page

    # ---------- 预览网站页面 ----------
    def create_preview_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)

        desc = QLabel("点击下方按钮在默认浏览器中打开悠米对话网站。")
        desc.setWordWrap(True)
        self.open_browser_btn = QPushButton("🌐 打开对话网站")
        self.open_browser_btn.clicked.connect(self.open_website)

        layout.addWidget(desc)
        layout.addWidget(self.open_browser_btn)
        layout.addStretch()
        return page

    # ---------- 导航切换 ----------
    def switch_page(self, index):
        self.stack.setCurrentIndex(index)

    # ---------- 模型选择事件 ----------
    def on_model_combo_changed(self, index):
        selected_data = self.model_combo.itemData(index)
        if selected_data == "custom":
            self.model_custom_edit.setEnabled(True)
            self.model_custom_edit.show()
        else:
            self.model_custom_edit.setEnabled(False)
            self.model_custom_edit.hide()

    # ---------- 服务控制 ----------
    def start_service(self):
        if self.process and self.process.poll() is None:
            QMessageBox.information(self, "提示", "服务已在运行中。")
            return

        port = self.config.get("port", 8000)
        cmd = [sys.executable, str(BACKEND_DIR / "main.py"), str(port)]
        try:
            self.process = subprocess.Popen(
                cmd,
                cwd=str(ROOT_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8"
            )
            self.status_label.setText(f"服务运行中 (端口 {port})")
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.restart_btn.setEnabled(True)
            self.log_view.append(f"[{datetime.now().strftime('%H:%M:%S')}] 服务已启动")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"启动失败: {str(e)}")

    def stop_service(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            self.log_view.append(f"[{datetime.now().strftime('%H:%M:%S')}] 服务已停止")
        self.status_label.setText("服务未运行")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.restart_btn.setEnabled(False)

    def restart_service(self):
        self.stop_service()
        self.start_service()

    # ---------- 配置保存 ----------
    def save_current_config(self):
        try:
            port = int(self.port_edit.text())
            selected_data = self.model_combo.itemData(self.model_combo.currentIndex())
            if selected_data == "custom":
                model = self.model_custom_edit.text().strip()
                if not model:
                    raise ValueError("自定义模型不能为空")
            else:
                model = selected_data
            
            self.config["port"] = port
            self.config["model"] = model
            save_config(self.config)
            QMessageBox.information(self, "成功", "配置已保存。需要重启服务生效。")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存配置失败: {str(e)}")

    # ---------- 日志监控 ----------
    def start_log_timer(self):
        self.log_timer = QTimer()
        self.log_timer.timeout.connect(self.update_log)
        self.log_timer.start(1000)
        self.log_position = 0

    def update_log(self):
        if not LOG_FILE.exists():
            return
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                f.seek(self.log_position)
                new_lines = f.read()
                if new_lines:
                    self.log_view.insertPlainText(new_lines)
                    if self.auto_scroll_cb.isChecked():
                        scrollbar = self.log_view.verticalScrollBar()
                        scrollbar.setValue(scrollbar.maximum())
                self.log_position = f.tell()
        except Exception:
            pass

    def clear_log(self):
        self.log_view.clear()
        try:
            open(LOG_FILE, "w").close()
            self.log_position = 0
        except:
            pass

    # ---------- 外观设置 ----------
    def choose_color(self):
        color = QColorDialog.getColor(QColor(self.config["theme_color"]), self, "选择主题颜色")
        if color.isValid():
            self.config["theme_color"] = color.name()
            self.color_preview.setStyleSheet(f"background-color: {color.name()}; border-radius: 8px;")

    def choose_bg_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择背景图片", "", "图片文件 (*.png *.jpg *.jpeg *.bmp)")
        if path:
            self.config["background_image"] = path
            self.bg_path_label.setText(path)

    def clear_bg_image(self):
        self.config["background_image"] = ""
        self.bg_path_label.setText("未设置")

    def apply_theme_settings(self):
        save_config(self.config)
        self.apply_theme()
        QMessageBox.information(self, "成功", "主题设置已应用并保存。")

    def apply_theme(self):
        color = self.config["theme_color"]
        bg_image = self.config.get("background_image", "")

        base_style = f"""
            QMainWindow {{
                background-color: #1a1a2e;
            }}
            QWidget {{
                font-family: "Segoe UI", "Microsoft YaHei";
                font-size: 13px;
                color: #e0e0e0;
            }}
            QListWidget {{
                background: rgba(30, 30, 46, 0.9);
                border: 1px solid rgba({self.hex_to_rgba(color, 0.3)});
                border-radius: 12px;
                padding: 6px 4px;
                color: #e0e0e0;
            }}
            QListWidget::item {{
                padding: 12px 16px;
                margin: 3px 6px;
                border-radius: 10px;
            }}
            QListWidget::item:selected {{
                background: {color};
                color: #ffffff;
            }}
            QListWidget::item:hover {{
                background: rgba({self.hex_to_rgba(color, 0.25)});
            }}
            QPushButton {{
                background: {color};
                color: #ffffff;
                border: none;
                border-radius: 10px;
                padding: 10px 18px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {self.lighten_color(color)};
            }}
            QPushButton:pressed {{
                background: {color};
            }}
            QPushButton:disabled {{
                background: rgba(80, 80, 100, 0.6);
                color: #888899;
            }}
            QLineEdit, QTextEdit, QComboBox {{
                background: rgba(30, 30, 46, 0.9);
                border: 1px solid rgba({self.hex_to_rgba(color, 0.4)});
                border-radius: 10px;
                padding: 8px;
                color: #e0e0e0;
                min-height: 34px;
            }}
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
                border-color: {color};
                outline: none;
            }}
            QComboBox::drop-down {{
                border: none;
                background: rgba(30, 30, 46, 0.9);
            }}
            QComboBox::down-arrow {{
                color: {color};
            }}
            QComboBox QAbstractItemView {{
                background: rgba(30, 30, 46, 0.98);
                border: 1px solid rgba({self.hex_to_rgba(color, 0.4)});
                border-radius: 10px;
                color: #e0e0e0;
            }}
            QComboBox QAbstractItemView::item {{
                padding: 10px 14px;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background: rgba({self.hex_to_rgba(color, 0.25)});
            }}
            QComboBox QAbstractItemView::item:selected {{
                background: {color};
                color: #ffffff;
            }}
            QTabWidget::pane {{
                border: 1px solid rgba({self.hex_to_rgba(color, 0.3)});
                background: rgba(25, 25, 40, 0.9);
                border-radius: 12px;
            }}
            QTabBar::tab {{
                background: rgba(40, 40, 60, 0.6);
                color: #aaaacc;
                padding: 8px 20px;
                margin-right: 2px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }}
            QTabBar::tab:selected {{
                background: rgba(30, 30, 46, 0.95);
                color: #e0e0e0;
                border-bottom: 2px solid {color};
            }}
            QTabBar::tab:hover {{
                background: rgba({self.hex_to_rgba(color, 0.15)});
            }}
            QGroupBox {{
                border: 1px solid rgba({self.hex_to_rgba(color, 0.3)});
                border-radius: 12px;
                margin-top: 14px;
                padding-top: 18px;
                color: #e0e0e0;
                background: rgba(30, 30, 46, 0.3);
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 8px;
                color: {color};
                background: #1a1a2e;
            }}
            QLabel {{
                color: #e0e0e0;
            }}
            QStatusBar {{
                background: rgba(20, 20, 35, 0.9);
                color: #aaaacc;
                border-top: 1px solid rgba({self.hex_to_rgba(color, 0.2)});
            }}
            QMessageBox {{
                background-color: rgba(30, 30, 46, 0.95);
                border: 1px solid rgba({self.hex_to_rgba(color, 0.4)});
                border-radius: 12px;
                color: #e0e0e0;
            }}
            QMessageBox QLabel {{
                color: #e0e0e0;
            }}
            QMessageBox QPushButton {{
                background: {color};
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 6px 16px;
            }}
            QMessageBox QPushButton:hover {{
                background: {self.lighten_color(color)};
            }}
        """

        if bg_image and os.path.exists(bg_image):
            bg_style = f"""
                QMainWindow {{
                    background-image: url({bg_image});
                    background-position: center;
                    background-repeat: no-repeat;
                    background-attachment: fixed;
                    background-size: cover;
                }}
            """
            base_style += bg_style

        self.setStyleSheet(base_style)

    @staticmethod
    def hex_to_rgba(hex_color, alpha):
        hex_color = hex_color.lstrip('#')
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        return f"{r}, {g}, {b}, {alpha}"

    @staticmethod
    def lighten_color(hex_color, factor=0.2):
        hex_color = hex_color.lstrip('#')
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        r = min(255, int(r + (255 - r) * factor))
        g = min(255, int(g + (255 - g) * factor))
        b = min(255, int(b + (255 - b) * factor))
        return f"#{r:02x}{g:02x}{b:02x}"

    # ---------- 打开网站 ----------
    def open_website(self):
        port = self.config["port"]
        url = f"http://localhost:{port}"
        webbrowser.open(url)

    # ---------- 关闭事件 ----------
    def closeEvent(self, event):
        if self.process and self.process.poll() is None:
            reply = QMessageBox.question(
                self, "确认退出",
                "FastAPI 服务正在运行，是否停止并退出？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.stop_service()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


# ---------------------------- 入口 ----------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))
    window = YumiManager()
    window.show()
    sys.exit(app.exec())