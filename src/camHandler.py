import math

import cv2 as cv
from harvesters.core import Harvester
import genicam.gentl
import time
import datetime
import numpy
import os
from filterConfig import FilterConfig


class CamHandler:
    def __init__(self):
        self.cam = None
        self.locator = None
        self.savepth = None
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
        self.filtcfg = FilterConfig()
        self.filtcfg.load()
        self.load()

    def load(self):
        try:
            file = open('handler.cfgh', 'r')
            self.savepth = file.readline()
            if self.savepth == 'None':
                self.savepth = None
            file.close()
        except FileNotFoundError:
            pass

    def save(self):
        file = open('handler.cfgh', 'w')
        file.write('{0}'.format(self.savepth))
        file.close()

    def changeCam(self, ind):
        if self.cam is not None:
            self.cam.stop_acquisition()
            self.cam.destroy()
            self.cam = None
        if 0 <= ind < len(self.harvester.device_info_list):
            try:
                self.cam = self.harvester.create_image_acquirer(ind)
                self.cam.num_buffers = 6
                self.cam.remote_device.node_map.PacketSize.value = 'Size2960'
                format = self.cam.remote_device.node_map.PixelFormat.value
                if format == "RGB8":
                    self.color = True
                else:
                    self.color = False
            except genicam.gentl.AccessDeniedException:
                self.cam = None

    def acquireImag(self):
        if self.cam.is_acquiring():
            try:
                buffer = self.cam.fetch_buffer(timeout=0.1)
                buffimag = buffer.payload.components[0]
                tstamp = buffer.timestamp
                if not self.sync:
                    self.synctimestamp(tstamp)
                syststamp = self.getsystimestamp(tstamp)
                arr = numpy.ndarray.copy(buffimag.data.reshape(buffimag.height, buffimag.width))
                buffer.queue()
                return arr, syststamp
            except genicam.gentl.TimeoutException:
                pass
        return None, 0


    def toggleTrigger(self):
        if self.triggering:
            self.triggering = False
            self.cam.remote_device.node_map.Trigger.value = 'OFF'
        else:
            self.triggering = True
            self.cam.remote_device.node_map.Trigger.value = 'ON'


    def getChannel(self, img, channum):
        r, b, g = cv.split(img)
        if channum == 1:
            return r
        elif channum == 2:
            return b
        elif channum == 3:
            return g
        else:
            return img

    def filtImag(self, frame, channel):
        if self.color:
            if 0 < channel < 4:
                frame = self.getChannel(frame, channel)
            else:
                return self.filtRGB(frame)
        filterc = self.filtcfg
        start = time.time()
        if self.filtering:
            if filterc.filt == 1:
                frame = cv.blur(frame, (filterc.filtw, filterc.filth))
            elif filterc.filt == 2:
                frame = cv.GaussianBlur(frame, (filterc.filtw, filterc.filth), 0)
            elif filterc.filt == 3:
                frame = cv.medianBlur(frame, filterc.filtw)
            frame = cv.convertScaleAbs(frame, alpha=filterc.alpha,
                                       beta=filterc.beta)  # Change contrast with linear multiplication
        bw = cv.threshold(frame, filterc.binthr, 255, cv.THRESH_TOZERO)[1]  # Binarize the image
        stop = time.time()
        # print('Time elapsed for drawImag: {0:1.4f}'.format(stop-start))
        return frame, bw

    def filtRGB(self, frame):
        r = self.filtImag(frame, 1)
        g = self.filtImag(frame, 2)
        b = self.filtImag(frame, 3)
        return cv.merge([r, g, b])

    def saveImag(self, bw, timestamp):
        if self.saving:
            bw = self.savesize(bw, bw.shape[0])
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

    def savesize(self, src, height):
        return cv.resize(src, (round((4 / 3) * height), height))

    def previewsize(self, src, width, height):
        return cv.resize(src, (width, height))

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
