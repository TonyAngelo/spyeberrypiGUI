###############################################################
###
###   Raspberry pi motion control of Spyeworks, console version
###
###   this is a proof of concept, not a fully featured program
###
###############################################################


# import libraries
import RPi.GPIO as GPIO
import time
import socket

# sensor number used
sensor=14
# sensor setup
GPIO.setmode(GPIO.BCM)
GPIO.setup(sensor,GPIO.IN,GPIO.PUD_DOWN)
# setup sensor states
prev_state=False
curr_state=False

# function for playing spyeworks list
def fnPlayList(player,path,name):
    s=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    s.connect((player,8900))
    s.send(b'LOGIN\r\n')
    msg=s.recv(1024)
    if(msg.decode('ascii')[:2]=='OK'):
        cmd='SPL'+path+name+'.dml\r\n'
        s.send(cmd.encode())
    s.close()

def UpdateTextFile():
    # write the model to a text file for tracking variable changes
    f=open('spyeconfig.txt','w+')
    f.write(player_IP+'\n'+listpath+'\n'+active_list+'\n'+idle_list+'\n'+active_delay_state+'\n'+
        active_delay_time+'\n'+idle_delay_state+'\n'+idle_delay_time+'\n')
    f.close()

#check to see if values are in text file, otherwise load defaults
try:
    f=open('spyeconfig.txt','r')
# problem opening the file, load the default values
except:
    player_IP = Observable("192.168.1.110")
    listpath = Observable("c:/users/public/documents/spyeworks/content/")
    active_list = Observable("active")
    idle_list = Observable("idle")
    active_delay_state = Observable("F")
    active_delay_time = Observable("0")
    idle_delay_state = Observable("T")
    idle_delay_time = Observable("10")
    UpdateTextFile()
else:
    player_IP = Observable(f.readline()[:-1])
    listpath = Observable(f.readline()[:-1])
    active_list = Observable(f.readline()[:-1])
    idle_list = Observable(f.readline()[:-1])
    active_delay_state = Observable(f.readline()[:-1])
    active_delay_time = Observable(f.readline()[:-1])
    idle_delay_state = Observable(f.readline()[:-1])
    idle_delay_time = Observable(f.readline()[:-1])
# close the file
f.close()

# start sensor loop
while True:
    time.sleep(0.1)
    prev_state=curr_state
    curr_state=GPIO.input(sensor)
    if curr_state!=prev_state:
        if curr_state:
            if active_delay_state=="T":
                time.sleep(int(active_delay_time))
                fnPlayList(player_IP,listpath,active_list) # active list
        else:
            if idle_delay_state=="T":
                time.sleep(int(idle_delay_time))
                fnPlayList(player_IP,listpath,idle_list) # idle list
