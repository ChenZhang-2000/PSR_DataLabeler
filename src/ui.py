import re
import os
import sys
import time
import pickle
import datetime
from pathlib import Path

import numpy as np
from PyQt5 import QtWidgets, QtGui, QtMultimedia, QtCore
from PyQt5.QtWidgets import QPushButton, QApplication, QVBoxLayout, QWidget, QHBoxLayout, QLabel, QGridLayout
from PyQt5.QtCore import Qt, pyqtSignal, QPoint

from .data import Data
from .exceptions import *

ORIGIN = {"border": "1px solid black", "padding": "3px", "background-color": "#FFFFFF"}
UNMARKED = {"border": "1px solid black", "padding": "3px", "background-color": "#FFFFFF"}
MARKED = {"border": "1px solid #C13434", "padding": "3px", "background-color": "#FFFFFF"}
CHOSEN = {"border": "1px solid #D7E9FF", "padding": "3px", "background-color": "#D7E9FF"}


def check_file(file_path, required_type=".csv"):
    """
    :param file_path:
    :param required_type:
    :return:
        0: required file
        -1: file type incorrect
        1: file does not exist
        2: input is not string
        3: empty input
    """
    if not file_path:
        return 3

    if not isinstance(file_path, str):
        return 2

    if not Path(file_path).exists():
        return 1

    if not required_type:
        return 0

    if len(file_path) >= len(required_type) and file_path[-len(required_type):] == required_type:
        return 0
    else:
        return -1


def time_stamp(t, time_zone):
    """

    :param t: YYYYMMDD-hhmmss
    :param time_zone: UTC n
    :return:
    """
    ts = int(time.mktime(datetime.datetime.strptime(t, "%Y%m%d-%H%M%S").timetuple())) - int(time_zone.split()[1]) * 3600
    return ts*1000


def style_2_stylesheet(style):
    return "; ".join([f"{k}: {style[k]}" for k in style])


def stylesheet_2_style(style_sheet):
    return {k.strip().split(":")[0].strip() : k.strip().split(":")[1].strip() for k in style_sheet.split(";")}


class Matching:
    def __init__(self, data, window):
        self.data = data
        self.window = window
        self.left = None
        self.right = None

        self.click = None
        self.rest = None

    def clicking(self, side_label, label):
        if side_label:
            if side_label.idx == label.idx:
                side_label.set_unmarked()
                return None
            else:
                side_label.set_unmarked()

        return label

    def on_click(self, side, label):
        """
        :param side: 0 or 1; 0 for sentences, and 1 for danmu
        :return:
        """

        if side == 0:
            self.left = self.clicking(self.left, label)
            self.rest = self.right
            # print(self.left)
        elif side == 1:
            self.right = self.clicking(self.right, label)
            self.rest = self.left
            # print(self.right)
        else:
            raise

        paired = 0
        out = 0
        left = None
        right = None

        if self.rest:
            paired = 1
            self.left.set_unmarked()
            self.right.set_unmarked()

            out = self.match(self.left.idx, self.right.idx)

            left = self.left
            right = self.right

            self.left = None
            self.right = None
            self.rest = None

        return paired, out, left, right

    def match(self, l_idx, r_idx):
        if self.data[l_idx, r_idx]:
            self.data.delete("dialogue", (l_idx, r_idx))
            if self.window.dialogue_show:
                if (self.data.dialogue[l_idx, :] != 0).count_nonzero() == 0:
                    self.window.sen_labels[l_idx][0].set_unchosen()
                else:
                    self.window.sen_labels[l_idx][0].set_chosen()
                if (self.data.dialogue[:, r_idx] != 0).count_nonzero() == 0:
                    self.window.dan_labels[r_idx][0].set_unchosen()
                else:
                    self.window.dan_labels[r_idx][0].set_chosen()
            out = 0
        else:
            self.data.match(l_idx, r_idx)
            if self.window.dialogue_show:
                self.window.sen_labels[l_idx][0].set_chosen()
                self.window.dan_labels[r_idx][0].set_chosen()
            out = 1
        return out


