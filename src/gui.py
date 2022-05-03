import PyQt5.QtWidgets as QtW
import PyQt5.QtCore as QtC
import PyQt5.QtGui as QtG
from camHandler import CamHandler
import time
import numpy


class ImageThread(QtC.QThread):
    imageAcquired = QtC.pyqtSignal(numpy.ndarray, str)

    def __init__(self, gui):
        super().__init__()
        self.camHand = gui

    def run(self):
        self.camHand.cam.start_acquisition()
        while self.camHand.acquire:
            arr,tstamp = self.camHand.acquireImag()
            if arr is not None:
                self.imageAcquired.emit(arr, tstamp)
        self.camHand.cam.stop_acquisition()

class SaveThread(QtC.QThread):
    imageSaved = QtC.pyqtSignal()

    def __init__(self, handler):
        super().__init__()
        self.camHand = handler
        self.bw = None
        self.tstamp = None

    def run(self):
        self.camHand.saveImag(self.bw, self.tstamp)
        self.imageSaved.emit()


class GUI(QtW.QMainWindow):

    def __init__(self):
        super().__init__()
        self.errlog = open("CamHandlerErrorLog.txt", 'w')
        self.setCentralWidget(QtW.QWidget())  # QMainWindown must have a centralWidget to be able to add layouts
        self.mainlout = QtW.QGridLayout()
        self.centralWidget().setLayout(self.mainlout)
        self.setWindowTitle('GenICam Handler v1.0')
        QtW.QApplication.setStyle(QtW.QStyleFactory.create('Windows'))
        self.start = 0
        self.stop = 1
        self.drawimagcount = 0
        self.sstart = 0
        self.sstop = 1
        self.channel = 0

        self.camHand = CamHandler()
        self.camHand.filtcfg.load()
        self.camHand.load()
        self.imageRet = ImageThread(self.camHand)
        self.imageSaver1 = SaveThread(self.camHand)
        self.imageSaver2 = SaveThread(self.camHand)
        self.imageSaver3 = SaveThread(self.camHand)
        self.imageSaver4 = SaveThread(self.camHand)
        self.imageRet.imageAcquired.connect(self.drawImage)
        self.imageSaver1.imageSaved.connect(self.imageSaved)
        self.imageSaver2.imageSaved.connect(self.imageSaved)
        self.imageSaver3.imageSaved.connect(self.imageSaved)
        self.imageSaver4.imageSaved.connect(self.imageSaved)
        self.imageSaverList = [self.imageSaver1, self.imageSaver2, self.imageSaver3, self.imageSaver4]

        self.toplout = QtW.QHBoxLayout()
        self.deviceListG = QtW.QComboBox()
        self.updtListG = QtW.QPushButton()
        self.savepathG = QtW.QLineEdit()

        self.toplout2 = QtW.QHBoxLayout()
        self.triggerG = QtW.QPushButton()
        self.acquiringG = QtW.QPushButton()
        self.previewG = QtW.QPushButton()
        self.savingG = QtW.QPushButton()
        self.channelG = QtW.QPushButton()
        self.filteringG = QtW.QPushButton()

        self.screens = QtW.QVBoxLayout()
        self.screennorm = QtW.QLabel()
        self.screenbw = QtW.QLabel()

        self.filterl = QtW.QGridLayout()
        self.filterset = QtW.QGroupBox("Filter settings")
        self.bint = QtW.QSpinBox()
        self.alpha = QtW.QDoubleSpinBox()
        self.beta = QtW.QSpinBox()
        self.filt = QtW.QComboBox()
        self.filtw = QtW.QSpinBox()
        self.filth = QtW.QSpinBox()

        self.infobox = QtW.QGroupBox("Info")
        self.infolout = QtW.QGridLayout()
        self.fps = 0
        self.thrcnt = 0
        self.framecount = 0
        self.savecount = 0
        self.fpsG = QtW.QLabel()
        self.thrcntG = QtW.QLabel()
        self.framecountG = QtW.QLabel()
        self.savecountG = QtW.QLabel()
        self.updateInfo()

        self.infolout.addWidget(self.thrcntG, 1, 2)
        self.infolout.addWidget(self.fpsG, 1, 1)
        self.infolout.addWidget(self.framecountG, 2, 1)
        self.infolout.addWidget(self.savecountG, 2, 2)
        self.infobox.setLayout(self.infolout)

        self.createUITop()
        self.createUITop2()
        self.createScreens()
        self.createFilterSettings()

        self.setInit()

        self.mainlout.addLayout(self.toplout, 1, 1, 1, 2)
        self.mainlout.addLayout(self.toplout2, 2, 1, 1, 2)
        self.mainlout.addLayout(self.screens, 3, 2, 3, 1)
        self.mainlout.addWidget(self.filterset, 3, 1, 1, 1)
        self.mainlout.addWidget(self.infobox, 4, 1, 1, 1)
        self.show()

        self.filterset.setFixedSize(self.filterset.size())
        self.infobox.setFixedSize(self.infobox.size())

    def createUITop(self):
        deviceListL = QtW.QLabel()
        deviceListL.setText('Active Device:')
        savepathL = QtW.QLabel()
        savepathL.setText('Storage folder:')
        self.updtListG.setText('Update')
        self.updtListG.clicked.connect(self.updateDevicelist)
        self.deviceListG.currentIndexChanged.connect(self.changeActiveDevice)
        self.updateDevicelist()
        self.savepathG.editingFinished.connect(self.changeSaveDirectory)
        self.toplout.addWidget(deviceListL)
        self.toplout.addWidget(self.deviceListG, 1)
        self.toplout.addWidget(self.updtListG, 0)
        self.toplout.addWidget(savepathL)
        self.toplout.addWidget(self.savepathG, 4)

    def createUITop2(self):
        self.triggerG.setText('Trigger')
        self.triggerG.setCheckable(True)
        self.triggerG.setStyleSheet("background-color : lightgray")
        self.triggerG.clicked.connect(self.toggleTrigger)
        self.toplout2.addWidget(self.triggerG)

        self.acquiringG.setText('Acquire')
        self.acquiringG.setCheckable(True)
        self.acquiringG.setStyleSheet("background-color : lightgray")
        self.acquiringG.clicked.connect(self.toggleImaging)
        self.toplout2.addWidget(self.acquiringG)

        self.previewG.setText('Preview')
        self.previewG.setCheckable(True)
        self.previewG.setStyleSheet("background-color : lightgray")
        self.previewG.clicked.connect(self.togglePreview)
        self.toplout2.addWidget(self.previewG)

        self.savingG.setText('Storing')
        self.savingG.setCheckable(True)
        self.savingG.setStyleSheet("background-color : lightgray")
        self.savingG.clicked.connect(self.toggleSaving)
        self.toplout2.addWidget(self.savingG)

        self.filteringG.setText('Filtering')
        self.filteringG.setCheckable(True)
        self.filteringG.setStyleSheet("background-color : lightgray")
        self.filteringG.clicked.connect(self.toggleFiltering)
        self.toplout2.addWidget(self.filteringG)

        if self.camHand.color:
            self.channelG.setText('RGB: All Channels')
        else:
            self.channelG.setText('Monochrome')
            self.channelG.setEnabled(False)
        self.channelG.setCheckable(False)
        self.channelG.setStyleSheet("background-color : lightgray")
        self.channelG.clicked.connect(self.switchChannel)
        self.toplout2.addWidget(self.channelG)

    def createScreens(self):
        self.screennorm.setScaledContents(True)
        self.screenbw.setScaledContents(True)
        self.screens.addWidget(self.screennorm)
        self.screens.addWidget(self.screenbw)

    def createFilterSettings(self):
        self.filterset.setCheckable(True)
        self.filterset.setChecked(True)
        self.filterl.addWidget(QtW.QLabel('Binarization Threshold'), 1, 1)
        self.bint.setMaximum(255)
        self.bint.setMinimum(0)
        self.bint.valueChanged.connect(self.changeBint)
        self.filterl.addWidget(self.bint, 1, 2)
        self.filterl.addWidget(QtW.QLabel('Contrast Multiplier'), 2, 1)
        self.alpha.setMaximum(5.0)
        self.alpha.setMinimum(0.1)
        self.alpha.setSingleStep(0.1)
        self.alpha.valueChanged.connect(self.changeAlpha)
        self.filterl.addWidget(self.alpha, 2, 2)
        self.filterl.addWidget(QtW.QLabel('Color Correction Constant'), 3, 1)
        self.beta.setMaximum(255)
        self.beta.setMinimum(-255)
        self.beta.valueChanged.connect(self.changeBeta)
        self.filterl.addWidget(self.beta, 3, 2)
        self.filterl.addWidget(QtW.QLabel('Filter Type'), 4, 1)
        self.filt.addItem('No Blur Filter')
        self.filt.addItem('Box Filter')
        self.filt.addItem('Gaussian Filter')
        self.filt.addItem('Median Filter')
        self.filt.activated.connect(self.changeFilterType)
        self.filterl.addWidget(self.filt, 4, 2)
        self.filterl.addWidget(QtW.QLabel('Filter Kernel Width'), 5, 1)
        self.filtw.setMaximum(15)
        self.filtw.setMinimum(1)
        self.filtw.valueChanged.connect(self.changeKernelWidth)
        self.filterl.addWidget(self.filtw, 5, 2)
        self.filterl.addWidget(QtW.QLabel('Filter Kernel Height'), 6, 1)
        self.filth.setMaximum(15)
        self.filth.setMinimum(1)
        self.filth.valueChanged.connect(self.changeKernelHeight)
        self.filterl.addWidget(self.filth, 6, 2)
        self.filterset.setLayout(self.filterl)

    def updateInfo(self):
        self.fpsG.setText('Display Fps: %2.2f' % self.fps)
        self.thrcntG.setText('Thread Count: %d' % self.thrcnt)
        self.framecountG.setText('Acquired Frames: %d' % self.framecount)
        self.savecountG.setText('Saved Frames: %d' % self.savecount)

    def updateDevicelist(self):
        self.deviceListG.clear()
        self.camHand.harvester.update()
        length = len(self.camHand.harvester.device_info_list)
        if length == 0:
            self.deviceListG.addItem('No devices found')
        else:
            for i in range(length):
                devinf = self.camHand.harvester.device_info_list[i]
                self.deviceListG.addItem(devinf.vendor + ' ' + devinf.model)
            self.deviceListG.addItem('Disable active device')

    def changeActiveDevice(self):
        actdev = self.deviceListG.currentIndex()
        if actdev != -1:
            self.camHand.changeCam(actdev)
        if self.camHand.cam is None:
            self.deviceListG.setStyleSheet("background-color : white")
        else:
            self.deviceListG.setStyleSheet("background-color : lightgreen")

    def changeSaveDirectory(self):
        newdir = self.savepathG.text()
        ret = self.camHand.changeSaveDir(newdir)
        if not ret:
            self.savepathG.setStyleSheet("background-color : red")
            self.savingG.setEnabled(False)
        else:
            self.savepathG.setStyleSheet("background-color : white")
            self.savingG.setEnabled(True)

    def toggleImaging(self):
        if self.camHand.cam is not None:
            if self.acquiringG.isChecked():
                self.acquiringG.setStyleSheet("background-color : lightgreen")
                self.camHand.acquire = True
                self.triggerG.setEnabled(False)
                self.framecount = 0
                self.savecount = 0
                self.imageRet.start()
            else:
                self.camHand.acquire = False
                self.camHand.sync = False
                self.triggerG.setEnabled(True)
                self.updateInfo()
                self.acquiringG.setStyleSheet("background-color : lightgray")
        else:
            self.acquiringG.setChecked(False)
            self.acquiringG.setStyleSheet("background-color : lightgray")

    def togglePreview(self):
        if self.previewG.isChecked():
            self.previewG.setStyleSheet("background-color : lightgreen")
        else:
            self.previewG.setStyleSheet("background-color : lightgray")

    def toggleSaving(self):
        if self.savingG.isChecked():
            self.savingG.setStyleSheet("background-color : lightgreen")
            self.camHand.saving = True
        else:
            self.savingG.setStyleSheet("background-color : lightgray")
            self.camHand.saving = False

    def switchChannel(self):
        if self.channelG.text() == "RGB: All Channels":
            self.channelG.setText("RGB: Red Channel")
            self.channelG.setStyleSheet("background-color : rgba(255, 0, 0, 30%)")
            self.channel = 1
        elif self.channelG.text() == "RGB: Red Channel":
            self.channelG.setText("RGB: Green Channel")
            self.channelG.setStyleSheet("background-color : rgba(0, 255, 0, 30%)")
            self.channel = 2
        elif self.channelG.text() == "RGB: Green Channel":
            self.channelG.setText("RGB: Blue Channel")
            self.channelG.setStyleSheet("background-color : rgba(0, 0, 255, 30%)")
            self.channel = 3
        else:
            self.channelG.setText("RGB: All Channels")
            self.channelG.setStyleSheet("background-color : lightgray")
            self.channel = 0

    def toggleFiltering(self):
        if self.filteringG.isChecked():
            self.filteringG.setStyleSheet("background-color : lightgreen")
            self.camHand.filtering = True
        else:
            self.filteringG.setStyleSheet("background-color : lightgray")
            self.camHand.filtering = False

    def toggleTrigger(self):
        if self.triggerG.isChecked():
            self.triggerG.setStyleSheet("background-color : lightgreen")
            self.camHand.toggleTrigger()
        else:
            self.triggerG.setStyleSheet("background-color : lightgray")
            self.camHand.toggleTrigger()

    def setInit(self):
        if self.camHand.savepth is not None:
            self.savepathG.setText(self.camHand.savepth[:-1])
        self.bint.setValue(self.camHand.filtcfg.binthr)
        self.alpha.setValue(self.camHand.filtcfg.alpha)
        self.beta.setValue(self.camHand.filtcfg.beta)
        self.filt.setCurrentIndex(self.camHand.filtcfg.filt)
        self.filtw.setValue(self.camHand.filtcfg.filtw)
        self.filth.setValue(self.camHand.filtcfg.filth)

    def changeBint(self):
        self.camHand.filtcfg.binthr = self.bint.value()

    def changeAlpha(self):
        self.camHand.filtcfg.alpha = self.alpha.value()

    def changeBeta(self):
        self.camHand.filtcfg.beta = self.beta.value()

    def changeFilterType(self):
        self.camHand.filtcfg.filt = self.filt.currentIndex()
        if self.filt.currentIndex() > 1:
            if self.filtw.value() % 2 == 0:
                self.filtw.setValue(self.filtw.value() - 1)
            if self.filth.value() % 2 == 0:
                self.filth.setValue(self.filth.value() - 1)

    def changeKernelWidth(self):
        newval = self.filtw.value()
        if self.camHand.filtcfg.filt > 1 and newval % 2 == 0:
            self.filtw.setValue(newval - 1)
        else:
            self.camHand.filtcfg.filtw = newval

    def changeKernelHeight(self):
        newval = self.filth.value()
        if self.camHand.filtcfg.filt > 1 and newval % 2 == 0:
            self.filth.setValue(newval - 1)
        else:
            self.camHand.filtcfg.filth = newval

    def pollThreads(self):
        self.thrcnt = 0
        freethr = -1
        if self.imageRet.isRunning():
            self.thrcnt += 1
        for i in range(len(self.imageSaverList)):
            if self.imageSaverList[i].isRunning():
                self.thrcnt += 1
            elif freethr == -1:
                freethr = i
        self.updateInfo()
        return freethr

    def closeEvent(self, e):
        if self.camHand.cam is not None:
            self.camHand.cam.stop_acquisition()
            self.camHand.cam.destroy()
        self.camHand.harvester.reset()
        self.camHand.filtcfg.save()
        self.camHand.save()
        self.errlog.close()
        e.accept()

    @QtC.pyqtSlot(numpy.ndarray, str)
    def drawImage(self, arr, tstamp):
        self.framecount += 1
        arr, arrbw = self.camHand.filtImag(arr, self.channel)
        thr = self.pollThreads()
        if self.camHand.saving:
            if thr < 0:
                self.errlog.write(
                    "ERROR: No save threads availible, TS:{0}, FrameCount:{1}".format(tstamp, self.framecount))
            else:
                self.imageSaverList[thr].tstamp = tstamp
                self.imageSaverList[thr].bw = arrbw
                self.imageSaverList[thr].start(QtC.QThread.Priority.HighPriority)
        if self.previewG.isChecked():
            if self.camHand.color:
                qimg = QtG.QImage(arr.data, arr.shape[1], arr.shape[0], arr.shape[1],
                                  QtG.QImage.Format_RGB888)
                qfiltimg = QtG.QImage(arrbw.data, arrbw.shape[1], arrbw.shape[0], arrbw.shape[1],
                                      QtG.QImage.Format_RGB888)
            else:
                qimg = QtG.QImage(arr.data, arr.shape[1], arr.shape[0], arr.shape[1],
                                  QtG.QImage.Format_Grayscale8)
                qfiltimg = QtG.QImage(arrbw.data, arrbw.shape[1], arrbw.shape[0], arrbw.shape[1],
                                      QtG.QImage.Format_Grayscale8)
            qimg = qimg.scaled(0.85 * self.screennorm.size())
            qfiltimg = qfiltimg.scaled(0.85 * self.screenbw.size())
            frame = QtG.QPixmap.fromImage(qimg)
            filtframe = QtG.QPixmap.fromImage(qfiltimg)
            self.screennorm.setPixmap(frame)
            self.screenbw.setPixmap(filtframe)
        if self.drawimagcount == 10:
            self.stop = time.time()
            self.fps = (1 / ((self.stop - self.start) / 10))
            self.start = time.time()
            self.drawimagcount = 0
        self.updateInfo()
        self.drawimagcount += 1

    @QtC.pyqtSlot()
    def imageSaved(self):
        self.savecount += 1
        self.updateInfo()
