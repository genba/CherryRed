import u6, u3, ue9

ANALOG_TYPE = "analogIn"
DIGITAL_OUT_TYPE = "digitalOut"
DIGITAL_IN_TYPE = "digitalIn"

class UE9FIO(object):
    """
    A class to hold help functions for dealing with UE9 inputs/outputs.
    """
    @staticmethod
    def getBipGain(dev, inputNumber):
        ainNumber = inputNumber
        ainNumber = ainNumber - (ainNumber % 2)
        
        attrName = "AIN%s_%s_BipGain" % (ainNumber + 1, ainNumber)
        print "Computed name =", attrName
        currentGain = dev.__getattribute__(attrName)
        
        inputsGain = (currentGain >> (4 * (ainNumber % 2))) & 0xf
        
        return currentGain, attrName, inputsGain
    
    @staticmethod
    def setupNewDevice(dev):
        # Add feedback options to UE9 object
        dev.AIN14ChannelNumber = 0
        dev.AIN15ChannelNumber = 0
        dev.Resolution = 0
        dev.SettlingTime = 0
        dev.AIN1_0_BipGain = 0
        dev.AIN3_2_BipGain = 0
        dev.AIN5_4_BipGain  = 0
        dev.AIN7_6_BipGain = 0
        dev.AIN9_8_BipGain = 0
        dev.AIN11_10_BipGain = 0
        dev.AIN13_12_BipGain = 0
        
    @staticmethod
    def updateFIO(dev, inputConnection):
        if inputConnection.fioNumber < 14:
            print "Got an update for an AIN"
            dev.Resolution = inputConnection.resolutionIndex
            dev.SettlingTime = inputConnection.settlingFactor
            
            currentGain, atterName, inputsGain = UE9FIO.getBipGain(dev, inputConnection.fioNumber)
            
            if inputConnection.fioNumber % 2 == 1:
                # Replacing the higher nibble
                otherGain = currentGain & 0xf
                newGain = ((inputConnection.gainIndex & 0xf) << 4) + otherGain
            else:
                otherGain = (currentGain >> 4) & 0xf
                newGain = (otherGain << 4) + (inputConnection.gainIndex & 0xf)
                
            dev.__setattr__(attrName, newGain)
        else:
            fioNumber = inputConnection.fioNumber - 14
            direction = 0 if inputConnection.chType == DIGITAL_IN_TYPE else 1
            dev.singleIO(1, fioNumber, Dir = direction, State = inputConnection.state )
    
    @staticmethod
    def getFioInfo(dev, inputNumber):
        if inputNumber < 14:
            currentGain, atterName, inputsGain = UE9FIO.getBipGain(dev, inputNumber)
            return { "label" : "AIN%s" % inputNumber, "connectionNumber" : inputNumber, "chType" : "ANALOG_TYPE", "settlingFactor" : dev.SettlingTime, "resolutionIndex" : dev.Resolution, "gainIndex" : inputsGain}
        else:
            fioNumber = inputNumber - 14
            direction = dev.readRegister(6100 + fioNumber)
            direction = DIGITAL_IN_TYPE if direction == 0 else DIGITAL_OUT_TYPE
            state = dev.readRegister(6000 + fioNumber)
            return { "label" : "FIO%s" % fioNumber, "connectionNumber" : inputNumber, "chType" : direction, "state": state }
    
    
