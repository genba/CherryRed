ANALOG_TYPE = "analogIn"
DIGITAL_OUT_TYPE = "digitalOut"
DIGITAL_IN_TYPE = "digitalIn"

class FIO(object):
    """
    The FIO Class represents a single input. Helps keep track of state.
    """
    def __init__(self, fioNumber, label = None , chType = "analogIn", state = None):
        self.fioNumber = fioNumber
        self.chType = chType
        self.label = None
        self.negChannel = False
        self.gainIndex = 0
        self.resolutionIndex = 1
        self.settleingFactor = 0
        
        if state is not None:
            self.state = int(state)
        else:
            self.state = None
        
        if self.chType == ANALOG_TYPE:
            self.negChannel = 31
            self.label = "AIN%s" % self.fioNumber
        else:
            self.label = "FIO%s" % self.fioNumber
            
        if label != None:
            self.label = label
    
    def asDict(self):
        """ Returns a dictionary representation of a FIO
        """
        return { "fioNumber" : self.fioNumber, "chType" : self.chType, "label" : self.label, "negChannel" : self.negChannel, "state": self.state, 'gainIndex' : self.gainIndex, 'resolutionIndex' : self.resolutionIndex, 'settleingFactor' : self.settleingFactor }
        
    def transform(self, dev, inputConnection):
        """ Converts a FIO to match a given FIO
        """
        if inputConnection.chType == ANALOG_TYPE:
            self.negChannel = inputConnection.negChannel
            self.gainIndex = 0
            self.resolutionIndex = 1
            self.settleingFactor = 0
            self.setSelfToAnalog(dev)
        elif inputConnection.chType == DIGITAL_OUT_TYPE:
            self.state = inputConnection.state
            self.setSelfToDigital(dev, DIGITAL_OUT_TYPE) 
        else:
            self.setSelfToDigital(dev, DIGITAL_IN_TYPE)
    
    
    def setSelfToDigital(self, dev, chType):
        # FIO or EIO
        if self.fioNumber < 16:
            if self.fioNumber < 8:
                reg = 50590
                self.label = "FIO%s" % self.fioNumber
            else:
                reg = 50591
                self.label = "EIO%s" % ( self.fioNumber % 8 )
            
            analog = dev.readRegister(reg)  
            
            digitalMask = 0xffff - ( 1 << (self.fioNumber % 8) )
            
            analog = analog & digitalMask
            
            # Set pin to digital.
            dev.writeRegister(reg, analog)
        else:
            self.label = "CIO%s" % ( self.fioNumber % 16 )
        
        if chType == DIGITAL_OUT_TYPE:
            dev.writeRegister(6100 + self.fioNumber, 1)
            dev.writeRegister(6000 + self.fioNumber, self.state)
        else:
            dev.writeRegister(6100 + self.fioNumber, 0)
        
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
        state = dev.readRegister(self.fioNumber*2)
        if self.negChannel == 32:
            state += 2.4
        
        return self.parseAinResults(state)
        
    def parseAinResults(self, state):
        infoDict = dict()
        infoDict['connection'] = self.label
        infoDict['state'] = "%0.5f" % state
        infoDict['value'] = "%0.5f" % state # Use state for 'state' and 'value'
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
        infoDict['chType'] = (DIGITAL_IN_TYPE if fioDir == 0 else DIGITAL_OUT_TYPE)
        
        return infoDict