# SkyMote Manager
from groundedutils import *
from skymotefirmwareupgrader import SkymoteFirmwareUpgraderThread
import threading
import LabJackPython, skymote

import csv, os
from datetime import datetime
from time import time as floattime

def moteAsDict(mote):
    returnDict = dict()
    
    returnDict['name'] = mote.nickname
    returnDict['firmware'] = mote.mainFWVersion
    returnDict['productName'] = mote.productName
    returnDict['devType'] = mote.devType
    returnDict['serial'] = mote.serialNumber
    returnDict['unitId'] = mote.unitId
    returnDict['checkinInverval'] = mote.checkinInterval

    return returnDict

def createFeedbackDict(channelName, value):
    connection = channelName
    state = FLOAT_FORMAT % value
    dictValue = FLOAT_FORMAT % value
    chType = ANALOG_TYPE

    if channelName == "Temperature":
        dictValue = kelvinToFahrenheit(float(value) + 273.15)
        state = (FLOAT_FORMAT % dictValue) + " &deg;F"
    elif channelName == "Vbatt":
        state = (FLOAT_FORMAT % value) + " V"
        chType += " vbatt"
    elif channelName == "Bump":
        chType = DIGITAL_IN_TYPE
        if value:
            state = "Bumped"
        else:
            state = "Still"
    elif channelName.endswith("Link Quality"):
        state = str(int(value))
        dictValue = str(int(value))
        chType += " lqi"

    return {'connection' : connection, 'state' : state, 'value' : dictValue, 'chType' : chType}

class SkyMoteManager(object):
    def __init__(self, address = LJSOCKET_ADDRESS, port = LJSOCKET_PORT):
        # The address and port to try to connect to LJSocket
        self.address = address
        self.port = port

        # Dictionary of all open bridges. Key = Serial, Value = Object.
        self.bridges = dict()
        
        # Logging Threads
        self.loggingThreads = dict()
        
        # Use Direct USB instead of LJSocket.
        self.usbOverride = False
        
    def shutdownThreads(self):
        """
        Called when cherrypy starts shutting down, shutdownThreads stops all the
        logging threads.
        """
        for s, thread in self.loggingThreads.items():
            thread.stop()
    
    def findBridges(self):
        print "self.bridges:", self.bridges
        devs = []
        ljsocketAddress = "localhost:6000"
        
        try:
            devs = LabJackPython.listAll(ljsocketAddress, 200)
        except:
            return {}
        
        #print "devsObj" = 
        
        #for dev in devsObj.values():
        #    devs.append({"serial" : dev["serialNumber"], "prodId" : dev["devType"]})
        
        for dev in devs:
            print "Got dev: serial = %s, prodId = 0x%X" % (dev['serial'], dev['prodId'])
            if dev['prodId'] != 0x501:
                continue
            elif str(dev['serial']) in self.bridges:
                d = self.bridges[str(dev['serial'])]
                if d.numMotes() != len(d.motes):
                    print "Found new motes"
                    d.motes = d.listMotes()
                    for mote in d.motes:
                        t = PlaceMoteInRapidModeThread(mote)
                        t.start()
                continue
            
            print "Got a bridge... opening."
            d = skymote.Bridge(LJSocket = ljsocketAddress, serial = dev['serial'])
            try:
                d.ethernetFirmwareVersion()
            except:
                d.ethernetFWVersion = "(No Ethernet)"
            d.nameCache = d.getName()
            d.usbFirmwareVersion()
            d.mainFirmwareVersion()
            d.productName = "SkyMote Bridge"
            d.meetsFirmwareRequirements = True
            d.spontaneousDataCache = dict()
            d.motes = d.listMotes()
            for mote in d.motes:
                t = PlaceMoteInRapidModeThread(mote)
                t.start()
            
            self.bridges["%s" % dev['serial']] = d
            
            t = SpontaneousDataLoggingThread(d)
            t.start()
            self.loggingThreads["%s" % dev['serial']] = t
        
        return self.bridges

    def scan(self):
        results = dict()
        
        for b in self.bridges.values():
            for mote in b.listMotes():
                results[str(mote.moteId)] = mote.sensorSweep()
                
        return results
    
    def getBridge(self, serial):
        if isinstance(serial, skymote.Bridge):
            return serial
        elif serial in self.bridges:
            return self.bridges[serial]
        else:
            return self.bridges[str(serial)]
    
    def getMote(self, b, moteId):
        moteId = int(moteId)
        m = None
        for mote in b.motes:
            if mote.unitId == unitId:
                m = mote
                break
        return m
    
    def scanBridge(self, serial):
        results = dict()
        
        b = self.getBridge(serial)
        
        numMotes = b.numMotes()
        
        if numMotes != len(b.motes):
            b.motes = b.listMotes()
            
            for mote in b.motes:
                t = PlaceMoteInRapidModeThread(mote)
                t.start()
        
        results['Number of Connected Motes'] = len(b.motes)
        
        motes = dict()
        
        for m in b.motes:
            moteDict = moteAsDict(m)
            moteDict['nickname'] = moteDict['name']
            data = b.spontaneousDataCache.get(str(m.unitId), {})
            if data:
                tableData = list()
                tableData.append(createFeedbackDict('Temperature',data['Temp']))
                tableData.append(createFeedbackDict('Light',data['Light']))
                tableData.append(createFeedbackDict('Bump',data['Bump']))
                tableData.append(createFeedbackDict('Tx Link Quality',data['TxLQI']))
                tableData.append(createFeedbackDict('Rx Link Quality',data['RxLQI']))
                tableData.append(createFeedbackDict('Vbatt',data['Battery']))

                moteDict['tableData'] = tableData
                moteDict['transId'] = data['transId']
            
            moteDict['inRapidMode'] = m.inRapidMode
            motes[str(m.unitId)] = moteDict
        
        results['Connected Motes'] = motes
        
        # Not implemented: results['Temperature'] = 
                
        return results

    def updateMoteSettings(self, serial, unitId, settings):
        # Update the settings on a mote.
        
        b = self.getBridge(serial)
        
        m = self.getMote(b, unitId)
        
        if m is None:
            return False
        
        if not m.inRapidMode:
            m.startRapidMode()
            m.inRapidMode = True
        
        print "settings =", settings
        
        if "name" in settings and settings['name'] != m.nickname:
            print "Updating name to %s from %s." % (settings['name'], m.nickname)
            m.name = settings['name']
            m.nickname = settings['name']
            
        if "unitId" in settings and settings['unitId'] != m.unitId:
            m.setUnitId(settings['unitId'])
        
        if "checkinInterval" in settings and settings['checkinInterval'] != m.checkinInterval:
            m.setCheckinInterval(settings['checkinInterval']*1000)
        
        return True
        
    def doFirmwareUpgrade(self, serial, unitId, fwFile):
        """
        Starts the thread that will upgrade the firmware of a Skymote device
        """
        
        b = self.getBridge(serial)
        
        if unitId != 0:
            # We are going to upgrade the motes
            b.upgradeThread = SkymoteFirmwareUpgraderThread(b, fwFile, upgradeMotes = True, recovery = False)
        else:
            # We are going to upgrade the bridge
            b.upgradeThread = SkymoteFirmwareUpgraderThread(b, fwFile, upgradeMotes = False, recovery = False)
        
        b.upgradeThread.start()
        
        return True

    def getFirmwareStatus(self, serial):
        b = self.getBridge(serial)
        
        try:
            t = b.upgradeThread
            if t.running:
                line = ""
                try:
                    while True:
                        line += (t.statusList.pop() + "\n")
                except:
                    pass
                
                return line
            else:
                b.statusList = None
                return "Firmware update finished."
        except AttributeError:
            return "Couldn't find a firmware upgrade thread."  
       

