import sys
import re
import subprocess
import os
from PyQt5.QtCore import Qt, QDir, QRegExp, QSize, QFileInfo, QProcess
from PyQt5.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat, QPainter, QTextFormat, QPalette, QTextCursor, QFont, QKeySequence
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QSplitter, QTreeView, QPlainTextEdit,
    QTabWidget, QFileSystemModel, QVBoxLayout, QWidget, QAction,
    QFileDialog, QMessageBox, QInputDialog, QLineEdit, QDialog, QLabel, QPushButton,
    QHBoxLayout, QTextEdit, QCompleter, QListView, QMenu, QTextBrowser, QListWidget
)

class SearchDialog(QDialog):
    def __init__(self, editor):
        super().__init__()
        self.editor = editor
        self.setWindowTitle("搜尋文字")
        layout = QVBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("輸入要搜尋的文字…")
        self.result_list = QListWidget()
        self.search_button = QPushButton("搜尋")
        self.search_button.clicked.connect(self.find_text)
        layout.addWidget(QLabel("關鍵字："))
        layout.addWidget(self.search_input)
        layout.addWidget(self.search_button)
        layout.addWidget(self.result_list)
        self.setLayout(layout)

    def find_text(self):
        self.result_list.clear()
        keyword = self.search_input.text()
        if not keyword:
            return
        parent = self.parentWidget()
        if not parent:
            parent = self.editor.parentWidget()
        if not hasattr(parent, 'parentWidget'):
            return
        main_window = parent.parentWidget()
        if not main_window:
            return
        for tab_index in range(main_window.tabs.count()):
            tab = main_window.tabs.widget(tab_index)
            editor = main_window.editor_widgets.get(tab)
            if editor:
                lines = editor.toPlainText().split('\n')
                for line_num, line in enumerate(lines, start=1):
                    if keyword in line:
                        file_name = getattr(tab, 'file_path', '未命名')
                        file_name = QFileInfo(file_name).fileName()
                        item_text = f"{file_name}: 第 {line_num} 行: {line.strip()}"
                        item = QListWidget.QListWidgetItem(item_text)
                        item.setData(Qt.UserRole, (tab_index, line_num))
                        self.result_list.addItem(item)
        self.result_list.itemClicked.connect(lambda item: self.go_to_result(item, main_window))

    def go_to_result(self, item, main_window):
        tab_index, line_num = item.data(Qt.UserRole)
        main_window.tabs.setCurrentIndex(tab_index)
        editor = main_window.editor_widgets[main_window.tabs.widget(tab_index)]
        cursor = editor.textCursor()
        cursor.movePosition(QTextCursor.Start)
        for _ in range(line_num - 1):
            cursor.movePosition(QTextCursor.Down)
        editor.setTextCursor(cursor)
        editor.setFocus()

class ReplaceDialog(QDialog):
    def __init__(self, editor):
        super().__init__()
        self.editor = editor
        self.setWindowTitle("取代文字")
        layout = QVBoxLayout()
        self.search_input = QLineEdit()
        self.replace_input = QLineEdit()
        self.replace_button = QPushButton("全部取代")
        self.replace_button.clicked.connect(self.replace_text)
        layout.addWidget(QLabel("搜尋："))
        layout.addWidget(self.search_input)
        layout.addWidget(QLabel("取代為："))
        layout.addWidget(self.replace_input)
        layout.addWidget(self.replace_button)
        self.setLayout(layout)

    def replace_text(self):
        search = self.search_input.text()
        replace = self.replace_input.text()
        if search:
            text = self.editor.toPlainText().replace(search, replace)
            self.editor.setPlainText(text)

class TerminalWidget(QTextBrowser):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background-color: black; color: white; font-family: monospace;")
        self.setReadOnly(True)
        self.process = QProcess()
        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.readyReadStandardError.connect(self.read_output)
        self.process.start("bash")

    def read_output(self):
        data = self.process.readAllStandardOutput().data().decode()
        self.append(data)

class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.highlightingRules = []
        keywordFormat = QTextCharFormat()
        keywordFormat.setForeground(Qt.blue)
        keywords = [
            'def', 'class', 'if', 'elif', 'else', 'try', 'except', 'finally',
            'while', 'for', 'in', 'import', 'from', 'as', 'return', 'with', 'pass',
            'break', 'continue', 'and', 'or', 'not', 'is', 'lambda', 'True', 'False', 'None'
        ]
        for word in keywords:
            pattern = QRegExp(f"\\b{word}\\b")
            self.highlightingRules.append((pattern, keywordFormat))
        commentFormat = QTextCharFormat()
        commentFormat.setForeground(Qt.darkGreen)
        self.highlightingRules.append((QRegExp("#.*"), commentFormat))
        stringFormat = QTextCharFormat()
        stringFormat.setForeground(Qt.darkMagenta)
        self.highlightingRules.append((QRegExp('\".*\"'), stringFormat))
        self.highlightingRules.append((QRegExp("'.*'"), stringFormat))

    def highlightBlock(self, text):
        for pattern, fmt in self.highlightingRules:
            index = pattern.indexIn(text)
            while index >= 0:
                length = pattern.matchedLength()
                self.setFormat(index, length, fmt)
                index = pattern.indexIn(text, index + length)

class GitDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Git 操作")
        self.setMinimumWidth(400)
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("輸入 Git 指令（如 status, commit -m 'msg'）")
        run_button = QPushButton("執行")
        run_button.clicked.connect(self.run_command)
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Git 指令："))
        layout.addWidget(self.command_input)
        layout.addWidget(run_button)
        layout.addWidget(QLabel("輸出："))
        layout.addWidget(self.output)
        self.setLayout(layout)

    def run_command(self):
        command = self.command_input.text().strip()
        if not command:
            return
        full_cmd = ["git"] + command.split()
        try:
            result = subprocess.run(full_cmd, capture_output=True, text=True, check=True)
            self.output.append("$ git " + command)
            self.output.append(result.stdout)
        except subprocess.CalledProcessError as e:
            self.output.append("$ git " + command)
            self.output.append(e.stderr)

class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.codeEditor = editor

    def sizeHint(self):
        return QSize(self.codeEditor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event):
        self.codeEditor.lineNumberAreaPaintEvent(event)

class CodeEditor(QPlainTextEdit):
    def __init__(self):
        super().__init__()
        self.highlighter = PythonHighlighter(self.document())
        self.cursorPositionChanged.connect(self.highlight_current_line)
        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.lineNumberArea = LineNumberArea(self)
        self.updateLineNumberAreaWidth(0)
        self.highlight_current_line()
        keywords = ['def', 'class', 'import', 'from', 'return', 'if', 'else', 'elif', 'while', 'for', 'in', 'try', 'except']
        self.completer = QCompleter(keywords)
        self.completer.setWidget(self)
        self.completer.setCompletionMode(QCompleter.PopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.activated.connect(self.insert_completion)

    def insert_completion(self, text):
        tc = self.textCursor()
        tc.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor)
        tc.insertText(text)
        self.setTextCursor(tc)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Tab:
            self.insertPlainText("    ")
        elif event.text().isalpha():
            super().keyPressEvent(event)
            self.completer.complete()
        else:
            super().keyPressEvent(event)

    def lineNumberAreaWidth(self):
        digits = len(str(max(1, self.blockCount())))
        return 3 + self.fontMetrics().width('9') * digits

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height())

    def updateLineNumberAreaWidth(self, _):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect, dy):
        if dy:
            self.lineNumberArea.scroll(0, dy)
        else:
            self.lineNumberArea.update(0, rect.y(), self.lineNumberArea.width(), rect.height())

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.lineNumberArea)
        painter.fillRect(event.rect(), Qt.lightGray)
        block = self.firstVisibleBlock()
        blockNumber = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(blockNumber + 1)
                painter.setPen(Qt.black)
                painter.drawText(0, top, self.lineNumberArea.width() - 2, self.fontMetrics().height(), Qt.AlignRight, number)
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            blockNumber += 1

    def highlight_current_line(self):
        extraSelections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            lineColor = QColor(Qt.yellow).lighter(160)
            selection.format.setBackground(lineColor)
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extraSelections.append(selection)
        self.setExtraSelections(extraSelections)

