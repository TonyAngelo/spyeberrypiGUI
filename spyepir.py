#########################################################################
#########################################################################
#
# Spyeworks - Motion Sensor Interface - v1
#
# This program uses the Rasberry Pi to track a connected motion sensor 
# and based on it's state change the playlist on a Spyeworks Digital 
# Signage Player from an Active list to an Idle list.
#
# by Tony Petrangelo
# tonypetrangelo@gmail.com
#
#########################################################################
#########################################################################

# import libraries
import RPi.GPIO as GPIO # for the sensor
from threading import Timer # for delay timers
import time # for measuring spyeworks buffer timeout
import chardet # for character encoding/decoding
import socket # for ip comms

# data object
class Observable:
    def __init__(self, initialValue=None):
        self.data = initialValue
        self.callbacks = {}

    def addCallback(self, func):
        self.callbacks[func] = 1

    def delCallback(self, func):
        del self.callback[func]

    def _docallbacks(self):
        for func in self.callbacks:
            func(self.data)

    def set(self, data):
        self.data = data
        self._docallbacks()

    def get(self):
        return self.data

    def unset(self):
        self.data = None

# sensor instance of the observable class
class Sensor(Observable):
    def __init__(self, sensor=1, initialValue="Off"):
        Observable.__init__(self,initialValue)
        self.sensor=sensor
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(self.sensor,GPIO.IN,GPIO.PUD_DOWN)
        GPIO.add_event_detect(self.sensor,GPIO.BOTH,self.sensorChange)

    def sensorChange(self,value):
        if GPIO.input(value):
            self.set("On")
        else:
            self.set("Off")

# spyeworks instance
class Spyeworks(Observable):
    def __init__(self,ipaddy,filepath,active,idle,initialValue="Offline"):
        Observable.__init__(self,initialValue)
        self.ipaddy=ipaddy
        self.port=8900
        self.filepath=filepath
        self.active=active
        self.idle=idle
        self.activeplaying=False
        self.idleplaying=False
        self.parse=False
        self.currentList=Observable()
        self.allLists=Observable()
        self.getCurrentList()

    def login(self,cmd=""):
        # initiate the socket
        s=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        # set the socket connect timeout
        s.settimeout(5)
        # try to connect
        try:
            s.connect((self.ipaddy,self.port))
        # connection error
        except:
            self.set("Connection Error")
        # socket connected
        else:
            # send the login msg
            s.send(b'LOGIN\r\n')
            # receive the reply
            msg=s.recv(1024)
            # decode the reply
            msg=msg.decode('ascii')
            # if it's an OK, login is good
            if(msg[:2]=='OK'):
                # set device to Online
                self.set("Online")
                # if there is a command
                if len(cmd)>0:
                    # send the endcoded command
                    s.send(cmd.encode())
                    # if the command needs to be parsed
                    if self.parse:
                        if self.parseType=='active':
                            # set the active string and change the flags
                            self.currentList.set(self.active)
                            self.activeplaying=True
                            self.idleplaying=False
                        elif self.parseType=='idle':
                            # set the idle string and change the flags
                            self.currentList.set(self.idle)
                            self.activeplaying=False
                            self.idleplaying=True
                        # reset the parse flag
                        self.parse=False
                        # get the strings for parsing
                        stringsForParsing=self.recv_timeout(s).split('\r\n')
                        # if we are pasring an all playlists response
                        if self.parseType=='all':
                            allListsTemp=[]
                            # loop over strings
                            for st in stringsForParsing:
                                myString=st[len(self.filepath):-12]
                                if len(myString)>0:
                                    # add response to list
                                    allListsTemp.append(myString)
                            self.allLists.set(allListsTemp)
                        # if we are parsing the current list
                        elif self.parseType=='current':
                            # loop over strings
                            for st in stringsForParsing:
                                # get the playlist response
                                myString=st[len(self.filepath):-4]
                                # if there is a response
                                if len(myString)>0:
                                    # assign response to current list
                                    self.currentList.set(myString)
            # login not okay         
            else:
                # set the device to login error
                self.set("Login Error")
            # close the socket connection
            s.close()

    # routine for receiving chunks of data from a socket
    def recv_timeout(self,mySocket,timeout=.5):
        # set the socket to nonblocking
        mySocket.setblocking(0)
        # initiate the variables
        buffer=[]
        data=''
        begin=time.time()
        # start the while loop
        while 1:
            # if there is data and we've reached the timeout, end the while
            if buffer and time.time()-begin > timeout:
                break
            # if there is no data, wait for twice the timeout
            elif time.time()-begin > timeout*2:
                break
            
            # receive data
            try:
                data=mySocket.recv(8192)
            except:
                pass
            else:
                # if data received
                if data:
                    # get the encoding type
                    encoding=chardet.detect(data)['encoding']
                    # add data to buffer
                    buffer.append(data.decode(encoding))
                    # reset timeout
                    begin=time.time()

        # join the buffer for return
        return ''.join(buffer)

    def getCurrentList(self):
        self.parse=True
        self.parseType='current'
        self.login('SCP\r\n')

    def getAllPlaylists(self):
        self.parse=True
        self.parseType='all'
        self.login('DML\r\n')

    def playActive(self):
        self.parse=True
        self.parseType='active'
        self.login('SPL'+self.filepath+self.active+'.dml\r\n')

    def playIdle(self):
        self.parse=True
        self.parseType='idle'
        self.login('SPL'+self.filepath+self.idle+'.dml\r\n')

