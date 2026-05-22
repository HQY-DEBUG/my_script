"""
batch_rename.py  --  批量文件重命名工具
版本    : v1.0
日期    : 2026/05/22

修改记录:
    v1.0  创建文件，实现批量重命名、顺序创建、前缀/后缀、字符替换、预览功能
"""

import os
import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QListWidget, QListWidgetItem,
    QTableWidget, QTableWidgetItem, QTabWidget, QFileDialog,
    QComboBox, QSpinBox, QGroupBox, QSplitter, QAbstractItemView,
    QMessageBox, QHeaderView, QCheckBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QIcon


# ---- 重命名执行线程 ----//
class RenameWorker(QThread):
    """
    后台执行重命名/创建操作，避免阻塞 GUI。

    Attributes:
        tasks: [(旧路径, 新路径), ...]
        finished: 完成信号，携带成功数和失败列表
        error: 错误信号
    """
    finished = pyqtSignal(int, list)    # 成功数, 失败列表
    progress = pyqtSignal(int)          # 当前进度

    def __init__(self, tasks, parent=None):
        """
        Args:
            tasks: [(old_path, new_path), ...]
        """
        super().__init__(parent)
        self._tasks = tasks

    def run(self):
        success = 0
        failed = []
        for i, (old_path, new_path) in enumerate(self._tasks):
            try:
                os.rename(old_path, new_path)
                success += 1
            except Exception as e:
                failed.append((old_path, str(e)))
            self.progress.emit(i + 1)
        self.finished.emit(success, failed)


# ---- 创建文件/文件夹线程 ----//
class CreateWorker(QThread):
    """后台执行顺序文件/文件夹创建。"""

    finished = pyqtSignal(int, list)
    progress = pyqtSignal(int)

    def __init__(self, target_dir, name_prefix, start, count, create_type, ext, parent=None):
        """
        Args:
            target_dir:  目标目录
            name_prefix: 名称前缀
            start:       起始编号
            count:       创建数量
            create_type: 'file' 或 'folder'
            ext:         文件扩展名（create_type='file' 时有效）
        """
        super().__init__(parent)
        self._dir = target_dir
        self._prefix = name_prefix
        self._start = start
        self._count = count
        self._type = create_type
        self._ext = ext

    def run(self):
        success = 0
        failed = []
        for i in range(self._count):
            num = self._start + i
            name = f"{self._prefix}{num:0>3d}"
            if self._type == 'file':
                name += self._ext if self._ext.startswith('.') else ('.' + self._ext)
            path = os.path.join(self._dir, name)
            try:
                if self._type == 'folder':
                    os.makedirs(path, exist_ok=True)
                else:
                    open(path, 'a').close()
                success += 1
            except Exception as e:
                failed.append((path, str(e)))
            self.progress.emit(i + 1)
        self.finished.emit(success, failed)