class FeatureManager:
    def __init__(self, main_window):
        self.main_window = main_window
        self.features = {}

    def register(self, name, callback, shortcut=None, menu=None, toolbar=True, tip=None):
        action = QAction(name, self.main_window)
        if shortcut:
            action.setShortcut(shortcut)
        if tip:
            action.setToolTip(tip)
        action.triggered.connect(callback)
        if toolbar:
            self.main_window.toolbar.addAction(action)
        if menu:
            menu.addAction(action)
        self.features[name] = action

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Be Like VSCode")
        self.setGeometry(100, 100, 1000, 700)
        self.toolbar = self.addToolBar("工具列")
        self.menuBar = self.menuBar()
        self.file_menu = self.menuBar.addMenu("檔案")
        self.edit_menu = self.menuBar.addMenu("編輯")
        self.view_menu = self.menuBar.addMenu("檢視")
        self.tools_menu = self.menuBar.addMenu("工具")
        self.help_menu = self.menuBar.addMenu("說明")
        self.editor = CodeEditor()
        self.setCentralWidget(self.editor)
        self.current_file = None
        self.recent_files = []
        self.is_dark = False
        self.feature_manager = FeatureManager(self)
        self.register_features()

    def register_features(self):
        fm = self.feature_manager
        fm.register("開啟檔案", self.open_file, "Ctrl+O", self.file_menu, True, "開啟本機檔案")
        fm.register("儲存檔案", self.save_file, "Ctrl+S", self.file_menu, True, "儲存目前檔案")
        fm.register("最近檔案", self.show_recent_files, None, self.file_menu, True, "顯示最近開啟的檔案")
        fm.register("關於", self.show_about, None, self.help_menu, True, "顯示關於視窗")
        fm.register("切換主題", self.toggle_theme, None, self.view_menu, True, "亮/暗主題切換")
        fm.register("Git 操作", self.open_git_dialog, "Ctrl+G", self.tools_menu, True, "開啟 Git 指令視窗")
        fm.register("搜尋", self.open_search_dialog, "Ctrl+F", self.edit_menu, True, "在檔案中搜尋文字")
        fm.register("取代", self.open_replace_dialog, "Ctrl+H", self.edit_menu, True, "在檔案中取代文字")
        fm.register("終端機", self.open_terminal, "Ctrl+`", self.tools_menu, True, "開啟終端機")
        fm.register("字數統計", self.word_count, None, self.tools_menu, True, "顯示目前檔案字數")
        fm.register("轉大寫", self.to_upper, None, self.edit_menu, True, "將選取文字轉為大寫")
        fm.register("轉小寫", self.to_lower, None, self.edit_menu, True, "將選取文字轉為小寫")
        fm.register("跳至行", self.goto_line, "Ctrl+L", self.edit_menu, True, "跳至指定行")
        fm.register("清除全部", self.clear_all, None, self.edit_menu, True, "清空編輯器內容")
        fm.register("重新載入", self.reload_file, None, self.file_menu, True, "重新載入目前檔案")
        fm.register("複製", self.editor.copy, "Ctrl+C", self.edit_menu, False, "複製選取文字")
        fm.register("貼上", self.editor.paste, "Ctrl+V", self.edit_menu, False, "貼上文字")
        fm.register("剪下", self.editor.cut, "Ctrl+X", self.edit_menu, False, "剪下選取文字")
        fm.register("全選", self.editor.selectAll, "Ctrl+A", self.edit_menu, False, "全選內容")
        fm.register("反白目前行", self.editor.highlight_current_line, None, self.view_menu, False, "反白目前行")

    def open_search_dialog(self):
        dlg = SearchDialog(self.editor)
        dlg.exec_()

    def open_replace_dialog(self):
        dlg = ReplaceDialog(self.editor)
        dlg.exec_()

    def open_terminal(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("終端機")
        layout = QVBoxLayout()
        terminal = TerminalWidget()
        layout.addWidget(terminal)
        dlg.setLayout(layout)
        dlg.resize(600, 300)
        dlg.exec_()

    def word_count(self):
        text = self.editor.toPlainText()
        words = len(text.split())
        chars = len(text)
        QMessageBox.information(self, "字數統計", f"字數：{words}\n字元數：{chars}")

    def to_upper(self):
        cursor = self.editor.textCursor()
        if cursor.hasSelection():
            cursor.insertText(cursor.selectedText().upper())

    def to_lower(self):
        cursor = self.editor.textCursor()
        if cursor.hasSelection():
            cursor.insertText(cursor.selectedText().lower())

    def goto_line(self):
        line, ok = QInputDialog.getInt(self, "跳至行", "輸入行號：", 1, 1)
        if ok:
            cursor = self.editor.textCursor()
            cursor.movePosition(QTextCursor.Start)
            for _ in range(line - 1):
                cursor.movePosition(QTextCursor.Down)
            self.editor.setTextCursor(cursor)
            self.editor.setFocus()

    def clear_all(self):
        self.editor.clear()

    def reload_file(self):
        if self.current_file and os.path.exists(self.current_file):
            with open(self.current_file, "r", encoding="utf-8") as f:
                self.editor.setPlainText(f.read())

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "開啟檔案", "", "所有檔案 (*)")
        if path:
            with open(path, "r", encoding="utf-8") as f:
                self.editor.setPlainText(f.read())
            self.current_file = path
            if path not in self.recent_files:
                self.recent_files.insert(0, path)
                self.recent_files = self.recent_files[:5]

    def save_file(self):
        if self.current_file:
            with open(self.current_file, "w", encoding="utf-8") as f:
                f.write(self.editor.toPlainText())
        else:
            path, _ = QFileDialog.getSaveFileName(self, "儲存檔案", "", "所有檔案 (*)")
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(self.editor.toPlainText())
                self.current_file = path

    def show_recent_files(self):
        if not self.recent_files:
            QMessageBox.information(self, "最近檔案", "沒有最近檔案。")
            return
        menu = QMenu(self)
        for path in self.recent_files:
            action = QAction(path, self)
            action.triggered.connect(lambda checked, p=path: self.load_recent_file(p))
            menu.addAction(action)
        menu.exec_(self.mapToGlobal(self.rect().bottomLeft()))

    def load_recent_file(self, path):
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                self.editor.setPlainText(f.read())
            self.current_file = path

    def toggle_theme(self):
        if self.is_dark:
            self.setStyleSheet("")
            self.is_dark = False
        else:
            self.setStyleSheet("background-color: #232323; color: #e0e0e0;")
            self.editor.setStyleSheet("background-color: #232323; color: #e0e0e0;")
            self.is_dark = True

    def show_about(self):
        QMessageBox.about(self, "關於", "Be Like VSCode\n改編者: cheerawab\nBeta 版\n2025")

    def open_git_dialog(self):
        dlg = GitDialog(self)
        dlg.exec_()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())

