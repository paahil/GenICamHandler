filtdict = {0: "None", 1: "Box", 2: "Gaussian", 3: "Median"}


class FilterConfig:

    def __init__(self):
        self.binthr = 128
        self.alpha = 1
        self.beta = 0
        self.filt = 0
        self.filtw = 1
        self.filth = 1

    def load(self):
        try:
            file = open('default.cfgf', 'r')
            self.binthr = int(file.readline())
            self.alpha = float(file.readline())
            self.beta = float(file.readline())
            self.filt = int(file.readline())
            self.filtw = int(file.readline())
            self.filth = int(file.readline())
            file.close()
        except FileNotFoundError:
            file = open('default.cfgf', 'w')
            file.write('{0}\n'.format(self.binthr))
            file.write('{0}\n'.format(self.alpha))
            file.write('{0}\n'.format(self.beta))
            file.write('{0}\n'.format(self.filt))
            file.write('{0}\n'.format(self.filtw))
            file.write('{0}\n'.format(self.filth))
            file.close()

    def save(self):
        file = open('default.cfgf', 'w')
        file.write('{0}\n'.format(self.binthr))
        file.write('{0}\n'.format(self.alpha))
        file.write('{0}\n'.format(self.beta))
        file.write('{0}\n'.format(self.filt))
        file.write('{0}\n'.format(self.filtw))
        file.write('{0}\n'.format(self.filth))
        file.close()
