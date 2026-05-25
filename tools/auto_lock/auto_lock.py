"""
auto_lock.py  --  无操作自动锁屏工具（系统托盘）
版本    : v1.0
日期    : 2026/05/25

修改记录:
    v1.0  创建文件，实现鼠标/键盘无操作 N 分钟后自动锁屏，系统托盘驻留
"""

import sys
import ctypes
import ctypes.wintypes
from PyQt5.QtWidgets import (
    QApplication, QSystemTrayIcon, QMenu, QAction,
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QSpinBox, QPushButton, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor, QPen


# ---- 默认超时时间（分钟）----//
DEFAULT_TIMEOUT_MIN = 10


# ---- Windows API 封装 ----//
class _LASTINPUTINFO(ctypes.Structure):
    """Windows LASTINPUTINFO 结构体，用于查询系统最后输入时间。"""
    _fields_ = [
        ("cbSize", ctypes.wintypes.UINT),
        ("dwTime", ctypes.wintypes.DWORD),
    ]


def get_idle_seconds():
    """
    获取系统自上次鼠标/键盘输入起经过的空闲秒数。

    Returns:
        float: 空闲秒数
    """
    lii = _LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(_LASTINPUTINFO)
    ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
    # GetTickCount 返回毫秒，减去最后输入时间得到空闲时长
    tick_now = ctypes.windll.kernel32.GetTickCount()
    idle_ms = tick_now - lii.dwTime
    return idle_ms / 1000.0


def lock_workstation():
    """调用 Windows API 锁定工作站。"""
    ctypes.windll.user32.LockWorkStation()


# ---- 托盘图标生成 ----//
def _make_tray_icon(color: str) -> QIcon:
    """
    生成指定颜色的锁形托盘图标（纯几何绘制，无 emoji 依赖）。

    Args:
        color: Qt 颜色名称字符串，如 "#4CAF50"

    Returns:
        QIcon 对象
    """
    size = 64
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    # 背景圆
    painter.setBrush(QColor(color))
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(2, 2, size - 4, size - 4)

    # 锁体（白色圆角矩形）
    painter.setBrush(QColor("white"))
    painter.drawRoundedRect(18, 32, 28, 22, 4, 4)

    # 锁梁（白色弧形，用粗笔描边）
    pen = QPen(QColor("white"), 5)
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    painter.drawArc(20, 16, 24, 26, 0 * 16, 180 * 16)

    # 锁孔（背景色小圆）
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(color))
    painter.drawEllipse(28, 37, 8, 8)

    painter.end()
    return QIcon(pixmap)


# ---- 设置对话框 ----//
class SettingsDialog(QDialog):
    """
    超时时间设置对话框。

    Attributes:
        _spin: 分钟数输入框
    """

    def __init__(self, current_min: int, parent=None):
        """
        Args:
            current_min: 当前超时分钟数
            parent: 父窗口
        """
        super().__init__(parent)
        self.setWindowTitle("自动锁屏设置")
        self.setFixedSize(280, 130)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(12)

        row = QHBoxLayout()
        row.addWidget(QLabel("无操作超时时间："))
        self._spin = QSpinBox()
        self._spin.setRange(1, 120)
        self._spin.setValue(current_min)
        self._spin.setSuffix(" 分钟")
        row.addWidget(self._spin)
        layout.addLayout(row)

        btns = QHBoxLayout()
        btns.addStretch()
        ok_btn = QPushButton("确定")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(ok_btn)
        btns.addWidget(cancel_btn)
        layout.addLayout(btns)

    def get_timeout(self) -> int:
        """
        Returns:
            int: 用户设置的超时分钟数
        """
        return self._spin.value()


