import traceback

import PyQt5.QtWidgets as QtW
import PyQt5.QtCore as QtC
import PyQt5.QtGui as QtG
from camHandler import CamHandler, pcktsizes
from genicam import genapi, gentl
import time
import numpy


# Class for image acquisition thread, based on QThread
class ImageThread(QtC.QThread):
    # Set a signal to be sent if acquisition is successful
    # The signal contains the image and timestamp used for further processing
    imageAcquired = QtC.pyqtSignal(numpy.ndarray, str)

    # Initialization method
    # input: handler, programs camHandler object
    def __init__(self, handler):
        super().__init__()  # Init the QThread
        self.camHand = handler  # Set the thread camHandler to match the programs

    # Method defining the runtime behaviour
    def run(self):
        self.camHand.cam.start_acquisition()  # Signal the device to start acquiring images
        while self.camHand.acquire:  # Loop acquisition as long as the camHandler defines
            arr, tstamp = self.camHand.acquireImag()  # Use camHandler method to acquire a single frame
            if arr is not None:  # If the image is valid send the image for further processing
                self.imageAcquired.emit(arr, tstamp)

        retry = 0
        while retry < 10:  # Retry the acquisition shut down for up to 10 times
            try:
                self.camHand.cam.stop_acquisition()  # Signal the device to stop image acquisition
                break
            except Exception as e:
                if retry == 0:  # If shut down is not completed on first try log a warning
                    self.camHand.logerror("Warning: Exception catched while stopping acquisition, Retrying")
                retry = retry + 1
                time.sleep(0.5)
                if retry == 10:  # If shut down is not completed after 10 tries log an error
                    self.camHand.logerror("ERROR: Stopping acquisition failed after 10 retries")


# Class for image saving thread, based on QThread
class SaveThread(QtC.QThread):
    # Set a signal to be sent after an image is saved
    imageSaved = QtC.pyqtSignal()

    # Initialization method
    # input: handler, programs camHandler object
    def __init__(self, handler):
        super().__init__()  # Init the QThread
        self.camHand = handler  # Set the thread camHandler to match the programs
        self.bw = None  # Init a variable for current image
        self.tstamp = None  # Init a variable for current timestamp

    def run(self):
        self.camHand.saveImag(self.bw, self.tstamp)  # Use the camHandler method to save the image
        self.imageSaved.emit()  # Emit a signal to notify image saving is completed


# Class for screen gui element, based on QLabel
class Screen(QtW.QLabel):

    # Initialization method
    def __init__(self):
        super().__init__()  # Init the QLabel
        self.img = None  # Init a variable for current image
        self.previewrect = QtC.QRect(0, 0, 0, 0)  # Init a QRect object to preview partial scan area
        self.prev = False  # Bool, Is the preview rectangle active?
        self.setStyleSheet("border:1px solid gray")

    # Method that describes Screen object drawing behaviour
    def paintEvent(self, event):
        if self.img is not None:  # If the image is valid draw it on the screen
            size = self.size()
            painter = QtG.QPainter(self)
            scimg = self.img.scaled(size.width() - 2, size.height() - 2, QtC.Qt.AspectRatioMode.KeepAspectRatio)
            point = QtC.QPoint((size.width()-scimg.width())/2, (size.height()-scimg.height())/2)
            painter.drawImage(point, scimg)
            if self.prev:  # If partial scan preview is enabled draw the preview rectangle on the screen
                trans = QtG.QTransform()
                trans.translate(point.x(), point.y())
                trans.scale(scimg.width()/self.img.width(), scimg.height()/self.img.height())
                painter.setPen(QtG.QPen(QtG.QColor("red")))
                painter.setTransform(trans)
                painter.drawRect(self.previewrect)

    # Method for setting a new image as the current one
    def setImage(self, qimg):
        self.img = qimg
        self.repaint()  # Calling a repaint to update the graphics on screen


