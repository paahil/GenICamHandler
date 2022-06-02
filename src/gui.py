import PyQt5.QtWidgets as QtW
import PyQt5.QtCore as QtC
import PyQt5.QtGui as QtG
from camHandler import CamHandler, pcktsizes
import genicam.genapi
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
            arr, tstamp = self.camHand.acquireImag()
            if arr is not None:
                self.imageAcquired.emit(arr, tstamp)
        retry = 0
        while retry < 100:
            try:
                self.camHand.cam.stop_acquisition()
                break
            except genicam.genapi.AccessException:
                retry = retry + 1
                time.sleep(0.1)


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


class Screen(QtW.QLabel):
    def __init__(self):
        super().__init__()
        self.prev = False
        self.img = None
        self.previewrect = QtC.QRect(0, 0, 0, 0)
        self.setStyleSheet("border:1px solid gray")

    def paintEvent(self, event):
        if self.img is not None:
            size = self.size()
            painter = QtG.QPainter(self)
            scimg = self.img.scaled(size.width() - 2, size.height() - 2, QtC.Qt.AspectRatioMode.KeepAspectRatio)
            point = QtC.QPoint((size.width()-scimg.width())/2, (size.height()-scimg.height())/2)
            painter.drawImage(point, scimg)
            if self.prev:
                trans = QtG.QTransform()
                trans.translate(point.x(), point.y())
                trans.scale(scimg.width()/self.img.width(), scimg.height()/self.img.height())
                painter.setPen(QtG.QPen(QtG.QColor("red")))
                painter.setTransform(trans)
                painter.drawRect(self.previewrect)

    def setImage(self, qimg):
        self.img = qimg
        self.repaint()


