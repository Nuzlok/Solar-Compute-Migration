from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *


class QToggleSwitch(QCheckBox):
    """ A custom toggle switch widget. Modified version of: https://www.youtube.com/watch?v=NnJFi285s3M"""

    def __init__(self, width=60, color="#777", circle_color="#DDD",  active_color="#599afe", duration=200, parent=None):
        super().__init__(parent=parent)

        self.setFixedSize(width, 20)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._deact_color = color
        self._circle_color = circle_color
        self._active_color = active_color
        self._spacing = 3
        self._circle_position = self._spacing
        self._circle_size = self.height() - (2*self._spacing)

        self.animation = QPropertyAnimation(self, b"circle_position", self)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCirc)
        self.animation.setDuration(duration)

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
        self.animation.setEndValue(self.width() - self._spacing - self._circle_size if value else self._spacing)
        # print(f'Manual Mode isChecked: {self.isChecked()}') # DEBUG LINE
        self.animation.start()

    def Error(self):
        self.setCheckState(Qt.Unchecked)
        self.start_transition

    def paintEvent(self, _: QPaintEvent):
        p = QPainter()
        p.begin(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)

        p.setBrush(QColor(self._active_color if self.isChecked() else self._deact_color))
        p.drawRoundedRect(0, 0, self.width(), self.height(), self.height() / 2, self.height() / 2)
        p.setBrush(QColor(self._circle_color))
        p.drawEllipse(self._circle_position, self._spacing, self._circle_size, self._circle_size)
        p.end()

    def hitButton(self, pos: QPoint) -> bool:
        return self.contentsRect().contains(pos)