# Class for the main GUI, based on QMainWindow
class GUI(QtW.QMainWindow):

    # Initialization method
    def __init__(self):
        super().__init__()  # Init the QMainWindow
        self.setCentralWidget(QtW.QWidget())  # QMainWindow must have a centralWidget to be able to add layouts
        self.mainlout = QtW.QGridLayout()  # Init the main layout as a grid
        self.centralWidget().setLayout(self.mainlout)
        self.setWindowTitle('GenICam Handler v1.1')
        QtW.QApplication.setStyle(QtW.QStyleFactory.create('Windows'))

        savethrnum = 6  # Number of threads to be used in saving of images
        # Timer variables and image counter for FPS counter
        self.start = 0
        self.stop = 1
        self.drawimagcount = 0

        # Variables for storing the default image size parameters
        self.defW = 0
        self.defH = 0
        self.defOffX = 0
        self.defOffY = 0

        # Create the camHandler object for the program and init imaging and saving threads
        self.camHand = CamHandler()
        self.imageRet = ImageThread(self.camHand)
        self.imageRet.imageAcquired.connect(self.drawImage)
        self.imageSaverList = []
        for i in range(savethrnum):
            self.imageSaverList.append(SaveThread(self.camHand))
            self.imageSaverList[i].imageSaved.connect(self.increaseSaved)

        # Create the top layout and GUI elements for top layout controls
        self.toplout = QtW.QHBoxLayout()
        self.deviceListG = QtW.QComboBox()
        self.usedevG = QtW.QPushButton()
        self.updtListG = QtW.QPushButton()
        self.savepathG = QtW.QLineEdit()

        # Create the Handler Properties group GUI elements
        self.handlerpropset = QtW.QGroupBox("Handler Properties")
        self.handlerproplout = QtW.QGridLayout()
        self.triggerG = QtW.QPushButton()
        self.acquiringG = QtW.QPushButton()
        self.previewG = QtW.QPushButton()
        self.savingG = QtW.QPushButton()

        # Create the screen for image drawing
        self.screen = Screen()

        # Create and Initialize the Info group GUI elements
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

        # Create Image Properties group GUI elements
        self.imagepropset = QtW.QGroupBox("Image Properties")
        self.imageproplout = QtW.QGridLayout()
        self.pixform = None
        self.formatG = QtW.QPushButton()
        self.formatLG = QtW.QLabel()
        self.rotateG = QtW.QPushButton()
        self.rotationG = QtW.QComboBox()
        self.threshG = QtW.QPushButton()
        self.bint = QtW.QSpinBox()
        self.gainG = QtW.QDoubleSpinBox()
        self.exposureG = QtW.QSpinBox()
        self.partialG = QtW.QPushButton()
        self.partialprevG = QtW.QPushButton()

        # Create the Partial Scan Properties group GUI elements
        self.partialset = QtW.QGroupBox("Partial Scan Properties")
        self.partiallout = QtW.QGridLayout()
        self.partialHG = QtW.QSpinBox()
        self.partialWG = QtW.QSpinBox()
        self.partialoffYG = QtW.QSpinBox()
        self.partialoffXG = QtW.QSpinBox()

        # Create the Network Properties group GUI elements
        self.connpropset = QtW.QGroupBox("Network Properties")
        self.connproplout = QtW.QGridLayout()
        self.packetSizeG = QtW.QComboBox()
        self.packetIntervalG = QtW.QSpinBox()
        self.frameDelayG = QtW.QSpinBox()
        self.bufferG = QtW.QSpinBox()
        self.limitFPStogG = QtW.QPushButton()
        self.limitFPSvalG = QtW.QSpinBox()

        # Initialize the rest of the layouts
        self.createUITop()
        self.createHandlerProperties()
        self.createImageProperties()
        self.createNetworkProperties()

        # Load camHandler settings and update GUI elements
        self.setInit()
        self.updateDevicelist()
        self.updateDeviceInfo()

        # Add sub-layouts to the main layout and make the GUI visible
        self.mainlout.addLayout(self.toplout, 1, 1, 1, 2)
        self.mainlout.addWidget(self.handlerpropset, 2, 1, 1, 1)
        self.mainlout.addWidget(self.screen, 2, 2, 6, 1)
        self.mainlout.addWidget(self.imagepropset, 3, 1, 1, 1)
        self.mainlout.addWidget(self.connpropset, 4, 1, 1, 1)
        self.mainlout.addWidget(self.infobox, 5, 1, 1, 1)
        self.show()

        # Set fixed sizes for group boxes and resize the window
        self.handlerpropset.setFixedSize(self.handlerpropset.size())
        self.infobox.setFixedSize(self.infobox.size())
        self.imagepropset.setFixedSize(self.imagepropset.size())
        self.connpropset.setFixedSize(self.connpropset.size())
        self.resize(1000, 600)
        self.move(0, 0)

    # Method for Initializing the top bar layout
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

    # Method for initializing the Handler Properties group box
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

    # Method for initializing the Image Properties group box
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

        self.rotateG.setText('Rotation')
        self.rotateG.setStyleSheet("background-color : lightgray")
        self.rotateG.clicked.connect(self.toggleRotation)
        self.rotationG.addItem("90")
        self.rotationG.addItem("180")
        self.rotationG.addItem("270")
        self.rotationG.currentIndexChanged.connect(self.changeRotation)
        self.imageproplout.addWidget(self.rotateG, 3, 1)
        self.imageproplout.addWidget(self.rotationG, 3, 2)

        self.imageproplout.addWidget(QtW.QLabel("Gain (dB)"), 4, 1)
        self.gainG.setSingleStep(0.1)
        self.gainG.valueChanged.connect(self.changeGain)
        self.imageproplout.addWidget(self.gainG, 4, 2)

        self.imageproplout.addWidget(QtW.QLabel("Exposure Time (µs)"), 5, 1)
        self.exposureG.valueChanged.connect(self.changeExposure)
        self.imageproplout.addWidget(self.exposureG, 5, 2)

        self.imageproplout.addWidget(self.partialset, 6, 1, 1, 2)
        self.imagepropset.setLayout(self.imageproplout)

    # Method for initializing the Network Properties group box
    def createNetworkProperties(self):
        self.connproplout.addWidget(QtW.QLabel("Packet Size (B)"), 1, 1)
        for i in pcktsizes:
            self.packetSizeG.addItem("%d" % i)
        self.packetSizeG.currentIndexChanged.connect(self.changePcktSize)
        self.connproplout.addWidget(self.packetSizeG, 1, 2)

        self.connproplout.addWidget(QtW.QLabel("Packet Interval (ticks)"), 2, 1)
        self.packetIntervalG.valueChanged.connect(self.changePcktInterval)
        self.connproplout.addWidget(self.packetIntervalG, 2, 2)

        self.connproplout.addWidget(QtW.QLabel("Frame Delay (ticks)"), 3, 1)
        self.frameDelayG.valueChanged.connect(self.changeFrameDelay)
        self.connproplout.addWidget(self.frameDelayG, 3, 2)

        self.connproplout.addWidget(QtW.QLabel("Number of Buffers"), 4, 1)
        self.bufferG.setMinimum(1)
        self.bufferG.setMaximum(50)
        self.bufferG.valueChanged.connect(self.changeBuf)
        self.connproplout.addWidget(self.bufferG, 4, 2)

        self.limitFPStogG.setText("Limit FPS")
        self.limitFPStogG.setStyleSheet("background-color : lightgray")
        self.limitFPStogG.setCheckable(True)
        self.limitFPStogG.clicked.connect(self.toggleFPSLimit)
        self.connproplout.addWidget(self.limitFPStogG, 5, 1)
        self.limitFPSvalG.valueChanged.connect(self.changeFPSLimit)
        self.connproplout.addWidget(self.limitFPSvalG, 5, 2)
        self.connpropset.setLayout(self.connproplout)

    # Method for updating Info group elements
    def updateInfo(self):
        self.fpsG.setText('FPS: %.2f' % self.fps)
        self.framecountG.setText('Acquired Frames: %d' % self.framecount)
        self.savecountG.setText('Saved Frames: %d' % self.savecount)
        self.bufferG.setValue(self.camHand.bufnum)

    # Method for updating all device related elements (except device list)
    def updateDeviceInfo(self):
        if self.camHand.camprops is not None:
            cam = self.camHand
            if cam.getProperty("Width") is not None:
                self.imageWG.setText('Image Width: %d' % cam.getProperty("Width"))
                self.partialWG.setMaximum(cam.getProperty("MaxWidth"))
                self.partialWG.setMinimum(cam.getProperty("MinWidth"))
                self.partialoffXG.setMaximum(cam.getProperty("MaxWidth") - cam.partw)
            if cam.getProperty("Height") is not None:
                self.imageHG.setText('Image Height: %d' % cam.getProperty("Height"))
                self.partialHG.setMaximum(cam.getProperty("MaxHeight"))
                self.partialHG.setMinimum(cam.getProperty("MinHeight"))
                self.partialoffYG.setMaximum(cam.getProperty("MaxHeight") - cam.parth)
            if cam.getProperty("MaxFPS") is not None:
                self.maxfpsG.setText('Max FPS: %.2f' % cam.getProperty("MaxFPS"))
            self.partialHG.setValue(self.camHand.parth)
            self.partialWG.setValue(self.camHand.partw)
            self.partialoffXG.setValue(self.camHand.offsetx)
            self.partialoffYG.setValue(self.camHand.offsety)
            self.updatePreviewRect()
            if cam.getProperty("Gain") is not None:
                self.gainG.blockSignals(True)
                self.gainG.setMaximum(cam.getProperty("MaxGain"))
                self.gainG.setValue(cam.getProperty("Gain"))
                self.gainG.blockSignals(False)
            if cam.getProperty("ExposureTime") is not None:
                self.exposureG.blockSignals(True)
                self.exposureG.setMaximum(cam.getProperty("MaxExposureTime"))
                self.exposureG.setMinimum(cam.getProperty("MinExposureTime"))
                self.exposureG.setValue(cam.getProperty("ExposureTime"))
                self.exposureG.blockSignals(False)
            pixform = cam.getProperty("PixelFormat")
            if pixform == 'BayerRG8':
                self.formatLG.setText('RGB')
            elif pixform == 'Mono8':
                self.formatLG.setText('Monochrome')
            else:
                self.formatLG.setText('Unknown')
            if cam.getProperty("PacketInterval") is not None:
                self.packetIntervalG.blockSignals(True)
                self.packetIntervalG.setMinimum(cam.getProperty("MinPacketInterval"))
                self.packetIntervalG.setMaximum(cam.getProperty("MaxPacketInterval"))
                self.packetIntervalG.setValue(cam.getProperty("PacketInterval"))
                self.packetIntervalG.blockSignals(False)
            if cam.getProperty("PacketSize") is not None:
                self.packetSizeG.setCurrentIndex(cam.getProperty("PacketSize"))
            if cam.getProperty("FrameDelay") is not None:
                self.frameDelayG.blockSignals(True)
                self.frameDelayG.setMaximum(cam.getProperty("MaxFrameDelay"))
                self.frameDelayG.setMinimum(cam.getProperty("MinFrameDelay"))
                self.frameDelayG.setValue(cam.getProperty("FrameDelay"))
                self.frameDelayG.blockSignals(False)
                self.frameDelayG.setEnabled(True)
            else:
                self.frameDelayG.setEnabled(False)
            if cam.getProperty("FPS") is not None:
                self.limitFPSvalG.blockSignals(True)
                self.limitFPSvalG.setMaximum(int(cam.getProperty("MaxFPS")))
                self.limitFPSvalG.setMinimum(int(cam.getProperty("MinFPS")))
                if not cam.limit:
                    cam.setProperty("FPS", cam.getProperty("MaxFPS"))
                self.limitFPSvalG.setValue(self.camHand.fpslimit)
                self.limitFPSvalG.blockSignals(False)
        else:
            self.connpropset.setEnabled(False)
            self.imagepropset.setEnabled(False)
            self.imageWG.setText('Image Width: N/A')
            self.imageHG.setText('Image Height: N/A')
            self.maxfpsG.setText('Max FPS: N/A')
            self.formatLG.setText('N/A')
        self.updateInfo()

    # Method for updating the device list
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

    # Method for toggling the use of the current device in the list
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

    # Method for changing the image save directory
    def changeSaveDirectory(self):
        newdir = self.savepathG.text()
        ret = self.camHand.changeSaveDir(newdir)
        if not ret:
            self.savepathG.setStyleSheet("background-color : red")
            self.savingG.setEnabled(False)
        else:
            self.savepathG.setStyleSheet("background-color : white")
            self.savingG.setEnabled(True)

    # Control method for toggling the image acquisition
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
                self.limitFPStogG.setEnabled(False)
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
                self.limitFPStogG.setEnabled(True)
                self.imageRet.wait()  # Avoid race conditions
                self.updateDeviceInfo()
                self.acquiringG.setStyleSheet("background-color : lightgray")
        else:
            self.acquiringG.setChecked(False)
            self.acquiringG.setStyleSheet("background-color : lightgray")

    # Control method for toggling the image preview
    def togglePreview(self):
        if self.previewG.isChecked():
            self.previewG.setStyleSheet("background-color : lightgreen")
        else:
            self.previewG.setStyleSheet("background-color : lightgray")

    # Control method for toggling the image saving
    def toggleSaving(self):
        if self.savingG.isChecked():
            self.savingG.setStyleSheet("background-color : lightgreen")
            self.camHand.saving = True
        else:
            self.savingG.setStyleSheet("background-color : lightgray")
            self.camHand.saving = False

    # Control method for switching between pixel formats
    def switchFormat(self):
        if self.camHand.cam is not None:
            if self.camHand.getProperty("PixelFormat") == 'BayerRG8':
                try:
                    self.camHand.setProperty("PixelFormat", 'Mono8')
                    self.updateDeviceInfo()
                except genapi.LogicalErrorException:
                    pass
            else:
                try:
                    self.camHand.setProperty("PixelFormat", 'BayerRG8')
                    self.updateDeviceInfo()
                except genapi.LogicalErrorException:
                    pass

    # Control method for toggling thresholding
    def toggleThersh(self):
        if self.threshG.isChecked():
            self.threshG.setStyleSheet("background-color : lightgreen")
            self.camHand.filtering = True
        else:
            self.threshG.setStyleSheet("background-color : lightgray")
            self.camHand.filtering = False

    # Control method for toggling the triggered acquisition
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

    # Control method for toggling the partial scanning
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
                if self.partialprevG.isChecked():
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

    # Control method for toggling partial scan preview rectangle
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

    # Control method for toggling the FPS limiter
    def toggleFPSLimit(self):
        if self.limitFPStogG.isChecked():
            if self.camHand.cam is not None:
                self.limitFPStogG.setStyleSheet("background-color : lightgreen")
                self.limitFPSvalG.setEnabled(False)
                self.camHand.toggleFPSLimit()
            else:
                self.limitFPStogG.setChecked(False)
        else:
            self.limitFPStogG.setStyleSheet("background-color : lightgray")
            self.limitFPSvalG.setEnabled(True)
            self.camHand.toggleFPSLimit()

    # Method for toggling image rotation
    def toggleRotation(self):
        if self.rotateG.isChecked():
            if self.camHand.cam is not None:
                self.rotateG.setStyleSheet("background-color : lightgreen")
                self.camHand.rotate = True
        else:
            self.rotateG.setStyleSheet("background-color : lightgray")

    # Method for loading camHand options and updating the responding GUI elements
    def setInit(self):
        if self.camHand.savepth is not None:
            self.savepathG.setText(self.camHand.savepth[:-1])
        self.bint.setValue(self.camHand.thrsh)

    # Method for updating the correct image rotation angle
    def changeRotation(self):
        self.camHand.rotation = (self.rotationG.currentIndex() + 1) * 90

    # Method for updating FPS limit variable
    def changeFPSLimit(self):
        self.camHand.fpslimit = self.limitFPSvalG.value()

    # Method for updating number of buffers
    def changeBuf(self):
        self.camHand.changeBufnum(self.bufferG.value())

    # Method for updating the threshold
    def changeBint(self):
        self.camHand.thrsh = self.bint.value()

    # Method for updating frame delay
    def changeFrameDelay(self):
        self.camHand.setProperty("FrameDelay", self.frameDelayG.value())

    # Method for updating the partial scan preview rectangle
    def updatePreviewRect(self):
        x = self.partialoffXG.value()
        y = self.partialoffYG.value()
        w = self.partialWG.value()
        h = self.partialHG.value()
        self.screen.previewrect = QtC.QRect(x, y, w, h)

    # Method for updating the exposure time
    def changeExposure(self):
        self.camHand.setProperty("ExposureTime", self.exposureG.value())

    # Method for updating the gain
    def changeGain(self):
        self.camHand.setProperty("Gain", self.gainG.value())

    # Method for updating the partial scan width
    def changePartialWidth(self):
        self.camHand.partw = self.partialWG.value()
        self.updatePreviewRect()

    # Method for updating the partial scan height
    def changePartialHeight(self):
        self.camHand.parth = self.partialHG.value()
        self.updatePreviewRect()

    # Method for updating the partial scan horizontal offset
    def changePartialOffsetX(self):
        self.camHand.offsetx = self.partialoffXG.value()
        self.updatePreviewRect()

    # Method for updating the partial scan vertical offset
    def changePartialOffsetY(self):
        self.camHand.offsety = self.partialoffYG.value()
        self.updatePreviewRect()

    # Method for updating the packet size
    def changePcktSize(self):
        ind = self.packetSizeG.currentIndex()
        self.camHand.setProperty("PacketSize", ind)

    # Method for updating the packet interval
    def changePcktInterval(self):
        self.camHand.setProperty("PacketInterval", self.packetIntervalG.value())

    # Method for polling free saving threads
    def pollThreads(self):
        freethr = -1
        for i in range(len(self.imageSaverList)):
            if not self.imageSaverList[i].isRunning():
                freethr = i
        return freethr

    # Method describing the program shutdown behaviour
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
        #self.camHand.save()
        self.camHand.closeerrlog()
        e.accept()

    # Method for drawing and saving the acquired image
    # Uses a slot to intercept the signal transmitted by the acquisition thread
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

    # Method to increase the saved image counter
    # Uses a slot to receive the image saved signal
    @QtC.pyqtSlot()
    def increaseSaved(self):
        self.savecount += 1
        self.updateInfo()