class GUI(QtW.QMainWindow):

    def __init__(self):
        super().__init__()
        self.setCentralWidget(QtW.QWidget())  # QMainWindow must have a centralWidget to be able to add layouts
        self.mainlout = QtW.QGridLayout()
        self.centralWidget().setLayout(self.mainlout)
        self.setWindowTitle('GenICam Handler v1.1')
        QtW.QApplication.setStyle(QtW.QStyleFactory.create('Windows'))

        savethrnum = 6  # Number of threads to be used in saving of images
        self.start = 0
        self.stop = 1
        self.drawimagcount = 0
        self.sstart = 0
        self.sstop = 1
        self.defW = 0
        self.defH = 0
        self.defOffX = 0
        self.defOffY = 0

        self.camHand = CamHandler()
        self.imageRet = ImageThread(self.camHand)
        self.imageRet.imageAcquired.connect(self.drawImage)
        self.imageSaverList = []
        for i in range(savethrnum):
            self.imageSaverList.append(SaveThread(self.camHand))
            self.imageSaverList[i].imageSaved.connect(self.increaseSaved)

        self.toplout = QtW.QHBoxLayout()
        self.deviceListG = QtW.QComboBox()
        self.usedevG = QtW.QPushButton()
        self.updtListG = QtW.QPushButton()
        self.savepathG = QtW.QLineEdit()

        self.handlerpropset = QtW.QGroupBox("Handler Properties")
        self.handlerproplout = QtW.QGridLayout()
        self.triggerG = QtW.QPushButton()
        self.acquiringG = QtW.QPushButton()
        self.previewG = QtW.QPushButton()
        self.savingG = QtW.QPushButton()


        self.screen = Screen()
        self.pixform = None

        self.infobox = QtW.QGroupBox("Info")
        self.infolout = QtW.QGridLayout()
        self.fps = 0
        self.maxfps = 0
        self.framecount = 0
        self.savecount = 0
        self.fpsG = QtW.QLabel()
        self.maxfpsG = QtW.QLabel()
        self.maxfpsG.setText("Max FPS: 0.00")
        self.framecountG = QtW.QLabel()
        self.savecountG = QtW.QLabel()
        self.imageHG = QtW.QLabel()
        self.imageHG.setText("Image Height: 0")
        self.imageWG = QtW.QLabel()
        self.imageWG.setText("Image Width: 0")

        self.infolout.addWidget(self.maxfpsG, 1, 1)
        self.infolout.addWidget(self.fpsG, 1, 2)
        self.infolout.addWidget(self.framecountG, 2, 1)
        self.infolout.addWidget(self.savecountG, 2, 2)
        self.infolout.addWidget(self.imageWG, 3, 1)
        self.infolout.addWidget(self.imageHG, 3, 2)
        self.infobox.setLayout(self.infolout)

        self.imagepropset = QtW.QGroupBox("Image Properties")
        self.imageproplout = QtW.QGridLayout()
        self.formatG = QtW.QPushButton()
        self.formatLG = QtW.QLabel()
        self.threshG = QtW.QPushButton()
        self.bint = QtW.QSpinBox()
        self.gainG = QtW.QDoubleSpinBox()
        self.exposureG = QtW.QSpinBox()
        self.partialG = QtW.QPushButton()
        self.partialprevG = QtW.QPushButton()
        self.partialset = QtW.QGroupBox("Partial Scan Properties")
        self.partiallout = QtW.QGridLayout()
        self.partialHG = QtW.QSpinBox()
        self.partialWG = QtW.QSpinBox()
        self.partialoffYG = QtW.QSpinBox()
        self.partialoffXG = QtW.QSpinBox()

        self.connpropset = QtW.QGroupBox("Network Properties")
        self.connproplout = QtW.QGridLayout()
        self.packetSizeG = QtW.QComboBox()
        self.packetIntervalG = QtW.QSpinBox()
        self.bufferG = QtW.QSpinBox()

        self.createUITop()
        self.createHandlerProperties()
        self.createImageProperties()
        self.createNetworkProperties()

        self.setInit()
        self.updateDevicelist()
        self.updateDeviceInfo()

        self.mainlout.addLayout(self.toplout, 1, 1, 1, 2)
        self.mainlout.addWidget(self.handlerpropset, 2, 1, 1, 1)
        self.mainlout.addWidget(self.screen, 2, 2, 6, 1)
        self.mainlout.addWidget(self.imagepropset, 3, 1, 1, 1)
        self.mainlout.addWidget(self.connpropset, 4, 1, 1, 1)
        self.mainlout.addWidget(self.infobox, 5, 1, 1, 1)
        self.show()
        self.infobox.setFixedSize(self.infobox.size())
        self.imagepropset.setFixedSize(self.imagepropset.size())
        self.connpropset.setFixedSize(self.connpropset.size())
        self.resize(1000, 600)
        self.move(0, 0)

    def createUITop(self):
        savepathL = QtW.QLabel('Storage Folder:')
        self.updtListG.setText('Update List')
        self.updtListG.clicked.connect(self.updateDevicelist)
        self.updtListG.setStyleSheet("background-color : lightgray")
        self.savepathG.editingFinished.connect(self.changeSaveDirectory)
        self.usedevG.setText('Use')
        self.usedevG.clicked.connect(self.toggleCurrDevice)
        self.usedevG.setCheckable(True)
        self.usedevG.setStyleSheet("background-color : lightgray")
        self.toplout.addWidget(self.usedevG)
        self.toplout.addWidget(self.deviceListG, 1)
        self.toplout.addWidget(self.updtListG, 0)
        self.toplout.addWidget(savepathL)
        self.toplout.addWidget(self.savepathG, 4)

    def createHandlerProperties(self):
        self.triggerG.setText('Trigger')
        self.triggerG.setCheckable(True)
        self.triggerG.setStyleSheet("background-color : lightgray")
        self.triggerG.clicked.connect(self.toggleTrigger)
        self.handlerproplout.addWidget(self.triggerG, 1, 1)

        self.acquiringG.setText('Acquire')
        self.acquiringG.setCheckable(True)
        self.acquiringG.setStyleSheet("background-color : lightgray")
        self.acquiringG.clicked.connect(self.toggleImaging)
        self.handlerproplout.addWidget(self.acquiringG, 1, 2)

        self.previewG.setText('Preview')
        self.previewG.setCheckable(True)
        self.previewG.setStyleSheet("background-color : lightgray")
        self.previewG.clicked.connect(self.togglePreview)
        self.handlerproplout.addWidget(self.previewG, 2, 1)

        self.savingG.setText('Store')
        self.savingG.setCheckable(True)
        self.savingG.setStyleSheet("background-color : lightgray")
        self.savingG.clicked.connect(self.toggleSaving)
        self.handlerproplout.addWidget(self.savingG, 2, 2)

        self.handlerpropset.setLayout(self.handlerproplout)

    def createImageProperties(self):
        self.partialG.setText('Enable')
        self.partialG.setCheckable(True)
        self.partialG.setStyleSheet("background-color : lightgray")
        self.partialG.clicked.connect(self.togglePartial)
        self.partiallout.addWidget(self.partialG, 1, 1)
        self.partialprevG.setText('Preview')
        self.partialprevG.setCheckable(True)
        self.partialprevG.setStyleSheet("background-color : lightgray")

        self.partiallout.addWidget(self.partialprevG, 1, 2)
        self.partialprevG.clicked.connect(self.togglePartialPrev)
        self.partiallout.addWidget(QtW.QLabel("Width"), 2, 1)
        self.partialWG.setMinimum(2)
        self.partialWG.setSingleStep(2)
        self.partialWG.valueChanged.connect(self.changePartialWidth)
        self.partiallout.addWidget(self.partialWG, 2, 2)
        self.partiallout.addWidget(QtW.QLabel("Height"), 3, 1)
        self.partiallout.addWidget(self.partialHG, 3, 2)
        self.partialHG.setMinimum(2)
        self.partialHG.setSingleStep(2)
        self.partialHG.valueChanged.connect(self.changePartialHeight)
        self.partiallout.addWidget(QtW.QLabel("Offset X"), 4, 1)
        self.partiallout.addWidget(self.partialoffXG, 4, 2)
        self.partialoffXG.setSingleStep(2)
        self.partialoffXG.valueChanged.connect(self.changePartialOffsetX)
        self.partiallout.addWidget(QtW.QLabel("Offset Y"), 5, 1)
        self.partiallout.addWidget(self.partialoffYG, 5, 2)
        self.partialoffYG.setSingleStep(2)
        self.partialoffYG.valueChanged.connect(self.changePartialOffsetY)
        self.partialset.setLayout(self.partiallout)

        self.formatG.setText('Format')
        self.formatG.setStyleSheet("background-color : lightgray")
        self.formatG.clicked.connect(self.switchFormat)
        self.imageproplout.addWidget(self.formatG, 1, 1)
        self.imageproplout.addWidget(self.formatLG, 1, 2)
        self.threshG.setText('Threshold')
        self.threshG.setCheckable(True)
        self.threshG.setStyleSheet("background-color : lightgray")
        self.threshG.clicked.connect(self.toggleThersh)
        self.bint.setMaximum(255)
        self.bint.setMinimum(1)
        self.bint.valueChanged.connect(self.changeBint)
        self.imageproplout.addWidget(self.threshG, 2, 1)
        self.imageproplout.addWidget(self.bint, 2, 2)

        self.imageproplout.addWidget(QtW.QLabel("Gain (dB)"), 3, 1)
        self.gainG.setSingleStep(0.1)
        self.gainG.valueChanged.connect(self.changeGain)
        self.imageproplout.addWidget(self.gainG, 3, 2)

        self.imageproplout.addWidget(QtW.QLabel("Exposure Time (µs)"), 4, 1)
        self.exposureG.valueChanged.connect(self.changeExposure)
        self.imageproplout.addWidget(self.exposureG, 4, 2)

        self.imageproplout.addWidget(self.partialset, 5, 1, 1, 2)
        self.imagepropset.setLayout(self.imageproplout)


    def createNetworkProperties(self):
        self.connproplout.addWidget(QtW.QLabel("Packet Size (B)"), 1, 1)
        for i in pcktsizes:
            self.packetSizeG.addItem("%d" % i)
        self.packetSizeG.currentIndexChanged.connect(self.changePcktSize)
        self.connproplout.addWidget(self.packetSizeG, 1, 2)

        self.connproplout.addWidget(QtW.QLabel("Packet Interval (ticks)"), 2, 1)
        self.packetIntervalG.valueChanged.connect(self.changePcktInterval)
        self.connproplout.addWidget(self.packetIntervalG, 2, 2)

        self.connproplout.addWidget(QtW.QLabel("Number of Buffers"), 3, 1)
        self.bufferG.setMinimum(1)
        self.bufferG.setMaximum(50)
        self.bufferG.valueChanged.connect(self.changeBuf)
        self.connproplout.addWidget(self.bufferG, 3, 2)
        self.connpropset.setLayout(self.connproplout)

    def updateInfo(self):
        self.fpsG.setText('FPS: %.2f' % self.fps)
        self.framecountG.setText('Acquired Frames: %d' % self.framecount)
        self.savecountG.setText('Saved Frames: %d' % self.savecount)
        self.bufferG.setValue(self.camHand.bufnum)

    def updateDeviceInfo(self):
        if self.camHand.camprops is not None:
            cam = self.camHand
            self.imageWG.setText('Image Width: %d' % cam.getProperty("Width"))
            self.imageHG.setText('Image Height: %d' % cam.getProperty("Height"))
            self.maxfpsG.setText('Max FPS: %.2f' % cam.getProperty("MaxFPS"))
            self.partialWG.setMaximum(cam.getProperty("MaxWidth"))
            self.partialHG.setMaximum(cam.getProperty("MaxHeight"))
            self.partialWG.setMinimum(cam.getProperty("MinWidth"))
            self.partialHG.setMinimum(cam.getProperty("MinHeight"))
            self.partialoffXG.setMaximum(cam.getProperty("MaxWidth") - cam.partw)
            self.partialoffYG.setMaximum(cam.getProperty("MaxHeight") - cam.parth)
            self.partialHG.setValue(self.camHand.parth)
            self.partialWG.setValue(self.camHand.partw)
            self.partialoffXG.setValue(self.camHand.offsetx)
            self.partialoffYG.setValue(self.camHand.offsety)
            self.updatePreviewRect()
            self.gainG.setMaximum(cam.getProperty("MaxGain"))
            self.gainG.setValue(cam.getProperty("Gain"))
            self.exposureG.setMaximum(cam.getProperty("MaxExposureTime"))
            self.exposureG.setValue(cam.getProperty("ExposureTime"))
            self.exposureG.setMinimum(cam.getProperty("MinExposureTime"))
            pixform = cam.getProperty("PixelFormat")
            if pixform == 'BayerRG8':
                self.formatLG.setText('RGB')
            elif pixform == 'Mono8':
                self.formatLG.setText('Monochrome')
            else:
                self.formatLG.setText('Unknown')
            self.packetIntervalG.setMinimum(cam.getProperty("MinPacketInterval"))
            self.packetIntervalG.setMaximum(cam.getProperty("MaxPacketInterval"))
            self.packetIntervalG.setValue(cam.getProperty("PacketInterval"))
            self.packetSizeG.setCurrentIndex(cam.getProperty("PacketSize"))
        else:
            self.connpropset.setEnabled(False)
            self.imagepropset.setEnabled(False)
            self.imageWG.setText('Image Width: N/A')
            self.imageHG.setText('Image Height: N/A')
            self.maxfpsG.setText('Max FPS: N/A')
            self.formatLG.setText('N/A')
        self.updateInfo()

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

    def toggleCurrDevice(self):
        if self.usedevG.isChecked():
            actdev = self.deviceListG.currentIndex()
            if actdev != -1:
                self.camHand.changeCam(actdev)
            if self.camHand.cam is None:
                self.usedevG.setChecked(False)
            else:
                self.usedevG.setStyleSheet("background-color : lightgreen")
                self.updateDeviceInfo()
                self.connpropset.setEnabled(True)
                self.imagepropset.setEnabled(True)
        else:
            count = self.deviceListG.count()
            self.camHand.changeCam(count)
            self.usedevG.setStyleSheet("background-color : lightgray")
            self.updateDeviceInfo()


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
                self.formatG.setEnabled(False)
                self.partialG.setEnabled(False)
                self.usedevG.setEnabled(False)
                self.connpropset.setEnabled(False)
                self.pixform = self.camHand.getProperty("PixelFormat")
                self.framecount = 0
                self.savecount = 0
                self.updateDeviceInfo()
                self.imageRet.start()
            else:
                self.camHand.acquire = False
                self.camHand.sync = False
                self.triggerG.setEnabled(True)
                self.formatG.setEnabled(True)
                self.connpropset.setEnabled(True)
                self.partialG.setEnabled(True)
                self.usedevG.setEnabled(True)
                self.imageRet.wait()  # Avoid race conditions
                self.updateDeviceInfo()
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

    def switchFormat(self):
        if self.camHand.cam is not None:
            if self.camHand.getProperty("PixelFormat") == 'BayerRG8':
                try:
                    self.camHand.setProperty("PixelFormat", 'Mono8')
                    self.updateDeviceInfo()
                except genicam.genapi.LogicalErrorException:
                    pass
            else:
                try:
                    self.camHand.setProperty("PixelFormat", 'BayerRG8')
                    self.updateDeviceInfo()
                except genicam.genapi.LogicalErrorException:
                    pass

    def toggleThersh(self):
        if self.threshG.isChecked():
            self.threshG.setStyleSheet("background-color : lightgreen")
            self.camHand.filtering = True
        else:
            self.threshG.setStyleSheet("background-color : lightgray")
            self.camHand.filtering = False

    def toggleTrigger(self):
        if self.triggerG.isChecked():
            if self.camHand.cam is not None:
                self.triggerG.setStyleSheet("background-color : lightgreen")
                self.camHand.toggleTrigger()
            else:
                self.triggerG.setChecked(False)
        else:
            self.triggerG.setStyleSheet("background-color : lightgray")
            self.camHand.toggleTrigger()

    def togglePartial(self):
        if self.partialG.isChecked():
            if self.camHand.cam is not None:
                self.partialG.setStyleSheet("background-color : lightgreen")
                self.camHand.togglePartial()
                self.partialWG.setEnabled(False)
                self.partialHG.setEnabled(False)
                self.partialoffXG.setEnabled(False)
                self.partialoffYG.setEnabled(False)
                self.partialprevG.setChecked(False)
                self.togglePartialPrev()
                self.partialprevG.setEnabled(False)
            else:
                self.partialG.setChecked(False)
        else:
            self.partialG.setStyleSheet("background-color : lightgray")
            self.camHand.togglePartial()
            self.partialWG.setEnabled(True)
            self.partialHG.setEnabled(True)
            self.partialoffXG.setEnabled(True)
            self.partialoffYG.setEnabled(True)
            self.partialprevG.setEnabled(True)

    def togglePartialPrev(self):
        if self.partialprevG.isChecked():
            if self.camHand.cam is not None:
                self.partialprevG.setStyleSheet("background-color : lightgreen")
                self.screen.prev = True
            else:
                self.partialprevG.setChecked(False)
        else:
            self.partialprevG.setStyleSheet("background-color : lightgray")
            self.screen.prev = False

    def setInit(self):
        if self.camHand.savepth is not None:
            self.savepathG.setText(self.camHand.savepth[:-1])
        self.bint.setValue(self.camHand.thrsh)

    def changeBuf(self):
        self.camHand.changeBufnum(self.bufferG.value())

    def changeBint(self):
        self.camHand.thrsh = self.bint.value()

    def updatePreviewRect(self):
        x = self.partialoffXG.value()
        y = self.partialoffYG.value()
        w = self.partialWG.value()
        h = self.partialHG.value()
        self.screen.previewrect = QtC.QRect(x, y, w, h)

    def changeExposure(self):
        self.camHand.setProperty("ExposureTime", self.exposureG.value())

    def changeGain(self):
        self.camHand.setProperty("Gain", self.gainG.value())

    def changePartialWidth(self):
        self.camHand.partw = self.partialWG.value()
        self.updatePreviewRect()
        self.updateDeviceInfo()

    def changePartialHeight(self):
        self.camHand.parth = self.partialHG.value()
        self.updatePreviewRect()
        self.updateDeviceInfo()

    def changePartialOffsetX(self):
        self.camHand.offsetx = self.partialoffXG.value()
        self.updatePreviewRect()
        self.updateDeviceInfo()

    def changePartialOffsetY(self):
        self.camHand.offsety = self.partialoffYG.value()
        self.updatePreviewRect()
        self.updateDeviceInfo()

    def changePcktSize(self):
        ind = self.packetSizeG.currentIndex()
        self.camHand.setProperty("PacketSize", ind)

    def changePcktInterval(self):
        self.camHand.setProperty("PacketInterval", self.packetIntervalG.value())

    def pollThreads(self):
        freethr = -1
        for i in range(len(self.imageSaverList)):
            if not self.imageSaverList[i].isRunning():
                freethr = i
        return freethr

    def closeEvent(self, e):
        if self.camHand.cam is not None:
            if self.acquiringG.isChecked():
                self.acquiringG.setChecked(False)
                self.toggleImaging()
                self.imageRet.wait()  # Avoid race conditions
                if self.partialG.isChecked():
                    self.partialG.setChecked(False)
                    self.togglePartial()
            self.usedevG.setChecked(False)
            self.toggleCurrDevice()
        self.camHand.harvester.reset()
        self.camHand.save()
        self.camHand.closeerrlog()
        e.accept()

    @QtC.pyqtSlot(numpy.ndarray, str)
    def drawImage(self, arr, tstamp):
        self.framecount += 1
        imag = self.camHand.filtImag(arr)
        thr = self.pollThreads()
        if self.camHand.saving:
            if thr < 0:
                self.camHand.logerror("No save threads available, FrameCount:{0}".format(self.framecount))
            else:
                self.imageSaverList[thr].tstamp = tstamp
                self.imageSaverList[thr].bw = imag
                self.imageSaverList[thr].start(QtC.QThread.Priority.HighPriority)
        if self.previewG.isChecked():
            if self.pixform == 'BayerRG8':
                qimg = QtG.QImage(imag.data, imag.shape[1], imag.shape[0], QtG.QImage.Format_RGB888)
                self.screen.setImage(qimg)
            if self.pixform == 'Mono8':
                qimg = QtG.QImage(imag.data, imag.shape[1], imag.shape[0], QtG.QImage.Format_Grayscale8)
                self.screen.setImage(qimg)
        if self.drawimagcount == 10:
            self.stop = time.time()
            self.fps = (1 / ((self.stop - self.start) / 10))
            self.start = time.time()
            self.drawimagcount = 0
        self.updateInfo()
        self.drawimagcount += 1

    @QtC.pyqtSlot()
    def increaseSaved(self):
        self.savecount += 1
        self.updateInfo()