class Label(QWidget):
    clicked = pyqtSignal()  # Define a signal for label click

    def __init__(self, idx, side, parent=None, match=None):
        super().__init__()
        self.selected = False
        self.is_editing = False
        self.side = side
        self.idx = idx
        self.match = match
        self.parent = parent

        data = self.match.data.danmu.data if side else self.match.data.sentences.data
        text = data.loc[idx, "content"]

        self.layout = QHBoxLayout(self)

        self.text_widget = QWidget(self)
        self.text_layout = QVBoxLayout(self.text_widget)
        self.text_layout.setSpacing(0)
        self.text_layout.setContentsMargins(10, 0, 10, 0)

        self.label = QLabel(text=text, parent=self)
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet(style_2_stylesheet(ORIGIN))

        self.line_edit = QtWidgets.QLineEdit(self)
        self.line_edit.hide()
        self.line_edit.editingFinished.connect(self.finish_editing)
        # self.line_edit.returnPressed.connect(self.return_pressed)

        self.text_layout.addWidget(self.label)
        self.text_layout.addWidget(self.line_edit)

        if self.side:
            self.button = None
        else:
            self.button = QtWidgets.QPushButton(self)
            self.button.setIcon(QtGui.QIcon("./lib/img/play_sound.png"))
            self.button.setIconSize(QtCore.QSize(32, 32))
            self.button.setFixedSize(30, 30)
            self.button.clicked.connect(self.play_sound)
            self.layout.addWidget(self.button)

        self.layout.addWidget(self.text_widget)

    def set_marked(self):
        self.selected = True
        out_ss = MARKED.copy()

        ss = stylesheet_2_style(self.label.styleSheet())
        if "background-color" in ss:
            bg_value = ss["background-color"]
        else:
            bg_value = "#FFFFFF"

        out_ss["background-color"] = bg_value

        self.label.setStyleSheet(style_2_stylesheet(out_ss))

    def set_unmarked(self):
        self.selected = False
        out_ss = UNMARKED.copy()

        ss = stylesheet_2_style(self.label.styleSheet())
        if "background-color" in ss:
            bg_value = ss["background-color"]
        else:
            bg_value = "#FFFFFF"

        out_ss["background-color"] = bg_value

        if "background-color" in ss:
            if ss["background-color"] == CHOSEN["background-color"]:
                out_ss["border"] = CHOSEN["border"]

        self.label.setStyleSheet(style_2_stylesheet(out_ss))

    def set_chosen(self):
        self.label.setStyleSheet(style_2_stylesheet(CHOSEN))

    def set_unchosen(self):
        out_ss = UNMARKED.copy()
        out_ss["background-color"] = "#FFFFFF"
        self.label.setStyleSheet(style_2_stylesheet(out_ss))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.left_click_event(event)
        elif event.button() == Qt.RightButton:
            self.contextMenuEvent(event)

    def left_click_event(self, event):
        if self.selected:
            self.set_unmarked()
        else:
            self.set_marked()

        paired, out, l, r = self.match.on_click(self.side, self)
        if paired:
            if out:
                self.parent.container.update()
            else:
                self.parent.container.update()

    def contextMenuEvent(self, event):
        context_menu = QtWidgets.QMenu(self)
        context_menu.setStyleSheet("""
            QMenu {
                background-color: #f0f0f0;  /* Menu background color */
                border: 1px solid black;   /* Menu border */
            }
            QMenu::item {
                background-color: transparent;  /* Item background color */
                padding: 5px 20px;  /* Item padding */
            }
            QMenu::item:selected {  /* Hover state */
                background-color: #8AB7FA;  /* Item background color when hovered */
            }""")

        action_edit = QtWidgets.QAction("edit", self)
        action_delete = QtWidgets.QAction("delete", self)

        action_edit.triggered.connect(self.start_editing)
        action_delete.triggered.connect(self.delete)

        # Add actions to the context menu
        context_menu.addAction(action_edit)
        context_menu.addAction(action_delete)

        # Show the context menu at the position of the cursor
        context_menu.exec_(event.globalPos())

    def start_editing(self):
        self.label.hide()
        self.line_edit.setText(self.label.text())
        self.line_edit.show()
        self.line_edit.setFocus()
        self.is_editing = True

    def finish_editing(self):
        if self.is_editing:
            self.is_editing = False
            text = self.line_edit.text()
            where = "danmu" if self.side else "sentence"
            self.match.data.modify(where, self.idx, text)
            self.label.setText(text)
            self.line_edit.hide()
            self.label.show()
        else:
            pass

    def delete(self):
        where = "danmu" if self.side else "sentence"
        self.match.data.delete(where, self.idx)
        self.parent.delete(self)

    def play_sound(self):
        sound_file = self.match.data.sentences.data.iloc[self.idx, 3]
        QtMultimedia.QSound.play(sound_file)


