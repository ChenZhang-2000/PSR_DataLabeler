import sys

from PyQt5 import QtWidgets

from src.ui import PreMainWidget


def main():

    app = QtWidgets.QApplication(sys.argv)
    pre_main = PreMainWidget()
    pre_main.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()