# ---- 主监控类 ----//
class AutoLockApp:
    """
    自动锁屏应用程序，驻留系统托盘，定时检测空闲时间。

    Attributes:
        _timeout_sec: 触发锁屏的空闲阈值（秒）
        _tray: 系统托盘图标
        _timer: 周期检测定时器
    """

    _CHECK_INTERVAL_MS = 5000   # 检测间隔 5 秒

    def __init__(self, app: QApplication):
        self._app = app
        self._timeout_sec = DEFAULT_TIMEOUT_MIN * 60
        self._locked_this_idle = False             # 防止本次空闲重复锁屏

        self._build_tray()
        self._timer = QTimer()
        self._timer.timeout.connect(self._on_tick)
        self._timer.start(self._CHECK_INTERVAL_MS)

    # ---- 托盘构建 ----//
    def _build_tray(self):
        """初始化系统托盘图标与右键菜单。"""
        self._icon_active   = _make_tray_icon("#4CAF50")   # 绿色：正常监控
        self._icon_warning  = _make_tray_icon("#FF9800")   # 橙色：即将锁屏

        self._tray = QSystemTrayIcon(self._icon_active)
        self._tray.setToolTip("自动锁屏 — 监控中")

        menu = QMenu()
        self._status_action = QAction("空闲: 0 秒")
        self._status_action.setEnabled(False)
        menu.addAction(self._status_action)
        menu.addSeparator()

        lock_now = QAction("立即锁屏")
        lock_now.triggered.connect(self._lock_now)
        menu.addAction(lock_now)

        settings_action = QAction("设置超时时间…")
        settings_action.triggered.connect(self._open_settings)
        menu.addAction(settings_action)

        menu.addSeparator()
        quit_action = QAction("退出")
        quit_action.triggered.connect(self._app.quit)
        menu.addAction(quit_action)

        self._tray.setContextMenu(menu)
        self._tray.show()
        # 延迟刷新确保 Windows 托盘区域完成初始化
        QTimer.singleShot(500, lambda: self._tray.show())

    # ---- 定时检测 ----//
    def _on_tick(self):
        """每隔 CHECK_INTERVAL_MS 毫秒执行一次空闲检测。"""
        idle_sec = get_idle_seconds()
        remaining = max(0, self._timeout_sec - idle_sec)

        # 更新托盘提示与状态菜单
        if remaining > 60:
            tip = f"自动锁屏 — 还剩 {int(remaining // 60)} 分 {int(remaining % 60)} 秒"
        else:
            tip = f"自动锁屏 — 还剩 {int(remaining)} 秒"
        self._tray.setToolTip(tip)
        self._status_action.setText(f"空闲: {int(idle_sec)} 秒 / 阈值: {self._timeout_sec} 秒")

        # 剩余不足 60 秒时切换为警告图标
        if remaining <= 60:
            self._tray.setIcon(self._icon_warning)
        else:
            self._tray.setIcon(self._icon_active)

        # 达到阈值且本次空闲尚未触发过锁屏
        if idle_sec >= self._timeout_sec and not self._locked_this_idle:
            self._locked_this_idle = True
            lock_workstation()

        # 空闲时间缩短说明用户重新活跃，重置标志
        if idle_sec < self._CHECK_INTERVAL_MS / 1000 * 2:
            self._locked_this_idle = False

    # ---- 立即锁屏 ----//
    def _lock_now(self):
        """菜单项：立即锁定工作站。"""
        self._locked_this_idle = True
        lock_workstation()

    # ---- 打开设置对话框 ----//
    def _open_settings(self):
        """弹出超时时间设置对话框，保存用户修改。"""
        dlg = SettingsDialog(self._timeout_sec // 60)
        if dlg.exec_() == QDialog.Accepted:
            self._timeout_sec = dlg.get_timeout() * 60
            self._locked_this_idle = False


# ---- 入口 ----//
def main():
    import traceback, os
    log_path = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "auto_lock_error.log")
    try:
        # 单例互斥锁，防止重复启动
        mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "Global\\AutoLockSingleInstance")
        if ctypes.windll.kernel32.GetLastError() == 183:    # ERROR_ALREADY_EXISTS
            ctypes.windll.kernel32.CloseHandle(mutex)
            return

        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)    # 关闭所有窗口后不退出

        if not QSystemTrayIcon.isSystemTrayAvailable():
            QMessageBox.critical(None, "错误", "系统不支持托盘图标，无法运行。")
            sys.exit(1)

        lock_app = AutoLockApp(app)
        sys.exit(app.exec_())
    except Exception:
        with open(log_path, "w", encoding="utf-8") as f:
            traceback.print_exc(file=f)
        raise


if __name__ == "__main__":
    main()