class ContentContainer(QWidget):
    def __init__(self, parent):
        super(ContentContainer, self).__init__(parent=parent)
        self.parent = parent

    def paintEvent(self, event):
        if self.parent.dialogue_show:
            painter = QtGui.QPainter(self)
            pen = QtGui.QPen(QtGui.QColor("#2C6DCD"), 3)
            painter.setPen(pen)

            L, R = self.parent.data.dialogue.nonzero()

            for l_idx, r_idx in zip(L, R):
                left_label = self.parent.sen_labels[l_idx][0]
                right_label = self.parent.dan_labels[r_idx][0]
                left_rect = left_label.label.geometry()
                right_rect = right_label.label.geometry()
                left_pos = left_label.mapTo(self, QPoint(left_rect.right(), left_rect.center().y()))
                right_pos = right_label.mapTo(self, QPoint(right_rect.left(), right_rect.center().y()))

                painter.drawLine(left_pos, right_pos)


class MainWindow(QWidget):
    def __init__(self, data: Data, danmu_shift=-20105000, parent=None):
        super(MainWindow, self).__init__()
        self.parent = parent
        self.data = data
        self.data.parent = self
        self.data.danmu.shift(danmu_shift)
        self.data.mk_timeline()

        self.match = Matching(self.data, self)

        self.w = 1000
        self.h = 1000
        self.dialogue_show = True
        self.file_path = None

        self.resize(self.w, self.h)
        self.setWindowTitle("PSR数据标注器")

        self.connections = {}
        self.sen_labels = {}
        self.dan_labels = {}
        self.deleted = [set(), set()]

        self.main_layout = QVBoxLayout(self)
        self.setLayout(self.main_layout)

        self.container = ContentContainer(self)
        self.container_layout = QGridLayout(self.container)

        self.init_labels()

        self.container.setLayout(self.container_layout)

        self.c_widget = QtWidgets.QScrollArea()
        self.c_widget.setWidgetResizable(True)
        self.c_widget.setWidget(self.container)

        # Control Panel

        self.control_panel = QWidget()
        self.cp_layout = QHBoxLayout(self.control_panel)
        self.control_panel.setLayout(self.cp_layout)

        self.button_show = QtWidgets.QPushButton("Show Dialogue")
        self.button_show.setStyleSheet("border: 1px solid black; padding: 5px; background-color: #D7E9FF")
        self.button_show.clicked.connect(self.show_dialogue)

        self.button_save = QtWidgets.QPushButton("Save")
        self.button_save.setStyleSheet("border: 1px solid black; padding: 5px; background-color: #D7E9FF")
        self.button_save.clicked.connect(self.save)

        self.button_file = QtWidgets.QPushButton("Select File")
        self.button_file.setStyleSheet("border: 1px solid black; padding: 5px; background-color: #D7E9FF")
        self.button_file.clicked.connect(self.select_file)

        self.cp_layout.addWidget(self.button_show)
        self.cp_layout.addWidget(self.button_save)
        self.cp_layout.addWidget(self.button_file)

        # Add shortcuts
        self.save_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+S"), self)
        self.save_shortcut.activated.connect(self.save)
        self.save_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Shift+S"), self)
        self.save_shortcut.activated.connect(self.save_as)
        self.undo_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Z"), self)
        self.undo_shortcut.activated.connect(self.undo)

        # main
        self.setStyleSheet("background-color: #F8F8F8")
        self.main_layout.addWidget(self.control_panel)
        self.main_layout.addWidget(self.c_widget)

    def init_labels(self):
        i = 1
        last_idx = None
        last_i = 2

        self.container_layout.addItem(QtWidgets.QSpacerItem(80, 20), 1, 2)

        for _, line in self.data.timeline.iterrows():
            idx, time, side = line

            label = Label(idx, side, parent=self, match=self.match)
            label.layout.setSpacing(0)
            label.layout.setContentsMargins(10, 0, 10, 0)
            label.label.adjustSize()

            if side:
                self.dan_labels[label.idx] = (label, i, side+2)

                self.container_layout.addWidget(label, i, side+2)

            else:
                if last_idx == idx:
                    self.sen_labels[label.idx] = (label, last_i, side+1, i-last_i, 1)
                    self.container_layout.addWidget(label, last_i, side+1, i-last_i, 1)
                else:
                    last_idx = idx
                    last_i = i
            i += 1

    def show_dialogue(self):
        I, J = self.data.dialogue.nonzero()
        for i, j in zip(I, J):
            if self.dialogue_show:
                self.sen_labels[i][0].set_unchosen()
                self.dan_labels[j][0].set_unchosen()
            else:
                self.sen_labels[i][0].set_chosen()
                self.dan_labels[j][0].set_chosen()
        self.dialogue_show = not self.dialogue_show
        self.update()

    def delete(self, label):
        self.container_layout.removeWidget(label)
        label.hide()
        self.deleted[label.side].add(label.idx)

    def save(self):
        if self.file_path:
            data = self.data.data_to_save()
            file_path = Path(self.file_path)
            with open(file_path, 'wb') as file:
                try:
                    pickle.dump(data, file)
                except Exception as err:
                    print(err)
        else:
            self.save_as()

    def save_as(self):
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(self,
                                                             "Save Connections",
                                                             "",
                                                             "PSR Files (*.psr);;All Files (*)")
        if file_path:
            self.file_path = file_path
            self.save()

    def select_file(self):
        self.parent.show()
        self.deleteLater()

    def undo(self):
        if len(self.data.history) == 0:
            return
        where, action = self.data.history[-1]
        content = self.data.undo()

        if action == "delete":
            if where == "sentence" or where == "danmu":
                idx = content.name
                widget_data = self.sen_labels[idx] if where == "sentence" else self.dan_labels[idx]
                label = widget_data[0]
                self.container_layout.addWidget(*widget_data)
                self.deleted[label.side].remove(label.idx)
                label.show()
            elif where == "dialogue":
                pass
            else:
                raise

        elif action == "modify":
            if where == "sentence" or where == "danmu":
                idx, content = content
                label = self.dan_labels[idx][0] if (where == "danmu") else self.sen_labels[idx][0]
                label.label.setText(content)
            else:
                raise

        elif action[0] == "match":
            if where == "dialogue":
                pass
            else:
                raise
        else:
            raise

        self.container.update()