# model
class Model:
    def __init__(self):
        #check to see if values are in text file, otherwise load defaults
        try:
            f=open('spyeconfig.txt','r')
        # problem opening the file, load the default values
        except:
            self.ipaddy = Observable("192.168.1.110")
            self.filepath = Observable("c:/users/public/documents/spyeworks/content/")
            self.active = Observable("active")
            self.idle = Observable("idle")
            self.sensorenable = Observable("T")
            self.activelist = Observable("T")
            self.activedelaytime = Observable("0")
            self.idlelist = Observable("T")
            self.idledelaytime = Observable("0")
            self.UpdateTextFile()
        else:
            self.ipaddy = Observable(f.readline()[:-1])
            self.filepath = Observable(f.readline()[:-1])
            self.active = Observable(f.readline()[:-1])
            self.idle = Observable(f.readline()[:-1])
            self.sensorenable = Observable(f.readline()[:-1])
            self.activelist = Observable(f.readline()[:-1])
            self.activedelaytime = Observable(f.readline()[:-1])
            self.idlelist = Observable(f.readline()[:-1])
            self.idledelaytime = Observable(f.readline()[:-1])
        # close the file
        f.close()

        # get the current status of the sensor variable
        self.sensorstate = Sensor(14)

        # initiate the spyeworks player
        self.spyeworks = Spyeworks(self.ipaddy.get(),self.filepath.get(),
                                   self.active.get(),self.idle.get())

    ###############################################################
    ### Methods for the controller to update variables in the model
    ###############################################################

    def SetIP(self, value):
        self.ipaddy.set(value)
        self.UpdateTextFile()
        # also update the spyeworks player
        self.spyeworks.ipaddy=value

    def SetFilepath(self, value):
        self.filepath.set(value)
        self.UpdateTextFile()
        # also update the spyeworks player
        self.spyeworks.filepath=value

    def SetActive(self, value):
        self.active.set(value)
        self.UpdateTextFile()
        # also update the spyeworks player
        self.spyeworks.active=value

    def SetIdle(self, value):
        self.idle.set(value)
        self.UpdateTextFile()
        # also update the spyeworks player
        self.spyeworks.idle=value

    def SetSensorEnable(self,value):
        self.sensorenable.set(value)
        self.UpdateTextFile()

    def SetActiveList(self, value):
        self.activelist.set(value)
        self.UpdateTextFile()

    def SetActiveDelayTime(self, value):
        self.activedelaytime.set(value)
        self.UpdateTextFile()

    def SetIdleList(self, value):
        self.idlelist.set(value)
        self.UpdateTextFile()

    def SetIdleDelayTime(self, value):
        self.idledelaytime.set(value)
        self.UpdateTextFile()

    ##########################################################
    ### Method for writing current model values to a text file
    ##########################################################

    def UpdateTextFile(self):
        # write the model to a text file for tracking variable changes
        f=open('spyeconfig.txt','w+')
        f.write(self.ipaddy.get()+'\n'+self.filepath.get()+'\n'+self.active.get()+'\n'+self.idle.get()+'\n'+self.sensorenable.get()+'\n'+
            self.activelist.get()+'\n'+self.activedelaytime.get()+'\n'+self.idlelist.get()+'\n'+self.idledelaytime.get()+'\n')
        f.close()


# controller, talks to views and models
class Controller:
    def __init__(self):
        # create model and setup callbacks
        self.model = Model()
        self.model.spyeworks.addCallback(self.updatePlayerOnline)
        self.model.spyeworks.currentList.addCallback(self.updateCurrentList)
        self.model.sensorstate.addCallback(self.updateSensorState)

        # create variables for timers
        self.activeTimer=Timer(1, self.dummyFunc, ())
        self.idleTimer=Timer(1, self.dummyFunc, ())
        self.playIdleList=False

        # update variables with data from model
        self.updatePlayerOnline(self.model.spyeworks.get())
        self.updateSensorState(self.model.sensorstate.get())

    #################################
    ### Methods for printing to the console
    #################################

    # updates the player online status in the view
    def updatePlayerOnline(self, value):
        #print("Player is "+value)
        pass

    # updates the current list status in the view
    def updateCurrentList(self, value):
        #print("Current List is "+value)
        pass

    # dummy function for passing to timer thread
    def dummyFunc(self):
        pass

    # handles updates to the sensor status
    def updateSensorState(self, value):
        # updates the sensor status in the view
        #print("Sensor is "+value)
        # if the sensor is activated
        if value=="On":
            # if the idle timer is active, cancel it
            if self.idleTimer.isAlive()==True:
                self.idleTimer.cancel()
            # if the idle list is playing, play the active list
            if self.model.spyeworks.currentList.get()==self.model.idle.get():
                self.model.spyeworks.playActive()
            
        # if the sensor is inactive and the idle list is enabled
        elif value=="Off" and self.model.idlelist.get()=="T":
            # if the idle timer is going (it shouldn't be, but just in case)
            if self.idleTimer.isAlive()==True:
                self.idleTimer.cancel()
            # start the idle list timer
            self.idleTimer=Timer(int(self.model.idledelaytime.get()), self.model.spyeworks.playIdle, ())
            self.idleTimer.start()

    # plays idle list when active list is finished if called for
    def activeListTimer(self):
        if self.playIdleList==True and self.model.sensorstate.get()=="Off" and self.model.idlelist.get()=="T":
            self.idleTimer=Timer(int(self.model.idledelaytime.get()), self.model.spyeworks.playIdle, ())
            self.idleTimer.start()
        self.playIdleList=False

app = Controller()

while True:
    pass