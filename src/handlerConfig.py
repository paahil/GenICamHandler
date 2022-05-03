import os.path

booldict = {True: 1, False: 0}
pdict = {True: 'On', False: 'Off'}


class HandlerConfig:

    def __init__(self):
        self.savepth = None
        self.view = False
        self.saving = False
        self.objdet = False
        self.filtering = False

    def loadSavePath(self):
        file = open('handler.cfgh', 'r')
        self.savepth = file.readline()[:-1]
        file.close()

    def load(self):
        try:
            file = open('handler.cfgh', 'r')
            self.savepth = file.readline()[:-1]
            print(self.savepth)
            self.view = bool(int(file.readline()))
            print(self.view)
            self.saving = bool(int(file.readline()))
            self.objdet = bool(int(file.readline()))
            self.filtering = bool(int(file.readline()))
            file.close()
        except FileNotFoundError:
            pass

    def save(self):

        file = open('handler.cfgh', 'w')
        file.write('{0}\n'.format(self.savepth))
        file.write('{0:d}\n'.format(booldict[self.view]))
        file.write('{0:d}\n'.format(booldict[self.saving]))
        file.write('{0:d}\n'.format(booldict[self.objdet]))
        file.write('{0:d}\n'.format(booldict[self.filtering]))
        file.close()

    def changePath(self):
        ans = input('Input full path to desired save directory\n')
        if os.path.isdir(ans):
            self.savepth = ans + '\\'
        else:
            print('Directory not found')

    def changeConfig(self):
        cont = True
        while cont:
            self.printInfo()
            print('{0:30}  {1:30} {2:30}'.format('1:Change save directory', '2:Toggle preview', '3:Toggle saving'))
            print('{0:30}  {1:30} {2:30}'.format('4:Toggle object detection', '5:Toggle filtering',
                                                 '0:Exit configuration'))
            ans = input('')
            if ans == '1':
                self.changePath()
            elif ans == '2':
                if self.view:
                    self.view = False
                else:
                    self.view = True
            elif ans == '3':
                if self.saving:
                    self.saving = False
                else:
                    self.saving = True
            elif ans == '4':
                if self.objdet:
                    self.objdet = False
                else:
                    self.objdet = True
            elif ans == '5':
                if self.filtering:
                    self.filtering = False
                else:
                    self.filtering = True
            elif ans == '0':
                cont = False
            else:
                print('Invalid input')

    def printInfo(self):
        if self.savepth is None:
            print('{0:90}'.format('Image storing location: Unassigned'))
        else:
            print('{0:90}'.format('Image storing location: ' + self.savepth))
        print('{0:30}  {1:30}  {2:30}'
              .format('Preview: ' + pdict[self.view], 'Storing: ' + pdict[self.saving],
                      'Object detection ' + pdict[self.objdet]))
        print('{0:30}  {1:30}  {2:30}'.format('FIiltering: ' + pdict[self.filtering], '', ''))
        print('{0:90}'.format(90 * '-'))