class FileLabel(QWidget):
    def __init__(self, idx, directory="", parent=None):
        super(FileLabel, self).__init__(parent=parent)
        self.parent = parent
        self.idx = idx
        self.layout = QHBoxLayout(self)
        self.setLayout(self.layout)
        self.setStyleSheet(style_2_stylesheet(ORIGIN))
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setFixedHeight(32)

        self.file_path = directory

        self.remove_button = QPushButton(self)
        self.remove_button.setIcon(QtGui.QIcon("./lib/img/delete_file.png"))
        self.remove_button.setIconSize(QtCore.QSize(32, 32))
        self.remove_button.setFixedSize(32, 32)
        self.remove_button.clicked.connect(self.delete)

        self.layout.addWidget(self.remove_button)

    def delete(self):
        self.parent.delete_label(self)

    def verify(self):
        return check_file(self.file_path)


class DanmuFileLabel(FileLabel):
    def __init__(self, idx, directory="", parent=None):
        super(DanmuFileLabel, self).__init__(idx=idx, directory=directory, parent=parent)

        self.label = QLabel(Path(directory).name, self)
        self.layout.addWidget(self.label)


class SentenceFileLabel(FileLabel):
    def __init__(self, idx, directory="", parent=None):
        super(SentenceFileLabel, self).__init__(idx=idx, directory=directory, parent=parent)
        self.is_editing = False

        path = Path(directory)
        self.folder_path = ""
        self.start_time = path.stem
        self.time_zone_code = "UTC +8"

        self.l_label = QLabel(path.name, self)

        fp = path.parent / path.stem
        if fp.exists():
            self.r_label = QLabel(path.stem, self)
            self.folder_path = fp.__str__()
        else:
            self.r_label = QLabel("Select .wav Directory", self)

        self.l_label.setFixedHeight(32)
        self.r_label.setFixedHeight(32)

        self.time_input = QtWidgets.QLineEdit(self.start_time, self)
        self.time_input.editingFinished.connect(self.finish_editing)
        self.time_input.setFixedSize(150, 32)

        self.time_zone = QtWidgets.QComboBox(self)
        self.init_time_zone_box()
        self.time_zone.setFixedHeight(32)

        self.layout.addWidget(self.l_label)
        self.layout.addWidget(self.r_label)
        self.layout.addWidget(self.time_input)
        self.layout.addWidget(self.time_zone)

    def verify(self):
        """

        :return:
            0, None: information correct
            1, x: file path incorrect with error code x
            2, x: folder path incorrect with error code x
            3, x: start time incorrect with error code x
                x=1: start time does not satisfy requirement
            4, x: time zone incorrect with error code x
                x=1: time zone code does not satisfy requirement
        """
        fp_status = check_file(self.file_path)
        if fp_status != 0:
            return 1, fp_status

        fp_status = check_file(self.folder_path, required_type="")
        if fp_status != 0:
            return 2, fp_status

        if not re.match(r"\d{8}-\d{6}", self.start_time):
            return 3, 1

        if not re.match(r"UTC [+-]\d{1,2}", self.time_zone_code):
            return 4, 1

        return 0, None

    def start_editing(self):
        self.time_input.setText(self.label.text())
        self.time_input.setFocus()
        # self.is_editing = True

    def finish_editing(self):
        # self.is_editing = False
        self.start_time = self.time_input.text()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.select_wav()

    def init_time_zone_box(self):
        for i in range(24):
            j = 8-i
            if j >= 0:
                out = f"+{j}"
            elif j >= -12:
                out = str(j)
            else:
                out = f"+{j+24}"
            self.time_zone.addItem(f"UTC {out}")

    def select_wav(self):
        file_folder = self.parent.select_folder()
        self.r_label.setText(Path(file_folder).name)
        self.folder_path = file_folder

    def current_text_changed(self, s):
        self.time_zone = s


