import math
import cv2 as cv
from harvesters.core import Harvester
import genicam.gentl
import genicam.genapi
import time
import datetime
import numpy
import os

colorforms = ["BayerRG8"]
pcktsizes = [1440, 2960, 4480, 6000, 7520, 9040, 10560]

class CamHandler:
    def __init__(self):
        self.errlog = None
        self.logfname = None
        self.cam = None
        self.camprops = None
        self.savepth = None
        self.thrsh = 0
        self.bufnum = 6
        self.partw = 256
        self.parth = 256
        self.offsetx = 900
        self.offsety = 900
        self.fpslimit = 1
        self.defH = 0
        self.defW = 0
        self.defOffX = 0
        self.defOffY = 0

        self.limit = False
        self.partial = False
        self.triggering = False
        self.acquire = False
        self.filtering = False
        self.color = False
        self.saving = False
        self.systime0 = None
        self.tstamp0 = 0
        self.sync = False

        self.harvester = Harvester()
        self.harvester.add_file("C:\\Users\\Paavo\\Documents\\ADENN2021\\MATRIX VISION\\bin\\x64\\mvGenTLProducer.cti")
        #self.load()
        self.openerrlog()

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

    def logerror(self, message):
        tstamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        self.errlog.write("{0} ERROR: ".format(tstamp) + message + '\n')

    def changeCam(self, ind):
        if self.cam is not None:
            self.acquire = False
            while self.cam.is_acquiring():
                time.sleep(0.01)
            self.saveCameraProperties()
            self.cam.destroy()
            self.cam = None
            self.camprops = None
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

    def toggleFPSLimit(self):
        if self.cam is not None:
            if self.limit:
                self.setProperty("FPS", self.getProperty("MaxFPS"))
                self.limit = False
            else:
                self.setProperty("FPS", self.fpslimit)
                self.limit = True

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

    def changeBufnum(self, val):
        if self.cam is not None:
            self.bufnum = val
            self.cam.num_buffers = self.bufnum

    def filtImag(self, frame):
        if self.filtering:
            frame = cv.threshold(frame, self.thrsh, 255, cv.THRESH_TOZERO)[1]  # Threshold the image
        return frame

    def saveImag(self, bw, timestamp):
        if self.saving:
            if self.savepth is None:
                cv.imwrite(timestamp + '.jpg', bw)
            else:
                fname = "{0}{1}.jpg".format(self.savepth, timestamp)
                cv.imwrite(fname, bw)

    def changeSaveDir(self, dirname):
        if os.path.isdir(dirname):
            self.savepth = dirname + '\\'
            return True
        else:
            return False

    def synctimestamp(self, tstamp0):
        self.systime0 = datetime.datetime.now()
        self.tstamp0 = tstamp0
        self.sync = True

    def getsystimestamp(self, tstamp):
        hour = self.systime0.hour
        min = self.systime0.minute
        sec = self.systime0.second
        deltaus = tstamp - self.tstamp0
        deltams = round(deltaus / 1000)
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
