import sys

from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *


class QToggleSwitch(QCheckBox):
    """ A custom toggle switch widget. Copied from: https://www.youtube.com/watch?v=NnJFi285s3M"""

    def __init__(self, width=60, bg_color="#777", circle_color="#DDD",  active_color="#599afe", animation_curve=QEasingCurve.Type.OutCirc):
        super().__init__()

        self.setFixedSize(width, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._bg_color = bg_color
        self._circle_color = circle_color
        self._active_color = active_color

        self._circle_position = 3
        self.animation = QPropertyAnimation(self, b"circle_position", self)
        self.animation.setEasingCurve(animation_curve)
        self.animation.setDuration(200)

        self.stateChanged.connect(self.start_transition)

    @Property(float)
    def circle_position(self):
        return self._circle_position

    @circle_position.setter
    def circle_position(self, pos):
        self._circle_position = pos
        self.update()

    def start_transition(self, value):
        self.animation.stop()
        self.animation.setEndValue(self.width() - 26 if value else 3)
        print(f'Manual Mode isChecked: {self.isChecked()}')
        self.animation.start()

    def Error(self):
        self.setCheckState(Qt.Unchecked)
        self.start_transition

    def paintEvent(self, _: QPaintEvent):
        p = QPainter()
        p.begin(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)

        p.setBrush(QColor(self._active_color if self.isChecked() else self._bg_color))
        p.drawRoundedRect(0, 0, self.width(), self.height(), self.height() / 2, self.height() / 2)
        p.setBrush(QColor(self._circle_color))
        p.drawEllipse(self._circle_position, 3, 22, 22)
        p.end()

    def hitButton(self, pos: QPoint) -> bool:
        return self.contentsRect().contains(pos)


# class RoundedLineEdit(QLineEdit):
#     def paintEvent(self, event):
#         # Create a QPainter and begin painting
#         painter = QPainter(self)
#         painter.begin(self)
#         painter.setPen(Qt.black)
#         painter.setPen(1)

#         # Create a QPainterPath and add rounded rectangles to it
#         path = QPainterPath()
#         radius = 50
#         rect = self.rect()
#         path.addRoundedRect(rect, radius, radius)

#         painter.setBrush(QColor(255, 255, 255))
#         painter.fillPath(path, painter.brush())

#         super().paintEvent(event)         # Call the superclass paintEvent function to draw the text and cursor
#         painter.end()