class PreMainWidget(QWidget):
    def __init__(self):
        super(PreMainWidget, self).__init__()
        self.resize(1000, 1000)

        self.layout = QVBoxLayout(self)
        self.setLayout(self.layout)
        self.setStyleSheet("background-color: #F8F8F8")

        self.launch_button = QtWidgets.QPushButton("Launch", self)
        self.launch_button.setFixedHeight(64)
        self.launch_button.clicked.connect(self.launch)
        self.launch_button.setStyleSheet("border: 1px solid #FFEFC1; padding: 3px; background-color: #FFEFC1")

        self.danmu_box = QWidget(self)
        self.danmu_box_layout = QVBoxLayout(self.danmu_box)
        self.danmu_box.setLayout(self.danmu_box_layout)

        self.sentence_box = QWidget(self)
        self.sentence_box_layout = QVBoxLayout(self.sentence_box)
        self.sentence_box.setLayout(self.sentence_box_layout)

        self.layout.addWidget(self.launch_button)
        self.layout.addWidget(self.danmu_box)
        self.layout.addWidget(self.sentence_box)

        self.danmu_labels = []
        self.sentence_labels = []

        self.init_danmu()
        self.init_sentence()

    def init_danmu(self):
        button = QtWidgets.QPushButton('Select Danmu File', self)
        button.clicked.connect(self.select_danmu_file)
        button.setStyleSheet("border: 1px solid #D7E9FF; padding: 3px; background-color: #D7E9FF")
        button.setFixedHeight(32)
        self.danmu_box_layout.addWidget(button)

    def init_sentence(self):
        button = QtWidgets.QPushButton('Select Sentence File', self)
        button.clicked.connect(self.select_sentence_file)
        button.setStyleSheet("border: 1px solid #D7E9FF; padding: 3px; background-color: #D7E9FF")
        button.setFixedHeight(32)
        self.sentence_box_layout.addWidget(button)

    def select_file(self):
        options = QtWidgets.QFileDialog.Options()
        file_name, _ = QtWidgets.QFileDialog.getOpenFileNames(self, "Select File", "", "CSV Files (*.csv);;All Files (*)", options=options)
        return file_name

    def select_folder(self):
        options = QtWidgets.QFileDialog.Options()
        folder_name = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Folder", "", options=options)
        return folder_name

    def select_sentence_file(self):
        file_names = self.select_file()
        if file_names:
            for file_name in file_names:
                idx = self.sentence_labels.__len__()
                label = SentenceFileLabel(idx, file_name, self)
                self.sentence_labels.append(label)
                self.sentence_box_layout.addWidget(label)

    def select_danmu_file(self):
        file_names = self.select_file()
        if file_names:
            for file_name in file_names:
                idx = self.danmu_labels.__len__()
                label = DanmuFileLabel(idx, file_name, self)
                self.danmu_labels.append(label)
                self.danmu_box_layout.addWidget(label)

    def delete_label(self, label):
        if isinstance(label, SentenceFileLabel):
            self.sentence_box_layout.removeWidget(label)
            self.sentence_labels.pop(label.idx)
            self.rearange_idx(self.sentence_labels)
        elif isinstance(label, DanmuFileLabel):
            self.danmu_box_layout.removeWidget(label)
            self.danmu_labels.pop(label.idx)
            self.rearange_idx(self.danmu_labels)
        else:
            raise

        label.deleteLater()

    def rearange_idx(self, labels):
        for i in range(len(labels)):
            labels[i].idx = i

    def check_err_code(self, err_code, idx, subject="Danmu file"):
        if err_code == 0:
            pass
        elif err_code == -1:
            raise FileNotCSVException(f"{subject} {idx} has incorrect file type")
        elif err_code == 1:
            raise FileDoesNotExist(f"{subject} {idx} does not exist")
        elif err_code == 2:
            raise InputNotString(f"{subject} {idx} has wrong input type")
        elif err_code == 3:
            raise EmptyInput(f"{subject} {idx} is empty")
        else:
            raise Exception(f"{subject} {idx} has unknown exception")

    def verify(self):
        for label in self.danmu_labels:
            err_code = label.verify()
            self.check_err_code(err_code, label.idx, "Danmu file")

        for label in self.sentence_labels:
            error_term, err_code = label.verify()
            if error_term == 0:
                continue
            elif error_term == 1:
                self.check_err_code(err_code, label.idx, "Sentence file")
            elif error_term == 2:
                self.check_err_code(err_code, label.idx, "Folder")
            elif error_term == 3:
                if err_code == 1:
                    raise StartTimeFormatIncorrect(f"Start time {label.start_time} has incorrect format")
                else:
                    raise Exception(f"Start time {label.start_time} has unknown exception")
            elif error_term == 4:
                if err_code == 1:
                    raise StartTimeFormatIncorrect(f"Time zone {label.time_zone_code} has incorrect format")
                else:
                    raise Exception(f"Time zone {label.time_zone_code} has unknown exception")

    def launch(self):
        try:
            self.verify()
            danmu_file = []
            for danmu_label in self.danmu_labels:
                danmu_file.append(danmu_label.file_path)

            ts0 = time_stamp(self.sentence_labels[0].start_time, self.sentence_labels[0].time_zone_code)
            sentence_dirs = []
            for sentence_label in self.sentence_labels:
                ts = time_stamp(sentence_label.start_time, sentence_label.time_zone_code)
                sentence_dirs.append((sentence_label.folder_path, sentence_label.file_path, (ts-ts0)))

            data = Data(sentence_dirs, danmu_file)

            t0 = data.danmu.t0

            mw = MainWindow(data, t0-ts0, parent=self)
            mw.show()
            self.hide()

        except FileLabelException as err:
            print(err)


if __name__ == "__main__":
    sen_dirs = ((
                   r"E:\Projects\PythonProjects\PSR-Analysis\temp\sentences\20231222-222826",
                   r"E:\Projects\PythonProjects\PSR_DataLabeler\test_data\20231222-222826.csv",
                   0
               ),)
    danmu_file = r"E:\Projects\PythonProjects\PSR_DataLabeler\test_data\danmu.csv"
    app = QApplication(sys.argv)
    firstWin = MainWindow(sen_dirs, danmu_file)
    firstWin.show()
    sys.exit(app.exec_())

