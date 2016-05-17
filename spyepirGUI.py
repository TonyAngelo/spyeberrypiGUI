#########################################################################
#########################################################################
#
# Spyeworks - Motion Sensor GUI - v1
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
#
# To do:
#
# Playlist routines; allow user to select from available lists
#    on the active, idle selection popups
#
#########################################################################
#########################################################################

# load imports
import tkinter as tk # for gui
from threading import Timer # for delay timers
import socket # for connecting with ip devices
import ipaddress # for validating ip addresses
import re # regex for validating text feilds
import chardet # for character encoding/decoding
import time # for measuring spyeworks buffer timeout
try:
    import RPi.GPIO as GPIO # for using sensor inputs
except:
    dev_mode=1
else:
    dev_mode=0

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
        if dev_mode==0:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            GPIO.setup(self.sensor,GPIO.IN,GPIO.PUD_DOWN)
            GPIO.add_event_detect(self.sensor,GPIO.BOTH,self.sensorChange)

    def sensorChange(self,value):
        if dev_mode==0:
            if GPIO.input(value):
                self.set("On")
            else:
                self.set("Off")
        else:
            self.set("Off")

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

# main view
class View(tk.Toplevel):
    def __init__(self, master):
        tk.Toplevel.__init__(self, master)
        self.protocol('WM_DELETE_WINDOW', self.master.destroy)
        self.title('Spyeworks Motion Settings')
        self.geometry("800x600")
        self.grid_columnconfigure(7, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # grid constants
        SPACE_COL=0
        LABEL_COL=1
        VALUE_COL=2
        LABEL2_COL=2
        VALUE2_COL=3
        BTN_COL=4
        VALUE_WIDTH=50
        EDIT_WIDTH=8

        ###################
        ### Begin GUI Setup
        ###################
        # spacer
        nRowNum=0
        self.titlespacerlabel = tk.Label(self, text='     ')
        self.titlespacerlabel.grid(column=SPACE_COL,row=nRowNum)
        # spyeworks title
        nRowNum=nRowNum+1
        self.spyetitlelabel = tk.Label(self, text='Spyeworks Settings')
        self.spyetitlelabel.grid(column=VALUE_COL,row=nRowNum)
        # spacer
        nRowNum=nRowNum+1
        self.titlespacerlabel = tk.Label(self, text='     ')
        self.titlespacerlabel.grid(column=SPACE_COL,row=nRowNum)
        # spyeworks online status
        nRowNum=nRowNum+1
        self.spyeworksonline = tk.Label(self)
        self.spyeworksonline.grid(column=VALUE_COL,row=nRowNum)
        # spacer
        nRowNum=nRowNum+1
        self.titlespacerlabel = tk.Label(self, text='     ')
        self.titlespacerlabel.grid(column=SPACE_COL,row=nRowNum)
        # spyeworks current list
        nRowNum=nRowNum+1
        self.spyeworkscurrentlist = tk.Label(self)
        self.spyeworkscurrentlist.grid(column=VALUE_COL,row=nRowNum)
        # spacer
        nRowNum=nRowNum+1
        self.titlespacerlabel = tk.Label(self, text='     ')
        self.titlespacerlabel.grid(column=SPACE_COL,row=nRowNum)
        # ip address section
        nRowNum=nRowNum+1
        tk.Label(self, text='IP Address:').grid(column=LABEL_COL,row=nRowNum,sticky=tk.E,padx=5,pady=5)
        self.IPActual = tk.Label(self)
        self.IPActual.grid(column=VALUE_COL,row=nRowNum,sticky=tk.W)
        self.editIPButton = tk.Button(self, text='EDIT', width=EDIT_WIDTH)
        self.editIPButton.grid(column=BTN_COL,row=nRowNum,sticky=tk.E)
        # filepath section
        nRowNum=nRowNum+1
        tk.Label(self, text='Filepath:').grid(column=LABEL_COL,row=nRowNum,sticky=tk.E,padx=5,pady=5)
        self.FilepathActual = tk.Label(self)
        self.FilepathActual.grid(column=VALUE_COL,row=nRowNum,sticky=tk.W)
        self.editFilepathButton = tk.Button(self, text='EDIT', width=EDIT_WIDTH)
        self.editFilepathButton.grid(column=BTN_COL,row=nRowNum,sticky=tk.E)
        # active section
        nRowNum=nRowNum+1
        tk.Label(self, text='Active List:').grid(column=LABEL_COL,row=nRowNum,sticky=tk.E,padx=5,pady=5)
        self.ActiveActual = tk.Label(self)
        self.ActiveActual.grid(column=VALUE_COL,row=nRowNum,sticky=tk.W)
        self.editActiveButton = tk.Button(self, text='EDIT', width=EDIT_WIDTH)
        self.editActiveButton.grid(column=BTN_COL,row=nRowNum,sticky=tk.E)
        # idle section
        nRowNum=nRowNum+1
        tk.Label(self, text='Idle List:').grid(column=LABEL_COL,row=nRowNum,sticky=tk.E,padx=5,pady=5)
        self.IdleActual = tk.Label(self)
        self.IdleActual.grid(column=VALUE_COL,row=nRowNum,sticky=tk.W)
        self.editIdleButton = tk.Button(self, text='EDIT', width=EDIT_WIDTH)
        self.editIdleButton.grid(column=BTN_COL,row=nRowNum,sticky=tk.E)
        # spacer
        nRowNum=nRowNum+1
        self.titlespacer2label = tk.Label(self, text='     ')
        self.titlespacer2label.grid(column=SPACE_COL,row=nRowNum)
        # motion title
        nRowNum=nRowNum+1
        self.motiontitlelabel = tk.Label(self, text='Motion Settings')
        self.motiontitlelabel.grid(column=VALUE_COL,row=nRowNum)
        # spacer
        nRowNum=nRowNum+1
        self.titlespacerlabel = tk.Label(self, text='     ')
        self.titlespacerlabel.grid(column=5,row=nRowNum)
        # sensor status
        nRowNum=nRowNum+1
        tk.Label(self, text='Sensor Enabled:').grid(column=LABEL_COL,row=nRowNum,sticky=tk.E,padx=5,pady=5)
        self.SensorEnable = tk.Checkbutton(self,onvalue="T", offvalue="F")
        self.SensorEnable.grid(column=VALUE_COL,row=nRowNum,sticky=tk.W)
        tk.Label(self, text='Sensor State:').grid(column=LABEL2_COL,row=nRowNum,sticky=tk.E,padx=5,pady=5)
        self.SensorStatus = tk.Label(self)
        self.SensorStatus.grid(column=VALUE2_COL,row=nRowNum,sticky=tk.W)
        # active delay settings
        nRowNum=nRowNum+1
        tk.Label(self,text="Active List Enabled:").grid(column=LABEL_COL,row=nRowNum,sticky=tk.E,padx=5,pady=5)
        self.ActiveListCheck=tk.Checkbutton(self,onvalue="T", offvalue="F")
        self.ActiveListCheck.grid(column=VALUE_COL,row=nRowNum,sticky=tk.W)
        tk.Label(self,text="Active Delay Time:").grid(column=LABEL2_COL,row=nRowNum,sticky=tk.E,padx=5,pady=5)
        self.ActiveDelayTime=tk.Label(self)
        self.ActiveDelayTime.grid(column=VALUE2_COL,row=nRowNum,sticky=tk.W,padx=5,pady=5)
        self.editActiveDelayTimeButton=tk.Button(self,text="EDIT", width=EDIT_WIDTH)
        self.editActiveDelayTimeButton.grid(column=BTN_COL,row=nRowNum,sticky=tk.E)
        # idle delay settings
        nRowNum=nRowNum+1
        tk.Label(self,text="Idle List Enabled:").grid(column=LABEL_COL,row=nRowNum,sticky=tk.E,padx=5,pady=5)
        self.IdleListCheck=tk.Checkbutton(self,onvalue="T", offvalue="F")
        self.IdleListCheck.grid(column=VALUE_COL,row=nRowNum,sticky=tk.W)
        tk.Label(self,text="Idle Delay Time:").grid(column=LABEL2_COL,row=nRowNum,sticky=tk.E,padx=5,pady=5)
        self.IdleDelayTime=tk.Label(self)
        self.IdleDelayTime.grid(column=VALUE2_COL,row=nRowNum,sticky=tk.W,padx=5,pady=5)
        self.editIdleDelayTimeButton=tk.Button(self,text="EDIT", width=EDIT_WIDTH)
        self.editIdleDelayTimeButton.grid(column=BTN_COL,row=nRowNum,sticky=tk.E)

        #################
        ### End GUI Setup
        #################

    #####################################################################
    ### Methods used by the controller for updating variables in the view
    #####################################################################

    # changes the ip address displayed to current 
    def updateOnline(self, value):
        self.spyeworksonline.config(text="Player Status: "+value) 

    # changes the list displayed to current 
    def updateCurrentList(self, value):
        self.spyeworkscurrentlist.config(text="Current Playlist: "+value) 
        
    # changes the lists available
    def updateAllLists(self, value):
        pass

    # changes the ip address displayed to current 
    def updateIP(self, value):
        self.IPActual.config(text=value) 

    # changes the filepath displayed to current
    def updateFilepath(self, value):
        self.FilepathActual.config(text=value) 

    # changes the active playlist displayed to current
    def updateActive(self, value):
        self.ActiveActual.config(text=value) 

    # changes the idle playlist displayed to current
    def updateIdle(self, value):
        self.IdleActual.config(text=value) 

    # changes the sensor state displayed to current
    def updateSensor(self, value):
        self.SensorStatus.config(text=value) 

    # changes active list delay time displayed to current
    def updateActiveDelayTime(self, value):
        self.ActiveDelayTime.config(text=value)

    # changes idle list delay time displayed to current
    def updateIdleDelayTime(self, value):
        self.IdleDelayTime.config(text=value) 

# basic popup class for editing variables
class BasicChangerWidget(tk.Toplevel):
    def __init__(self, master, app, title, currlabel, newlabel):
        # initiate the popup as a toplevel object, keep track of the app and set the geometry and title
        tk.Toplevel.__init__(self, master)
        self.app=app
        self.title(title)
        # display the current ip label and value
        self.currlabel=tk.Label(self, text=currlabel).pack(padx=5,pady=5)
        self.curractual=tk.Label(self)
        self.curractual.pack(padx=5,pady=5)
        # display the new ip label and value
        self.value=tk.StringVar(None)
        self.newlabel=tk.Label(self,text=newlabel).pack(padx=5,pady=5)
        self.newentry=tk.Entry(self, textvariable=self.value)
        self.newentry.pack(padx=5,pady=5)
        # display the ok button
        self.okButton = tk.Button(self, text='OK', width=8)
        self.okButton.pack(padx=5,pady=5)
        # add the error message label
        self.errormsg = tk.Label(self)
        self.errormsg.pack(padx=5,pady=5)

# popup window for setting the players ip address
class IPChangerWidget(BasicChangerWidget):
    def __init__(self, master, app, title, currlabel, newlabel):
        BasicChangerWidget.__init__(self, master, app, title, currlabel, newlabel)
        self.geometry('%dx%d+%d+%d' % (300,200,350,250))
        self.okButton.config(command=self.validateIP)

    # validates the value entered to see if it is a valid ip address
    def validateIP(self):
        try:
            ip=ipaddress.ip_address(self.value.get())
        except: # IP is invalid
            # throw an error message
            self.errormsg.config(text=self.value.get()+" is not a valid IP address.")
        else: # IP is valid
            self.app.newIP(self.value.get())
            self.destroy()
        
# popup window for setting the filepath
class FilepathChangerWidget(BasicChangerWidget):
    def __init__(self, master, app, title, currlabel, newlabel):
        BasicChangerWidget.__init__(self, master, app, title, currlabel, newlabel)
        self.geometry('%dx%d+%d+%d' % (400,200,350,250))
        self.okButton.config(command=self.validateFilepath)
        self.newentry.config(width=300)

    # validates the value entered to see if it is a valid filepath
    def validateFilepath(self):
        self.pattern = re.compile("^[a-z]:/[A-Za-z0-9/-_ ]*/$")
        self.validate=self.pattern.match(self.value.get())
        if self.validate: 
            # filepath is valid
            self.app.newFilepath(self.value.get())
            self.destroy()
        else: 
            # throw an error message
            self.errormsg.config(text=self.value.get()+" is not a valid filepath.")

# popup window for setting the active list
class ActiveChangerWidget(BasicChangerWidget):
    def __init__(self, master, app, title, currlabel, newlabel):
        BasicChangerWidget.__init__(self, master, app, title, currlabel, newlabel)
        self.geometry('%dx%d+%d+%d' % (300,200,350,250))
        self.okButton.config(command=self.validateActive)
        self.newentry.config(width=250)

    # validates the value entered to see if it is a valid active list
    def validateActive(self):
        self.pattern = re.compile("^[A-Za-z0-9-_ ]*$")
        self.validate=self.pattern.match(self.value.get())
        if self.validate: 
            # list name is valid
            self.app.newActive(self.value.get())
            self.destroy()
        else: 
            # throw an error message
            self.errormsg.config(text=self.value.get()+" is not a valid playlist name.")

# popup window for setting the idle list
class IdleChangerWidget(BasicChangerWidget):
    def __init__(self, master, app, title, currlabel, newlabel):
        BasicChangerWidget.__init__(self, master, app, title, currlabel, newlabel)
        self.geometry('%dx%d+%d+%d' % (300,200,350,250))
        self.okButton.config(command=self.validateIdle)
        self.newentry.config(width=250)

    # validates the value entered to see if it is a valid idle list
    def validateIdle(self):
        self.pattern = re.compile("^[A-Za-z0-9-_ ]*$")
        self.validate=self.pattern.match(self.value.get())
        if self.validate: 
            # list name is valid
            self.app.newIdle(self.value.get())
            self.destroy()
        else: 
            # throw an error message
            self.errormsg.config(text=self.value.get()+" is not a valid playlist name.")

# popup window for setting the active list delay time
class ActiveDelayTimeChangerWidget(BasicChangerWidget):
    def __init__(self, master, app, title, currlabel, newlabel):
        BasicChangerWidget.__init__(self, master, app, title, currlabel, newlabel)
        self.geometry('%dx%d+%d+%d' % (300,200,350,250))
        self.okButton.config(command=self.validateActiveDelayTime)

    # validates the value entered to see if it is a valid delay time
    def validateActiveDelayTime(self):
        self.pattern = re.compile("^[0-9]*$")
        self.validate=self.pattern.match(self.value.get())
        if self.validate: 
            # delay time is valid
            self.app.newActiveDelayTime(self.value.get())
            self.destroy()
        else: 
            # throw an error message
            self.errormsg.config(text=self.value.get()+" is not a valid delay time.")

# popup window for setting the idle list delay time
class IdleDelayTimeChangerWidget(BasicChangerWidget):
    def __init__(self, master, app, title, currlabel, newlabel):
        BasicChangerWidget.__init__(self, master, app, title, currlabel, newlabel)
        self.geometry('%dx%d+%d+%d' % (300,200,350,250))
        self.okButton.config(command=self.validateIdleDelayTime)

    # validates the value entered to see if it is a valid delay time
    def validateIdleDelayTime(self):
        self.pattern = re.compile("^[0-9]*$")
        self.validate=self.pattern.match(self.value.get())
        if self.validate: 
            # delay time is valid
            self.app.newIdleDelayTime(self.value.get())
            self.destroy()
        else: 
            # throw an error message
            self.errormsg.config(text=self.value.get()+" is not a valid delay time.")

# controller, talks to views and models
class Controller:
    def __init__(self, root):

        # create modle and setup callbacks
        self.model = Model()
        self.model.spyeworks.addCallback(self.updatePlayerOnline)
        self.model.spyeworks.currentList.addCallback(self.updateCurrentList)
        self.model.spyeworks.allLists.addCallback(self.updateAllLists)
        self.model.ipaddy.addCallback(self.updateIP)
        self.model.filepath.addCallback(self.updateFilepath)
        self.model.active.addCallback(self.updateActive)
        self.model.idle.addCallback(self.updateIdle)
        self.model.sensorstate.addCallback(self.updateSensorState)
        self.model.activedelaytime.addCallback(self.updateActiveDelayTime)
        self.model.idledelaytime.addCallback(self.updateIdleDelayTime)

        # create variables for tracking checkboxs and timers
        self.ActiveList=tk.StringVar()
        self.ActiveList.set(self.model.activelist.get())
        self.IdleList=tk.StringVar()
        self.IdleList.set(self.model.idlelist.get())
        self.SensorEnable=tk.StringVar()
        self.SensorEnable.set(self.model.sensorenable.get())
        self.activeTimer=Timer(1, self.dummyFunc, ())
        self.idleTimer=Timer(1, self.dummyFunc, ())
        self.playIdleList=False

        # create main view and link edit btns to funcs
        self.view = View(root)
        self.view.editIPButton.config(command=self.editIP)
        self.view.editFilepathButton.config(command=self.editFilepath)
        self.view.editActiveButton.config(command=self.editActive)
        self.view.editIdleButton.config(command=self.editIdle)
        self.view.SensorEnable.config(variable=self.SensorEnable,command=self.updateSensorEnable)
        self.view.ActiveListCheck.config(variable=self.ActiveList,command=self.updateActiveList)
        self.view.editActiveDelayTimeButton.config(command=self.editActiveDelayTime)
        self.view.IdleListCheck.config(variable=self.IdleList,command=self.updateIdleList)
        self.view.editIdleDelayTimeButton.config(command=self.editIdleDelayTime)

        # update variables with data from model
        self.updatePlayerOnline(self.model.spyeworks.get())
        self.updateCurrentList(self.model.spyeworks.currentList.get())
        self.updateAllLists(self.model.spyeworks.allLists.get())
        self.updateIP(self.model.ipaddy.get())
        self.updateFilepath(self.model.filepath.get())
        self.updateActive(self.model.active.get())
        self.updateIdle(self.model.idle.get())
        self.updateSensorState(self.model.sensorstate.get())
        self.updateActiveDelayTime(self.model.activedelaytime.get())
        self.updateIdleDelayTime(self.model.idledelaytime.get())
    
    #################################################################
    ### Methods for launching the changer popup for changing settings
    #################################################################

    # launches the popup for editing the players ip address
    def editIP(self):
        self.editIP = IPChangerWidget(self.view,self,"Set IP Address","Current IP", "New IP")
        self.editIP.curractual.config(text=self.model.ipaddy.get())

    # launches the popup for editing the filepath
    def editFilepath(self):
        self.editFilepath = FilepathChangerWidget(self.view,self,"Set Filepath","Current Filepath", "New Filepath")
        self.editFilepath.curractual.config(text=self.model.filepath.get())

    # launches the popup for editing the active list
    def editActive(self):
        self.editActive = ActiveChangerWidget(self.view,self,"Set Active List","Current Active List", "New Active List")
        self.editActive.curractual.config(text=self.model.active.get())

    # launches the popup for editing the idle list
    def editIdle(self):
        self.editIdle = IdleChangerWidget(self.view,self,"Set Idle List","Current Idle List", "New Idle List")
        self.editIdle.curractual.config(text=self.model.idle.get())

    # launches the popup for editing the active delay time
    def editActiveDelayTime(self):
        self.editActiveDelayTime = ActiveDelayTimeChangerWidget(self.view,self,"Set Active Delay Time","Current Active Delay Time", "New Active Delay Time")
        self.editActiveDelayTime.curractual.config(text=self.model.activedelaytime.get())

    # launches the popup for editing the idle delay time
    def editIdleDelayTime(self):
        self.editIdleDelayTime = IdleDelayTimeChangerWidget(self.view,self,"Set Idle Delay Time","Current Idle Delay Time", "New Idle Delay Time")
        self.editIdleDelayTime.curractual.config(text=self.model.idledelaytime.get())

    ##################################
    ### Methods for updating the model
    ##################################

    # sets the new ip address returned from the validate ip function
    def newIP(self, value):
        self.model.SetIP(value)

    # sets the new filepath returned from the validate filepath function
    def newFilepath(self, value):
        self.model.SetFilepath(value)

    # sets the new active list returned from the validate active function
    def newActive(self, value):
        self.model.SetActive(value)

    # sets the new idle list returned from the validate idle function
    def newIdle(self, value):
        self.model.SetIdle(value)

    # sets the new idle list returned from the validate idle function
    def newActiveDelayTime(self, value):
        self.model.SetActiveDelayTime(value)

    # sets the new idle list returned from the validate idle function
    def newIdleDelayTime(self, value):
        self.model.SetIdleDelayTime(value)
    
    #################################
    ### Methods for updating the view
    #################################

    # updates the player online status in the view
    def updatePlayerOnline(self, value):
        self.view.updateOnline(value)

    # updates the current list status in the view
    def updateCurrentList(self, value):
        self.view.updateCurrentList(value)

    # updates the current list status in the view
    def updateAllLists(self, value):
        self.view.updateAllLists(value)

    # updates the ip address in the view
    def updateIP(self, value):
        self.view.updateIP(value)

    # updates the filepath in the view
    def updateFilepath(self, value):
        self.view.updateFilepath(value)

    # updates the active list in the view
    def updateActive(self, value):
        self.view.updateActive(value)

    # updates the idle list in the view
    def updateIdle(self, value):
        self.view.updateIdle(value)

    # updates the sensor status in the view
    def updateSensorEnable(self):
        self.model.SetSensorEnable(self.SensorEnable.get())
        # if the sensor has been disabled, cancel any active timers
        if self.SensorEnable.get()=="F":
            if self.activeTimer.isAlive():
                self.activeTimer.cancel()
            if self.idleTimer.isAlive():
                self.idleTimer.cancel()

    # dummy function for passing to timer thread
    def dummyFunc(self):
        pass

    # handles updates to the sensor status
    def updateSensorState(self, value):
        # updates the sensor status in the view
        self.view.updateSensor(value)
        # sensor effects
        # if sensor is enabled
        if self.SensorEnable.get()=="T":
            # if the sensor is activated
            if value=="On":
                # if the idle timer is active, cancel it
                if self.idleTimer.isAlive()==True:
                    self.idleTimer.cancel()
                # if the active timer is on and the active list is enabled, restart the active timer
                if self.activeTimer.isAlive()==True and self.model.activelist.get()=="T":
                    self.activeTimer.cancel()
                    self.activeTimer=Timer(int(self.model.activedelaytime.get()), self.activeListTimer, ())
                    self.activeTimer.start()
                else:
                    self.model.spyeworks.playActive()
                    self.activeTimer=Timer(int(self.model.activedelaytime.get()), self.activeListTimer, ())
                    self.activeTimer.start()
                
            # if the sensor is inactive and the idle list is enabled
            elif value=="Off" and self.model.idlelist.get()=="T":
                # if the idle timer is going (it shouldn't be, but just in case)
                if self.idleTimer.isAlive()==True:
                    self.idleTimer.cancel()
                # if the active list timer is running and the active list is enabled
                if self.activeTimer.isAlive()==True and self.model.activelist.get()=="T":
                    self.playIdleList=True
                # if the active timer is not running or the active list isn't enabled
                else:
                    self.idleTimer=Timer(int(self.model.idledelaytime.get()), self.model.spyeworks.playIdle, ())
                    self.idleTimer.start()

    # plays idle list when active list is finished if called for
    def activeListTimer(self):
        if self.playIdleList==True and self.model.sensorstate.get()=="Off" and self.model.idlelist.get()=="T":
            self.idleTimer=Timer(int(self.model.idledelaytime.get()), self.model.spyeworks.playIdle, ())
            self.idleTimer.start()
        self.playIdleList=False

    # updates the active delay in the view
    def updateActiveList(self):
        self.model.SetActiveList(self.ActiveList.get())

    # updates the active delay time in the view
    def updateActiveDelayTime(self, value):
        self.view.updateActiveDelayTime(value)

    # updates the idle delay in the view
    def updateIdleList(self):
        self.model.SetIdleList(self.IdleList.get())

    # updates the idle delay time in the view
    def updateIdleDelayTime(self, value):
        self.view.updateIdleDelayTime(value)

if __name__ == '__main__':
    root = tk.Tk()
    root.withdraw()
    app = Controller(root)
    root.mainloop()