# ---- 主窗口 ----//
class BatchRenameWindow(QMainWindow):
    """
    批量重命名工具主窗口。

    Attributes:
        _current_dir: 当前选中的目录路径
        _worker:      后台工作线程（重命名/创建）
    """

    def __init__(self):
        super().__init__()
        self._current_dir = ''
        self._worker = None
        self._initUI()

    def _initUI(self):
        """初始化界面布局。"""
        self.setWindowTitle('批量重命名工具 v1.0')
        self.setMinimumSize(900, 650)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # ---- 目录选择区 ----//
        dir_group = QGroupBox('目标目录')
        dir_layout = QHBoxLayout(dir_group)
        self.m_dirEdit = QLineEdit()
        self.m_dirEdit.setPlaceholderText('选择要操作的文件夹...')
        self.m_dirEdit.setReadOnly(True)
        m_browseBtn = QPushButton('浏览')
        m_browseBtn.setFixedWidth(70)
        m_browseBtn.clicked.connect(self.onBrowseDir)
        m_refreshBtn = QPushButton('刷新')
        m_refreshBtn.setFixedWidth(70)
        m_refreshBtn.clicked.connect(self.onRefreshFiles)
        dir_layout.addWidget(self.m_dirEdit)
        dir_layout.addWidget(m_browseBtn)
        dir_layout.addWidget(m_refreshBtn)
        main_layout.addWidget(dir_group)

        # ---- 主体区（文件列表 + 操作面板）----//
        splitter = QSplitter(Qt.Horizontal)

        # 左侧：文件列表
        file_group = QGroupBox('文件列表（多选）')
        file_layout = QVBoxLayout(file_group)
        self.m_fileList = QListWidget()
        self.m_fileList.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.m_fileList.itemSelectionChanged.connect(self.onSelectionChanged)
        select_layout = QHBoxLayout()
        m_selectAllBtn = QPushButton('全选')
        m_selectAllBtn.clicked.connect(self.m_fileList.selectAll)
        m_clearSelBtn = QPushButton('清除选择')
        m_clearSelBtn.clicked.connect(self.m_fileList.clearSelection)
        self.m_selCountLabel = QLabel('已选 0 个')
        select_layout.addWidget(m_selectAllBtn)
        select_layout.addWidget(m_clearSelBtn)
        select_layout.addStretch()
        select_layout.addWidget(self.m_selCountLabel)
        file_layout.addWidget(self.m_fileList)
        file_layout.addLayout(select_layout)
        splitter.addWidget(file_group)

        # 右侧：操作 Tab
        op_widget = QWidget()
        op_layout = QVBoxLayout(op_widget)
        op_layout.setContentsMargins(0, 0, 0, 0)
        self.m_tabWidget = QTabWidget()
        self.m_tabWidget.addTab(self._buildRenameTab(), '重命名操作')
        self.m_tabWidget.addTab(self._buildCreateTab(), '顺序创建')
        op_layout.addWidget(self.m_tabWidget)
        splitter.addWidget(op_widget)
        splitter.setSizes([380, 480])
        main_layout.addWidget(splitter, 3)

        # ---- 预览区 ----//
        preview_group = QGroupBox('重命名预览')
        preview_layout = QVBoxLayout(preview_group)
        self.m_previewTable = QTableWidget(0, 2)
        self.m_previewTable.setHorizontalHeaderLabels(['原文件名', '新文件名'])
        self.m_previewTable.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.m_previewTable.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.m_previewTable.setAlternatingRowColors(True)
        preview_layout.addWidget(self.m_previewTable)
        main_layout.addWidget(preview_group, 2)

        # ---- 底部操作按钮 ----//
        btn_layout = QHBoxLayout()
        self.m_statusLabel = QLabel('就绪')
        m_previewBtn = QPushButton('预览')
        m_previewBtn.setFixedWidth(90)
        m_previewBtn.clicked.connect(self.onPreview)
        self.m_executeBtn = QPushButton('执行')
        self.m_executeBtn.setFixedWidth(90)
        self.m_executeBtn.clicked.connect(self.onExecute)
        self.m_executeBtn.setStyleSheet('QPushButton { background-color: #0078d4; color: white; font-weight: bold; }')
        btn_layout.addWidget(self.m_statusLabel)
        btn_layout.addStretch()
        btn_layout.addWidget(m_previewBtn)
        btn_layout.addWidget(self.m_executeBtn)
        main_layout.addLayout(btn_layout)

    def _buildRenameTab(self):
        """构建重命名操作 Tab 页。"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)

        # 前缀/后缀
        pf_group = QGroupBox('前缀 / 后缀')
        pf_layout = QHBoxLayout(pf_group)
        pf_layout.addWidget(QLabel('前缀:'))
        self.m_prefixEdit = QLineEdit()
        self.m_prefixEdit.setPlaceholderText('留空则不添加')
        pf_layout.addWidget(self.m_prefixEdit)
        pf_layout.addWidget(QLabel('后缀:'))
        self.m_suffixEdit = QLineEdit()
        self.m_suffixEdit.setPlaceholderText('留空则不添加（在扩展名前）')
        pf_layout.addWidget(self.m_suffixEdit)
        layout.addWidget(pf_group)

        # 字符替换
        rep_group = QGroupBox('字符替换')
        rep_layout = QHBoxLayout(rep_group)
        rep_layout.addWidget(QLabel('查找:'))
        self.m_findEdit = QLineEdit()
        self.m_findEdit.setPlaceholderText('要替换的文本')
        rep_layout.addWidget(self.m_findEdit)
        rep_layout.addWidget(QLabel('替换为:'))
        self.m_replaceEdit = QLineEdit()
        self.m_replaceEdit.setPlaceholderText('新文本（留空则删除）')
        rep_layout.addWidget(self.m_replaceEdit)
        self.m_caseCheckBox = QCheckBox('区分大小写')
        self.m_caseCheckBox.setChecked(True)
        rep_layout.addWidget(self.m_caseCheckBox)
        layout.addWidget(rep_group)

        # 编号
        num_group = QGroupBox('添加顺序编号')
        num_layout = QHBoxLayout(num_group)
        self.m_addNumCheckBox = QCheckBox('启用编号')
        num_layout.addWidget(self.m_addNumCheckBox)
        num_layout.addWidget(QLabel('起始:'))
        self.m_numStartSpin = QSpinBox()
        self.m_numStartSpin.setRange(0, 99999)
        self.m_numStartSpin.setValue(1)
        num_layout.addWidget(self.m_numStartSpin)
        num_layout.addWidget(QLabel('位数:'))
        self.m_numWidthSpin = QSpinBox()
        self.m_numWidthSpin.setRange(1, 6)
        self.m_numWidthSpin.setValue(3)
        num_layout.addWidget(self.m_numWidthSpin)
        num_layout.addWidget(QLabel('位置:'))
        self.m_numPosCombo = QComboBox()
        self.m_numPosCombo.addItems(['文件名前', '文件名后（扩展名前）'])
        num_layout.addWidget(self.m_numPosCombo)
        num_layout.addStretch()
        layout.addWidget(num_group)

        # 扩展名处理
        ext_group = QGroupBox('扩展名处理')
        ext_layout = QHBoxLayout(ext_group)
        self.m_extActionCombo = QComboBox()
        self.m_extActionCombo.addItems(['不修改', '全部小写', '全部大写'])
        ext_layout.addWidget(QLabel('扩展名:'))
        ext_layout.addWidget(self.m_extActionCombo)
        ext_layout.addStretch()
        layout.addWidget(ext_group)

        layout.addStretch()
        return widget

    def _buildCreateTab(self):
        """构建顺序创建 Tab 页。"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)

        cfg_group = QGroupBox('创建配置')
        cfg_layout = QVBoxLayout(cfg_group)

        # 类型选择
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel('创建类型:'))
        self.m_createTypeCombo = QComboBox()
        self.m_createTypeCombo.addItems(['文件夹', '文件'])
        self.m_createTypeCombo.currentTextChanged.connect(self._onCreateTypeChanged)
        type_layout.addWidget(self.m_createTypeCombo)
        type_layout.addStretch()
        cfg_layout.addLayout(type_layout)

        # 名称前缀
        prefix_layout = QHBoxLayout()
        prefix_layout.addWidget(QLabel('名称前缀:'))
        self.m_createPrefixEdit = QLineEdit()
        self.m_createPrefixEdit.setPlaceholderText('例如 chapter_')
        prefix_layout.addWidget(self.m_createPrefixEdit)
        cfg_layout.addLayout(prefix_layout)

        # 扩展名（仅文件模式）
        self.m_extRow = QWidget()
        ext_layout = QHBoxLayout(self.m_extRow)
        ext_layout.setContentsMargins(0, 0, 0, 0)
        ext_layout.addWidget(QLabel('文件扩展名:'))
        self.m_createExtEdit = QLineEdit()
        self.m_createExtEdit.setPlaceholderText('.txt')
        self.m_createExtEdit.setText('.txt')
        ext_layout.addWidget(self.m_createExtEdit)
        ext_layout.addStretch()
        self.m_extRow.setVisible(False)
        cfg_layout.addWidget(self.m_extRow)

        # 起始/数量
        num_layout = QHBoxLayout()
        num_layout.addWidget(QLabel('起始编号:'))
        self.m_createStartSpin = QSpinBox()
        self.m_createStartSpin.setRange(0, 99999)
        self.m_createStartSpin.setValue(1)
        num_layout.addWidget(self.m_createStartSpin)
        num_layout.addWidget(QLabel('创建数量:'))
        self.m_createCountSpin = QSpinBox()
        self.m_createCountSpin.setRange(1, 999)
        self.m_createCountSpin.setValue(10)
        num_layout.addWidget(self.m_createCountSpin)
        num_layout.addStretch()
        cfg_layout.addLayout(num_layout)

        layout.addWidget(cfg_group)

        # 预览提示
        self.m_createPreviewLabel = QLabel('预览: 001, 002, ...')
        self.m_createPreviewLabel.setStyleSheet('color: gray;')
        layout.addWidget(self.m_createPreviewLabel)

        # 创建按钮
        create_btn = QPushButton('开始创建')
        create_btn.setStyleSheet('QPushButton { background-color: #107c10; color: white; font-weight: bold; }')
        create_btn.clicked.connect(self.onStartCreate)
        layout.addWidget(create_btn)

        # 连接预览更新
        self.m_createPrefixEdit.textChanged.connect(self._updateCreatePreview)
        self.m_createStartSpin.valueChanged.connect(self._updateCreatePreview)
        self.m_createCountSpin.valueChanged.connect(self._updateCreatePreview)
        self.m_createExtEdit.textChanged.connect(self._updateCreatePreview)

        layout.addStretch()
        return widget

    # ---- 槽函数 ----//
    def onBrowseDir(self):
        """选择目标目录。"""
        directory = QFileDialog.getExistingDirectory(self, '选择目录', self._current_dir or os.path.expanduser('~'))
        if directory:
            self._current_dir = directory
            self.m_dirEdit.setText(directory)
            self.onRefreshFiles()

    def onRefreshFiles(self):
        """刷新文件列表。"""
        self.m_fileList.clear()
        if not self._current_dir or not os.path.isdir(self._current_dir):
            return
        entries = sorted(os.listdir(self._current_dir))
        for name in entries:
            item = QListWidgetItem(name)
            full = os.path.join(self._current_dir, name)
            if os.path.isdir(full):
                item.setForeground(QColor('#0078d4'))   # 文件夹蓝色
            self.m_fileList.addItem(item)
        self.m_statusLabel.setText(f'已加载 {len(entries)} 个条目')

    def onSelectionChanged(self):
        """更新已选计数。"""
        count = len(self.m_fileList.selectedItems())
        self.m_selCountLabel.setText(f'已选 {count} 个')

    def onPreview(self):
        """计算并显示重命名预览。"""
        selected = self.m_fileList.selectedItems()
        if not selected:
            QMessageBox.information(self, '提示', '请先在文件列表中选择要重命名的文件/文件夹')
            return
        tasks = self._buildRenameTasks(selected)
        self._showPreview(tasks)

    def onExecute(self):
        """执行重命名。"""
        selected = self.m_fileList.selectedItems()
        if not selected:
            QMessageBox.information(self, '提示', '请先选择文件/文件夹')
            return
        tasks = self._buildRenameTasks(selected)
        if not tasks:
            QMessageBox.information(self, '提示', '没有需要重命名的文件（新旧名称相同）')
            return

        reply = QMessageBox.question(self, '确认', f'即将重命名 {len(tasks)} 个文件，确认执行？',
                                     QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return

        self.m_executeBtn.setEnabled(False)
        self.m_statusLabel.setText('正在执行...')
        self._worker = RenameWorker(tasks, self)
        self._worker.finished.connect(self.onRenameFinished)
        self._worker.start()

    def onRenameFinished(self, success, failed):
        """重命名完成后更新 UI。"""
        self.m_executeBtn.setEnabled(True)
        if failed:
            msg = f'完成：成功 {success} 个，失败 {len(failed)} 个\n\n失败列表：\n'
            msg += '\n'.join(f'{os.path.basename(p)}: {e}' for p, e in failed[:10])
            QMessageBox.warning(self, '部分失败', msg)
        else:
            self.m_statusLabel.setText(f'完成：成功重命名 {success} 个文件')
        self.onRefreshFiles()
        self.m_previewTable.setRowCount(0)

    def onStartCreate(self):
        """执行顺序创建。"""
        if not self._current_dir:
            QMessageBox.warning(self, '警告', '请先选择目标目录')
            return

        create_type = 'folder' if self.m_createTypeCombo.currentText() == '文件夹' else 'file'
        prefix = self.m_createPrefixEdit.text()
        start = self.m_createStartSpin.value()
        count = self.m_createCountSpin.value()
        ext = self.m_createExtEdit.text() if create_type == 'file' else ''

        reply = QMessageBox.question(self, '确认',
                                     f'将在\n{self._current_dir}\n创建 {count} 个{"文件夹" if create_type == "folder" else "文件"}，确认？',
                                     QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return

        self._worker = CreateWorker(self._current_dir, prefix, start, count, create_type, ext, self)
        self._worker.finished.connect(self.onCreateFinished)
        self._worker.start()
        self.m_statusLabel.setText('创建中...')

    def onCreateFinished(self, success, failed):
        """创建完成后更新 UI。"""
        if failed:
            QMessageBox.warning(self, '部分失败', f'成功 {success}，失败 {len(failed)} 个')
        else:
            self.m_statusLabel.setText(f'完成：成功创建 {success} 个')
        self.onRefreshFiles()

    def _onCreateTypeChanged(self, text):
        """切换创建类型时显示/隐藏扩展名行。"""
        self.m_extRow.setVisible(text == '文件')
        self._updateCreatePreview()

    def _updateCreatePreview(self):
        """更新顺序创建预览文本。"""
        prefix = self.m_createPrefixEdit.text()
        start = self.m_createStartSpin.value()
        count = self.m_createCountSpin.value()
        is_file = self.m_createTypeCombo.currentText() == '文件'
        ext = self.m_createExtEdit.text() if is_file else ''
        if not ext.startswith('.') and ext:
            ext = '.' + ext

        samples = []
        for i in range(min(3, count)):
            name = f"{prefix}{(start + i):0>3d}{ext}"
            samples.append(name)
        if count > 3:
            samples.append('...')
        self.m_createPreviewLabel.setText('预览: ' + ',  '.join(samples))

    # ---- 核心逻辑 ----//
    def _buildRenameTasks(self, selected_items):
        """
        根据当前操作配置计算重命名任务列表。

        Args:
            selected_items: QListWidget 已选 items

        Returns:
            [(old_path, new_path), ...] 仅包含有变化的条目
        """
        tasks = []
        prefix = self.m_prefixEdit.text()
        suffix = self.m_suffixEdit.text()
        find_text = self.m_findEdit.text()
        replace_text = self.m_replaceEdit.text()
        case_sensitive = self.m_caseCheckBox.isChecked()
        add_num = self.m_addNumCheckBox.isChecked()
        num_start = self.m_numStartSpin.value()
        num_width = self.m_numWidthSpin.value()
        num_pos = self.m_numPosCombo.currentIndex()   # 0=前, 1=后
        ext_action = self.m_extActionCombo.currentIndex()  # 0=不变, 1=小写, 2=大写

        for idx, item in enumerate(selected_items):
            old_name = item.text()
            base, ext = os.path.splitext(old_name)

            # 扩展名处理
            if ext_action == 1:
                ext = ext.lower()
            elif ext_action == 2:
                ext = ext.upper()

            # 字符替换（仅作用于 base 部分）
            if find_text:
                if case_sensitive:
                    base = base.replace(find_text, replace_text)
                else:
                    import re
                    base = re.sub(re.escape(find_text), replace_text, base, flags=re.IGNORECASE)

            # 编号
            if add_num:
                num_str = str(num_start + idx).zfill(num_width)
                if num_pos == 0:
                    base = num_str + base
                else:
                    base = base + num_str

            # 前缀/后缀（作用于 base）
            base = prefix + base + suffix

            new_name = base + ext
            if new_name != old_name:
                old_path = os.path.join(self._current_dir, old_name)
                new_path = os.path.join(self._current_dir, new_name)
                tasks.append((old_path, new_path))

        return tasks

    def _showPreview(self, tasks):
        """
        将重命名任务填入预览表格。

        Args:
            tasks: [(old_path, new_path), ...]
        """
        self.m_previewTable.setRowCount(len(tasks))
        for row, (old_path, new_path) in enumerate(tasks):
            old_item = QTableWidgetItem(os.path.basename(old_path))
            new_item = QTableWidgetItem(os.path.basename(new_path))
            new_item.setForeground(QColor('#107c10'))   # 新名称绿色
            self.m_previewTable.setItem(row, 0, old_item)
            self.m_previewTable.setItem(row, 1, new_item)
        self.m_statusLabel.setText(f'预览：{len(tasks)} 个文件将被重命名')


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    win = BatchRenameWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