class FIO(object):
    """
    The FIO Class represents a single input. Helps keep track of state.
    """
    def __init__(self, fioNumber, label = None , chType = "analogIn", state = None, negChannel = None):
        self.fioNumber = fioNumber
        self.chType = chType
        self.label = None
        if negChannel:
            self.negChannel = int(negChannel)
        else:
            self.negChannel = False
        self.gainIndex = 0
        self.resolutionIndex = 1
        self.settlingFactor = 0
        
        if state is not None:
            self.state = int(state)
        else:
            self.state = None
        
        if self.chType == ANALOG_TYPE:
            if not self.negChannel:
                self.negChannel = 31
            self.label = "AIN%s" % self.fioNumber
        else:
            self.label = "FIO%s" % self.fioNumber
            
        if label != None:
            self.label = label
    
    def asDict(self):
        """ Returns a dictionary representation of a FIO
        """
        return { "fioNumber" : self.fioNumber, "chType" : self.chType, "label" : self.label, "negChannel" : self.negChannel, "state": self.state, 'gainIndex' : self.gainIndex, 'resolutionIndex' : self.resolutionIndex, 'settlingFactor' : self.settlingFactor }
        
    def makeFeedbackCommand(self, dev):
        if self.chType == ANALOG_TYPE:
            if dev.devType == 3:
                nc = self.negChannel
                if nc == 32:
                    nc = 30
                return u3.AIN(self.fioNumber, NegativeChannel = nc, LongSettling = self.gainIndex, QuickSample = self.settlingFactor)
            elif dev.devType == 6:
                diff = False
                if self.negChannel != 31:
                    diff = True 
                
                return u6.AIN24(self.fioNumber, ResolutionIndex = self.resolutionIndex, GainIndex = self.gainIndex, Differential = diff)
        else:
            if dev.devType == 3:
                return u3.BitStateRead(self.fioNumber)
            elif dev.devType == 6:
                return u6.BitStateRead(self.fioNumber)
        
    def transform(self, dev, inputConnection):
        """ Converts a FIO to match a given FIO
        """
        if inputConnection.chType == ANALOG_TYPE:
            self.negChannel = inputConnection.negChannel
            self.gainIndex = inputConnection.gainIndex
            self.resolutionIndex = inputConnection.resolutionIndex
            self.settlingFactor = inputConnection.settlingFactor
            self.setSelfToAnalog(dev)
        elif inputConnection.chType == DIGITAL_OUT_TYPE:
            self.state = inputConnection.state
            self.setSelfToDigital(dev, DIGITAL_OUT_TYPE) 
        else:
            self.setSelfToDigital(dev, DIGITAL_IN_TYPE)
    
    
    def setSelfToDigital(self, dev, chType):
        if dev.devType == 6:
            fioNumber = self.fioNumber - 14
        else:
            fioNumber = self.fioNumber
        
        # FIO or EIO
        if fioNumber < 16:
            if fioNumber < 8:
                reg = 50590
                self.label = "FIO%s" % fioNumber
            else:
                reg = 50591
                self.label = "EIO%s" % ( fioNumber % 8 )
            
            analog = dev.readRegister(reg)  
            
            digitalMask = 0xffff - ( 1 << (fioNumber % 8) )
            
            analog = analog & digitalMask
            
            # Set pin to digital.
            dev.writeRegister(reg, analog)
        else:
            self.label = "CIO%s" % ( fioNumber % 16 )
        
        if chType == DIGITAL_OUT_TYPE:
            dev.writeRegister(6100 + fioNumber, 1)
            dev.writeRegister(6000 + fioNumber, self.state)
        else:
            dev.writeRegister(6100 + fioNumber, 0)
        
        print "Setting self to be %s" % chType
        self.chType = chType
    
    def setSelfToAnalog(self, dev):
        # FIO or EIO
        if self.fioNumber < 8:
            reg = 50590
        else:
            reg = 50591
            
        analog = dev.readRegister(reg)
            
        analog |= (1 << (self.fioNumber % 8))
        
        # Set pin to Analog.
        dev.writeRegister(reg, analog)
        
        # Set Negative channel.
        if self.negChannel == 32:
            dev.writeRegister(3000 + self.fioNumber, 30)
        else:
            dev.writeRegister(3000 + self.fioNumber, self.negChannel)
        
        self.chType = ANALOG_TYPE
        self.label = "AIN%s" % ( self.fioNumber )
    
    def readResult(self, dev):
        if self.chType == ANALOG_TYPE:
            return self.readAin(dev)
        else:
            return self.readFio(dev)

    def readAin(self, dev):
        state = dev.getAIN(self.fioNumber, negChannel = self.negChannel)
        
        return self.parseAinResults(state)
        
    def parseAinResults(self, state):
        infoDict = dict()
        infoDict['connection'] = self.label
        infoDict['connectionNumber'] = self.fioNumber
        # Should use FLOAT_FORMAT
        infoDict['state'] = "%0.3f" % state
        infoDict['value'] = "%0.3f" % state # Use state for 'state' and 'value'
        infoDict['chType'] = self.chType
        
        return infoDict

    def readFio(self, dev):
        fioDir = dev.readRegister(6100 + self.fioNumber)
        fioState = dev.readRegister(6000 + self.fioNumber)
        
        return self.parseFioResults(fioDir, fioState)
        
    def parseFioResults(self, fioDir, fioState):
        if fioDir == 0:
            fioDirText = "Input"
        else:
            fioDirText = "Output"
            
        if fioState == 0:
            fioStateText = "Low"
        else:
            fioStateText = "High"
        
        infoDict = {'connection' : self.label, 'state' : "%s %s" % (fioDirText, fioStateText), 'value' : "%s" % fioState}
        infoDict['connectionNumber'] = self.fioNumber
        infoDict['chType'] = (DIGITAL_IN_TYPE if fioDir == 0 else DIGITAL_OUT_TYPE)
        
        return infoDict