class PlaceMoteInRapidModeThread(threading.Thread):
    def __init__(self, mote):
        threading.Thread.__init__(self)
        self.daemon = True
        self.mote = mote
        self.mote.inRapidMode = False
        self.mote.lastCommunication = None

    def run(self):
        self.mote.nickname = "Placeholder SkyMote Name"
        self.mote.startRapidMode()
        self.mote.inRapidMode = True
        self.mote.nickname = self.mote.name
        self.mote.mainFirmwareVersion()
        self.mote.devType = self.mote.readRegister(65000)
        if self.mote.devType == 2000:
            self.mote.productName = "SkyMote TLB"
        else:
            self.mote.productName = "SkyMote Unknown Type"
        self.mote.readSerialNumber()
        self.mote.checkinInterval = self.mote.readCheckinInterval()/1000

class SpontaneousDataLoggingThread(threading.Thread):
    def __init__(self, bridge):
        threading.Thread.__init__(self)
        self.daemon = True
        self.bridge = bridge
        self.name = sanitize(self.bridge.nameCache)
        self.filename = "%%Y-%%m-%%d %%H__%%M__%%S %s %s.csv" % (self.name, "spontaneous")
        self.filename = datetime.now().strftime(self.filename)
        
        self.headers = [ "Timestamp", "Unit ID", "Temp", "Light", "Bump", "RxLQI", "TxLQI", "Battery"]
        
        self.filepath = "./logfiles/%s" % self.filename
        
        self.running = False
        
        try:
            self.stream = open(self.filepath, "wb", 1)
            self.csvWriter = csv.writer(self.stream)
        except IOError:
            os.mkdir("./logfiles")
            self.stream = open(self.filepath, "wb", 1)
            self.csvWriter = csv.writer(self.stream)
        
        self.csvWriter.writerow(self.headers)
        
    def stop(self):
        self.running = False
        
    def run(self):
        print "Spontaneous Data Logger for %s started." % (self.name)
        self.running = True
        
        while self.running:
            data = self.bridge.spontaneous().next()
            now = datetime.now()
            data['timevalue'] = floattime()
            
            m = None
            for mote in self.bridge.motes:
                if mote.unitId == data['unitId']:
                    m = mote
                    break
            
            if m is not None:
                hasLast = m.lastCommunication is not None
                if m.inRapidMode and hasLast and (data['timevalue'] - m.lastCommunication) > 1.5:
                    print "Communication has slowed. Mote %s is not in rapid mode anymore." % m.unitId
                    m.inRapidMode = False
                    
                m.lastCommunication = data['timevalue']
            
            data['timestamp'] = str(now)
            self.bridge.spontaneousDataCache[str(data['unitId'])] = data
            print "Logging spontaneous data from %s." % data['unitId']
            
            results = [ now, data['unitId'], data['Temp'], data['Light'], data['Bump'], data['RxLQI'], data['TxLQI'], data['Battery']]
            self.csvWriter.writerow(results)
        
        print "Spontaneous Data Logger for %s stopped." % (self.name)
        
        
        #{'Sound': 0.0, 'RxLQI': 108.0, 'unitId': 5, 'Temp': 24.9375, 'Battery': 4.3470158576965332, 'Light': 2716.149658203125, 'Motion': 0.0, 'TxLQI': 120.0}
















