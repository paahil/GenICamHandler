import math
import cv2 as cv
from harvesters.core import Harvester
import genicam.gentl
import genicam.genapi
import time
import datetime
import numpy
import os

# Static Defines
colorforms = ["BayerRG8"]
pcktsizes = [1440, 2960, 4480, 6000, 7520, 9040, 10560]

# Class for interfacing with the physical device

class CamHandler:
    # Class initialization
    def __init__(self):
        # Variables for storing runtime variables
        self.errlog = None  # Variable for current error log
        self.logfname = None  # Variable for the filename of the current error log
        self.cam = None  # Variable for current physical device
        self.camprops = None  # Variable shorthand to access properties of the current device
        self.savepth = None  # Variable for current save directory path
        self.thrsh = 0  # Variable for binarization threshold
        self.bufnum = 6  # Variable for used number of buffers
        self.partw = 256  # Variable for partial scan width (in pixels)
        self.parth = 256  # Variable for partial scan height (in pixels)
        self.offsetx = 900  # Variable for partial scan horizontal offset (in pixels)
        self.offsety = 900  # Variable for partial scan vertical offset (in pixels)
        self.fpslimit = 1  # Variable for FPS limit
        self.defH = 0  # Variable for saving the original height (for toggling partial scan off)
        self.defW = 0  # Variable for saving the original width (for toggling partial scan off)
        self.defOffX = 0  # Variable for saving the original horizontal offset (for toggling partial scan off)
        self.defOffY = 0  # Variable for saving the original vertical offset (for toggling partial scan off)
        self.rotation = 90  # Variable for saving the rotation angle (must be 90, 180 or 270)

        # Boolean variables for toggle switches
        self.limit = False  # Is the FPS limiter enabled?
        self.partial = False  # Is partial scanning enabled?
        self.triggering = False  # Is triggered acquisition enabled?
        self.acquire = False  # Is image acquisition enabled?
        self.filtering = False  # Is image filtering (thresholding) enabled?
        self.color = False  # Is the device using color format (BAYERNRG8)
        self.saving = False  # Is image storing enabled?
        self.rotate = False  # Is image rotation enabled?

        # Variables for timestamp usage
        self.systime0 = None  # Variable for system timestamp acquired with the first frame
        self.tstamp0 = 0  # Variable for device timestamp acquired with the first frame
        self.sync = False  # Are variables systime0 and tstamp0 synchronized i.e. frame count > 1

        self.harvester = Harvester()  # Initialize the harvester class
        #  Add a cti file to the harvester
        #  MODIFY THIS TO MATCH YOUR MATRIX VISION INSTALLATION PATH!!!
        self.harvester.add_file("C:\\Users\\Paavo\\Documents\\ADENN2021\\MATRIX VISION\\bin\\x64\\mvGenTLProducer.cti")
        #self.load()
        self.openerrlog()  # Open the error log for runtime logging

    # Method for loading saved configurations (Currently not used)
    def load(self):
        try:
            file = open('cfgs/default.cfgh', 'r')
            self.savepth = file.readline()[:-1]
            if self.savepth == 'None':
                self.savepth = None
            self.bufnum = int(file.readline())
            self.thrsh = int(file.readline())
            self.partw = int(file.readline())
            self.parth = int(file.readline())
            self.offsetx = int(file.readline())
            self.offsety = int(file.readline())
            file.close()
        except FileNotFoundError:
            pass

    # Method for saving current configurations for later use
    def save(self):
        file = open('cfgs/default.cfgh', 'w')
        file.write('%s\n' % self.savepth)
        file.write('%d\n' % self.bufnum)
        file.write('%d\n' % self.thrsh)
        file.write('%d\n' % self.partw)
        file.write('%d\n' % self.parth)
        file.write('%d\n' % self.offsetx)
        file.write('%d\n' % self.offsety)
        file.close()

    # Method for running the parameter load function on the end device
    def loadCameraProperties(self):
        if self.camprops is not None:
            try:
                self.camprops.get_node("UserSetSelector").value = "UserSet1"
                self.camprops.get_node("UserSetLoad").execute()
            except genicam.genapi.LogicalErrorException:
                try:
                    self.camprops.get_node("MemoryChannel").value = 1
                    self.camprops.get_node("LoadParameters").value = 'CameraParameters'
                    self.camprops.get_node("LoadParameters").value = 'CommonParameters'
                except genicam.genapi.LogicalErrorException:
                    pass

    # Method for running the parameter save function on the end device
    def saveCameraProperties(self):
        if self.camprops is not None:
            try:
                self.camprops.get_node("UserSetSelector").value = "UserSet1"
                self.camprops.get_node("UserSetSave").execute()
            except genicam.genapi.LogicalErrorException:
                try:
                    self.camprops.get_node("MemoryChannel").value = 1
                    self.camprops.get_node("SaveParameters").value = 'CameraParameters'
                    self.camprops.get_node("SaveParameters").value = 'CommonParameters'
                except genicam.genapi.LogicalErrorException:
                    pass

    # Method for initializing properties on the end device to comply with the software
    def initCamera(self):
        if self.camprops is not None:
            try:
                self.camprops.get_node("AutoGain").value = 'OFF'
                self.camprops.get_node("Binning").value = 'OFF'
                self.camprops.get_node("AutoFrameRate").value = 'OFF'
            except genicam.genapi.LogicalErrorException:
                try:
                    self.camprops.get_node("GainAuto").value = "Off"
                    self.camprops.get_node("ExposureAuto").value = "Off"
                    self.camprops.get_node("BalanceWhiteAuto").value = "Off"
                    self.camprops.get_node("AcquisitionFrameRateEnable").value = True
                    self.setProperty("FPS", self.getProperty("MaxFPS"))
                except genicam.genapi.LogicalErrorException:
                    pass

    # Method for opening the error log
    def openerrlog(self):
        if not os.path.exists(os.path.join(os.getcwd(), 'logs')):
            os.mkdir('logs')
        string = datetime.datetime.now().strftime("%Y-%m-%d_%H;%M;%S")
        if os.path.exists("logs/CamHandlerERRORLog_%s.txt" % string):
            string = string + "p2"
        self.logfname = "logs/CamHandlerERRORLog_%s.txt" % string
        self.errlog = open(self.logfname, 'w')

    def closeerrlog(self):
        self.errlog.close()
        if os.path.getsize(self.logfname) == 0:
            os.remove(self.logfname)

    # Method for logging errors with the specified message
    # Input: message, string containing the desired error message
    def logerror(self, message):
        tstamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        self.errlog.write("{0} ERROR: ".format(tstamp) + message + '\n')

    # Method for changing active device
    # Input: ind, index of the desired device in harvester.device_info_list
    def changeCam(self, ind):
        if self.cam is not None:  # If another device is in use disconnect it before activating new device
            self.acquire = False  # Verify that acquisition is stopped before disconnecting
            while self.cam.is_acquiring():
                time.sleep(0.01)

            self.saveCameraProperties()  # Save configured device properties to device memory
            self.cam.destroy()  # Destroy the link to the old device
            self.cam = None  # Set the current device variable to None to indicate no device is active
            self.camprops = None  # Reset device property helper variable
        if 0 <= ind < len(self.harvester.device_info_list):
            try:
                self.cam = self.harvester.create_image_acquirer(ind)
                self.camprops = self.cam.remote_device.node_map
                self.loadCameraProperties()
                self.initCamera()
                self.cam.num_buffers = self.bufnum
                self.defH = self.getProperty("Height")
                self.defW = self.getProperty("Width")
                self.defOffX = self.getProperty("OffsetX")
                self.defOffY = self.getProperty("OffsetY")
                for test in ["Trigger", "TriggerMode"]:  # Some manufacturers use different naming
                    try:
                        for val in self.camprops.get_node(test).symbolics:
                            if val.upper() == "OFF":  # Some manufacturers use Off/On and some use OFF/ON
                                self.camprops.get_node(test).value = val
                        break
                    except genicam.genapi.LogicalErrorException:
                        pass
                self.color = False
                for pixform in self.camprops.PixelFormat.symbolics:
                    if pixform in colorforms:
                        self.color = True
            except genicam.gentl.AccessDeniedException:
                self.cam = None
                self.camprops = None

    # Method for acquiring a single frame
    # return: arr, numpy array containing the pixel values of the acquired image
    # return: syststamp, system timestamp for the acquired image (calculated from the timestamp given by the device)
    def acquireImag(self):
        if self.cam.is_acquiring():
            try:
                buffer = self.cam.fetch_buffer(timeout=0.1)
                if len(buffer.payload.components) > 0:
                    buffimag = buffer.payload.components[0]
                    tstamp = buffer.timestamp
                    if not self.sync:
                        self.synctimestamp(tstamp)
                    syststamp = self.getsystimestamp(tstamp)
                    arr = numpy.ndarray.copy(buffimag.data.reshape(buffimag.height, buffimag.width))
                    if self.camprops.PixelFormat.value == colorforms[0]:  # Is Bayer RG8
                        arr = cv.cvtColor(arr, cv.COLOR_BayerRGGB2RGB)
                    buffer.queue()
                    return arr, syststamp
            except genicam.gentl.TimeoutException:
                pass
        return None, 0

    # Method for getting the value of the desired property
    # input: prop, string containing the name of the property
    # return: value of the property
    def getProperty(self, prop):
        ret = None
        if self.camprops is not None:
            if prop == "Width":
                ret = self.camprops.get_node("Width").value
            elif prop == "Height":
                ret = self.camprops.get_node("Height").value
            elif prop == "MaxWidth":
                ret = self.camprops.get_node("Width").max
            elif prop == "MaxHeight":
                ret = self.camprops.get_node("Height").max
            elif prop == "MinWidth":
                ret = self.camprops.get_node("Width").min
            elif prop == "MinHeight":
                ret = self.camprops.get_node("Height").min
            elif prop == "OffsetX":
                ret = self.camprops.get_node("OffsetX").value
            elif prop == "OffsetY":
                ret = self.camprops.get_node("OffsetY").value
            elif prop == "PixelFormat":
                ret = self.camprops.get_node("PixelFormat").value
            elif prop == "FPS":
                for test in ["FrameRate", "ResultingFrameRateAbs"]:
                    try:
                        ret = self.camprops.get_node(test).value
                        break
                    except genicam.genapi.LogicalErrorException:
                        pass
            elif prop == "MaxFPS":
                for test in ["FrameRate", "ResultingFrameRateAbs"]:
                    try:
                        if test == "ResultingFrameRateAbs":
                            self.camprops.get_node("AcquisitionFrameRateEnable").value = False
                            ret = self.camprops.get_node(test).value
                            self.camprops.get_node("AcquisitionFrameRateEnable").value = True
                        else:
                            ret = self.camprops.get_node(test).max

                        break
                    except genicam.genapi.LogicalErrorException:
                        pass
            elif prop == "MinFPS":
                for test in ["FrameRate", "AcquisitionFrameRateAbs"]:
                    try:
                        ret = self.camprops.get_node(test).min
                        break
                    except genicam.genapi.LogicalErrorException:
                        pass
            elif prop == "PacketInterval":
                for test in ["InterPacketDelay", "GevSCPD"]:
                    try:
                        ret = self.camprops.get_node(test).value
                    except genicam.genapi.LogicalErrorException:
                        pass
            elif prop == "MinPacketInterval":
                for test in ["InterPacketDelay", "GevSCPD"]:
                    try:
                        ret = self.camprops.get_node(test).min
                    except genicam.genapi.LogicalErrorException:
                        pass
            elif prop == "MaxPacketInterval":
                for test in ["InterPacketDelay", "GevSCPD"]:
                    try:
                        ret = self.camprops.get_node(test).max
                    except genicam.genapi.LogicalErrorException:
                        pass
            elif prop == "FrameDelay":
                try:
                    ret = self.camprops.get_node("GevSCFTD").value
                except genicam.genapi.LogicalErrorException:
                    pass
            elif prop == "MinFrameDelay":
                try:
                    ret = self.camprops.get_node("GevSCFTD").min
                except genicam.genapi.LogicalErrorException:
                    pass
            elif prop == "MaxFrameDelay":
                try:
                    ret = self.camprops.get_node("GevSCFTD").max
                except genicam.genapi.LogicalErrorException:
                    pass
            elif prop == "PacketSize":
                try:
                    val = pcktsizes[0]
                    try:
                        val = self.camprops.get_node("PacketSize").value
                        val = int(val[4:])
                    except genicam.genapi.PropertyException:
                        pass
                    for i in range(len(pcktsizes)):
                        if val == pcktsizes[i]:
                            ret = i
                except genicam.genapi.LogicalErrorException:
                    try:
                        val = self.camprops.get_node("GevSCPSPacketSize").value
                        for i in range(len(pcktsizes)):
                            if val == pcktsizes[i]:
                                ret = i
                        if ret is None:
                            self.camprops.get_node("GevSCPSPacketSize").value = pcktsizes[0]
                            ret = 0
                    except genicam.genapi.LogicalErrorException:
                        pass
            elif prop == "Gain":
                gainsc = [0.0358, 0.1]
                ind = 0
                for test in ["Gain_L", "GainRaw"]:
                    try:
                        ret = self.camprops.get_node(test).value*gainsc[ind]
                        break
                    except genicam.genapi.LogicalErrorException:
                        ind = ind + 1
            elif prop == "MaxGain":
                gainsc = [0.0358, 0.1]
                ind = 0
                for test in ["Gain_L", "GainRaw"]:
                    try:
                        ret = self.camprops.get_node(test).max*gainsc[ind]
                        break
                    except genicam.genapi.LogicalErrorException:
                        ind = ind + 1
            elif prop == "ExposureTime":
                for test in ["Shutter", "ExposureTimeAbs"]:
                    try:
                        ret = self.camprops.get_node(test).value
                        break
                    except genicam.genapi.LogicalErrorException:
                        pass
            elif prop == "MinExposureTime":
                for test in ["Shutter", "ExposureTimeAbs"]:
                    try:
                        ret = self.camprops.get_node(test).min
                        break
                    except genicam.genapi.LogicalErrorException:
                        pass
            elif prop == "MaxExposureTime":
                for test in ["Shutter", "ExposureTimeAbs"]:
                    try:
                        ret = self.camprops.get_node(test).max
                        break
                    except genicam.genapi.LogicalErrorException:
                        pass
        return ret

    # Method for setting the value of the desired device property
    # input: prop, String containing the name of the property
    # input: val, Desired value for the property. Type depends on the property
    def setProperty(self, prop, val=None):
        if self.camprops is not None:
            if prop == "Width":
                self.camprops.get_node("Width").value = val
            elif prop == "Height":
                self.camprops.get_node("Height").value = val
            elif prop == "PixelFormat":
                self.camprops.get_node("PixelFormat").value = val
            elif prop == "OffsetX":
                self.camprops.get_node("OffsetX").value = val
            elif prop == "OffsetY":
                self.camprops.get_node("OffsetY").value = val
            elif prop == "PacketSize":
                try:
                    self.camprops.get_node("PacketSize").value = "Size"+str(pcktsizes[val])
                except genicam.genapi.LogicalErrorException:
                    try:
                        self.camprops.get_node("GevSCPSPacketSize").value = pcktsizes[val]
                    except genicam.genapi.LogicalErrorException:
                        pass
            elif prop == "PacketInterval":
                for test in ["InterPacketDelay", "GevSCPD"]:
                    try:
                        self.camprops.get_node(test).value = val
                    except genicam.genapi.LogicalErrorException:
                        pass
            elif prop == "FrameDelay":
                try:
                    self.camprops.get_node("GevSCFTD").value = val
                except genicam.genapi.LogicalErrorException:
                    pass
            elif prop == "Gain":
                gainsc = [0.0358, 0.1]
                ind = 0
                for test in ["Gain_L", "GainRaw"]:
                    try:
                        self.camprops.get_node(test).value = int(val/gainsc[ind])
                        break
                    except genicam.genapi.LogicalErrorException:
                        ind = ind + 1

            elif prop == "ExposureTime":
                for test in ["Shutter", "ExposureTimeAbs"]:
                    try:
                        self.camprops.get_node(test).value = val
                        break
                    except genicam.genapi.LogicalErrorException:
                        pass
            elif prop == "FPS":
                for test in ["FrameRate", "AcquisitionFrameRateAbs"]:
                    try:
                        self.camprops.get_node(test).value = val
                        break
                    except genicam.genapi.LogicalErrorException:
                        pass

    # Method for toggling the FPS limiter
    def toggleFPSLimit(self):
        if self.cam is not None:
            if self.limit:
                self.setProperty("FPS", self.getProperty("MaxFPS"))
                self.limit = False
            else:
                self.setProperty("FPS", self.fpslimit)
                self.limit = True

    # Method for toggling partial scanning
    def togglePartial(self):
        if self.partial:
            self.setProperty("OffsetX", self.defOffX)
            self.setProperty("OffsetY", self.defOffY)
            self.setProperty("Width", self.defW)
            self.setProperty("Height", self.defH)
            self.partial = False
        else:
            self.setProperty("Width", self.partw)
            self.setProperty("Height", self.parth)
            self.setProperty("OffsetX", self.offsetx)
            self.setProperty("OffsetY", self.offsety)
            self.partial = True

    # Method for toggling triggering
    def toggleTrigger(self):
        if self.cam is not None:
            if self.triggering:
                self.triggering = False
                for test in ["Trigger", "TriggerMode"]:  # Some manufacturers use different naming
                    try:
                        for val in self.camprops.get_node(test).symbolics:
                            if val.upper() == "OFF":  # Some manufacturers use Off/On and some use OFF/ON
                                self.camprops.get_node(test).value = val
                        break
                    except genicam.genapi.LogicalErrorException:
                        pass
            else:
                self.triggering = True
                for test in ["Trigger", "TriggerMode"]:  # Some manufacturers use different naming
                    try:
                        for val in self.camprops.get_node(test).symbolics:
                            if val.upper() == "ON":  # Some manufacturers use Off/On and some use OFF/ON
                                self.camprops.get_node(test).value = val
                        break
                    except genicam.genapi.LogicalErrorException:
                        pass

    # Method to change the number of buffers that can be used
    def changeBufnum(self, val):
        if self.cam is not None:
            self.bufnum = val
            self.cam.num_buffers = self.bufnum

    # Method for rotating images
    # input: frame, image to be rotated
    # return: frame, rotated image
    def rotateImag(self, frame):
        if self.rotation == 90:
            frame = cv.rotate(frame, cv.cv.ROTATE_90_CLOCKWISE)
        elif self.rotation == 180:
            frame = cv.rotate(frame, cv.cv.ROTATE_180)
        else:
            frame = cv.rotate(frame, cv.cv.ROTATE_90_COUNTERCLOCKWISE)
        return frame
    # Method for filtering the image (threshold)
    # input: frame, image frame to be filtered
    # return: frame, filtered image frame (if filtering is toggled off returns the input)
    def filtImag(self, frame):
        if self.filtering:
            frame = cv.threshold(frame, self.thrsh, 255, cv.THRESH_TOZERO)[1]  # Threshold the image
        if self.rotate:
            frame = self.rotateImag(frame)
        return frame

    # Method for saving a image
    # input: frame, image frame to be saved
    # input: timestamp, timestamp of the image frame
    def saveImag(self, frame, timestamp):
        if self.saving:
            if self.savepth is None:
                cv.imwrite(timestamp + '.jpg', frame)
            else:
                fname = "{0}{1}.jpg".format(self.savepth, timestamp)
                cv.imwrite(fname, frame)

    # Method for changing the image storage directory
    # input: dirname, absolute path to the directory
    # return: boolean, was the change successful?
    def changeSaveDir(self, dirname):
        if os.path.isdir(dirname):
            self.savepth = dirname + '\\'
            return True
        else:
            return False

    # Method for syncing the system timestamp with the device timestamp
    # input: tstamp0, the device timestamp of the first acquired frame
    def synctimestamp(self, tstamp0):
        self.systime0 = datetime.datetime.now()
        self.tstamp0 = tstamp0
        self.sync = True

    # Method for acquiring a system timestamp based on current synchronization and the device timestamp
    # input: tstamp, device timestamp used for conversion
    # return: syststamp, system timestamp
    def getsystimestamp(self, tstamp):
        hour = self.systime0.hour
        min = self.systime0.minute
        sec = self.systime0.second
        deltans = tstamp - self.tstamp0
        deltams = round(deltans / 1000000)
        ms = round(self.systime0.microsecond / 1000) + deltams
        if ms >= 1000:
            sec = sec + math.floor(ms / 1000)
            ms = ms - math.floor(ms / 1000) * 1000
            if sec >= 60:
                min = min + math.floor(sec / 60)
                sec = sec - math.floor(sec / 60) * 60
                if min >= 60:
                    hour = hour + math.floor(min / 60)
                    min = min - math.floor(min / 60) * 60
        syststamp = self.systime0.strftime("%Y-%m-%d ") + "{0};{1};{2},{3}".format(hour, min, sec, ms)
        return syststamp
