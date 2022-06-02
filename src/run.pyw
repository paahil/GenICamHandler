import PyQt5.QtWidgets as QtW
import sys
from gui import GUI


def main():
    app = QtW.QApplication(sys.argv)
    ex = GUI()
    sys.exit(app.exec())


main()
