###############################################################
###
###   Spyeworks python class
###
###############################################################

import socket # for connecting with ip devices
import chardet
import time

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

# spyeworks instance of the observable class
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
        self.login()

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
                                #if len(myString)>0:
                                    # assign response to current list
                                self.currentList.set(myString)
            # login not okay         
            else:
                # set the device to login error
                self.set("Login Error")
            # close the socket connection
            s.close()

    # routine for receiving chunks of data from a socket
    def recv_timeout(self,mySocket,timeout=.25):
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
        self.login('SPL'+self.filepath+self.active+'.dml\r\n')
        print("Play Active")
        #self.currentlist=self.active
        self.activeplaying=True
        self.idleplaying=False

    def playIdle(self):
        self.login('SPL'+self.filepath+self.idle+'.dml\r\n')
        print("Play Idle")
        #self.currentlist=self.idle
        self.activeplaying=False
        self.idleplaying=True

def updatePlayerOnline(value):
    print(value)

def updateCurrentList(value):
    print(value)

def updateAllLists(value):
    print(value)


spyeworks = Spyeworks("10.10.9.51",
                    "c:/users/public/documents/spyeworks/content/",
                    "code 42","jamf")

spyeworks.addCallback(updatePlayerOnline)
spyeworks.currentList.addCallback(updateCurrentList)
spyeworks.allLists.addCallback(updateAllLists)
