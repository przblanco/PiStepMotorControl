""" Control of bipolar step motor using 8825 driver

Description:
    This module implementa a class to control bipolar step motor using 8825 driver
    Also a class to implement TPC/IP remote control of the control class have been implemeted,
    the user can connect with hyperterminal or telnet and control trhe motor thotug a remote menu
    
Author:
    Pablo Rodriguez-2018
    
'""" 
#!/usr/bin/python
# Import required libraries

import sys
import RPi.GPIO as GPIO
import pigpio

import  socket

from tkinter import *
import tkinter.font
import time
import threading
from enum import Enum

appDebug = False

def lostStep(channel):
    print("lostStep" )


class stepMotorDriver8825(threading.Thread):
    """ Class to control  step motor movements using a 8825 driver """
    #
    # defult tag plate position respct the reader (the attack angle from the TAG)
    DEFAULT_PLATE_POSITION = 90
    #
    # step motor min resolution degres
    #STEP_RESOLUTION = 360 / (200)
    STEP_RESOLUTION = 360 / (200 *  32)
    
    
    #
    # step motor frequency in pigiod   17        16     15      14      13      12  11  10      9
    #                                                   (8000  4000  2000 1600 1000  800  500  400  320)
    #                                                       8           7       6       5       4       3       2   1       0
    #                                                   (250       200    160   100    80     50     40  20     10 )
    STEP_MOTOR_FREQ =  2000
    
        
    #
    # back direction
    MOVE_BACK = 0
    #
    # forward direction
    MOVE_FORWARD = 1
    #
    # current plate position
    currPlatePosition = DEFAULT_PLATE_POSITION
    #
    # possition demanded by GUI
    demandedPlatePosition = currPlatePosition
    #
    # detectection of reference position PIN
    referencePIN = 16

    #
    # if the plate is currently in movement, if it is, we can not demand a new movement until the current is ended
    inMovement = False

    #
    # we are looking for reference
    lookingForReference = False

    #
    # step movements pending to be executed
    pendingMovements = 0

    #
    # direction of the current movement in execution
    moveDirection = MOVE_FORWARD

    #
    # pin used to produce steps, a generate square wave is used
    stepPin = None
    dirPin = None
    #
    # to control step pin square generation
    stepPWM = None

    #
    # if the postion have to be update
    updatePosition = False

    #
    # access to GPIO
    gpioControl = pigpio.pi()


    
    #def stepDetection(self,channel):
    def stepDetection(self,g,b,t):
        """ on each step detected we decrement the number of pending movements """
        self.pendingMovements = self.pendingMovements - 1
        if (self.updatePosition):
            #
            # update curr plate position
            if (self.moveDirection == self.MOVE_BACK):
                self.currPlatePosition = self.currPlatePosition - self.STEP_RESOLUTION
            else:
                self.currPlatePosition = self.currPlatePosition + self.STEP_RESOLUTION
        
    
    #
    # on construction the thread starts
    def __init__(self):
        self.loop_active = True
        threading.Thread.__init__(self)
        self.setupPins()
        self.start()

    #
    #  setup board pins
    def setupPins(self):
        # Use BCM GPIO references
        # instead of physical pin numbers
        GPIO.setmode(GPIO.BCM)
        
        #
        # Define GPIO signals to use
        #GPIO20 for direction and 21 for step
        self.stepPin = 21
        self.dirPin = 20

        

        if (not self.gpioControl.connected):
            print ("pigiod connection error")

        self.gpioControl.set_mode(self.stepPin,pigpio.OUTPUT)
        self.gpioControl.set_PWM_frequency(self.stepPin,self.STEP_MOTOR_FREQ)

        #
        # step detection
        GPIO.setup(4, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        #GPIO.add_event_detect(4, GPIO.RISING, callback=self.stepDetection)
        self.gpioControl.callback(4,pigpio.RISING_EDGE,self.stepDetection)
        
        GPIO.setup(self.dirPin,GPIO.OUT)
        GPIO.output(self.dirPin,self.moveDirection)

        #
        # set reference pin as input
        GPIO.setup(self.referencePIN,GPIO.IN,GPIO.PUD_DOWN)
    
    #
    #  look for the plate initial posiition (DEFAULT_PLATE_POSITION)
    def lookForReference(self):
        #
        # by default we return that the movement is not possible
        retVal = False
        if (not  self.inMovement):
            retVal = True
            self.moveDirection = self.MOVE_FORWARD
            self.lookingForReference = True
            self.inMovement = True
            #
            # update direction before start movement
            GPIO.output(self.dirPin,self.moveDirection)
            #
            # start pulses on step pin
            self.gpioControl.set_PWM_dutycycle(self.stepPin,128)
                    
        return retVal
            
        
    def getCurrPlatePosition(self):
        """ return curr plate position """
        return self.currPlatePosition

    def getCurrParams(self):
        """ return curr plate position and speed in string"""
        return "Position: " +str(int( self.currPlatePosition)) + " --- Speed (RPM): " + str((self.STEP_RESOLUTION*self.STEP_MOTOR_FREQ*60)/360)

    
    def  moveTo(self,position):
        """ start movement of plate to demanded position"""
        #
        # by default we return that the movement is not possible
        retVal = False
        if (not  self.inMovement):
            retVal = True
            #
            # check if we have to move (if we are more than one step away of the desired position
            if (abs(position - self.currPlatePosition) >= self.STEP_RESOLUTION):
                #
                #   how far how we have to move and in what direction
                self.pendingMovements =  int(abs(position - self.currPlatePosition) /self.STEP_RESOLUTION)
                
                if (self.currPlatePosition >  position):
                    self.moveDirection = self.MOVE_BACK
                else:
                    self.moveDirection = self.MOVE_FORWARD
                self.updatePosition = True
                self.inMovement = True
                #
                # update direction before start movement
                GPIO.output(self.dirPin,self.moveDirection)
                #
                # start pulses on step pin
                self.gpioControl.set_PWM_dutycycle(self.stepPin,128)
                    
        return retVal

    def  advanceOneDegree(self):
        """ moves one degree or the minimum current resolution """
        destination = self.currPlatePosition + 1
        
        if (self.STEP_RESOLUTION > 1):
            destination = self.currPlatePosition + self.STEP_RESOLUTION + 1

        self.moveTo(destination)

    def setReference(self):
        self.gpioControl.set_PWM_dutycycle(self.stepPin,0)
        self.currPlatePosition = self.DEFAULT_PLATE_POSITION
        print("reference found")
        self.lookingForReference = False
        self.InMovement = False

    #
    # infinite loop of the thread
    def run(self):
        count = 0
        while self.loop_active:
            time.sleep(0.0001)
       
            #
            # if we need to move the plate (dur to moveTo or lookForReference demmand)
            if (self.inMovement):
                #
                # Move one step
                #self.moveOneStep(self.moveDirection,True)
                if (self.lookingForReference):
                    if (GPIO.input(self.referencePIN) == 1):
                        #
                        # stop pulses on step pin
                        self.gpioControl.set_PWM_dutycycle(self.stepPin,0)
                        self.currPlatePosition = self.DEFAULT_PLATE_POSITION
                        print("reference found")
                        self.lookingForReference = False
                        self.InMovement = False
                        
                else:
                    if (self.pendingMovements <= 0):
                        self.gpioControl.set_PWM_dutycycle(self.stepPin,0)
                        self.inMovement = False
                    count = count + 1
                    if (count % 100 == 0):
                        if (appDebug):
                            print("curr position:", int(self.currPlatePosition) , " - In movement: ", self.inMovement, " - Pending steps: ", self.pendingMovements)

    #
    # collaboative method to terminale
    def terminate(self):
        #
        # start pulses on step pin and close connection
        self.gpioControl.set_PWM_dutycycle(self.stepPin,0)
        self.gpioControl.stop()
                
        self.loop_active = False



class motorControlTerminalConnection(threading.Thread):
    """ Connection instance from TCP/IP terminal to control de motor """
    loop_active = True
    sock = None
    motorControl = None

    def showMenu(self):
        try:
            self.sock.send("\r\n".encode())
            self.sock.send("=================  Plate control menu ===============\r\n".encode())
            self.sock.send("\r\n".encode())
            
            self.sock.send("                 1.-  Move to 0\r\n".encode())
            self.sock.send("                 2.-  Move to 45\r\n".encode())
            self.sock.send("                 3.-  Move to 90\r\n".encode())
            self.sock.send("                 4.-  Move to 135\r\n".encode())
            self.sock.send("                 5.-  Move to  180\r\n".encode())
            self.sock.send("\r\n".encode())
            self.sock.send("                 F.-  Fix\r\n".encode())
            self.sock.send("                 S.-  Search\r\n".encode())
            self.sock.send("                 A.-  Advance\r\n".encode())
            self.sock.send("\r\n".encode())
            self.sock.send("                 0.-  Close connection\r\n".encode())
            self.sock.send("\r\n".encode())
            self.sock.send(self.motorControl.getCurrParams().encode())
            self.sock.send("\r\n".encode())
            self.sock.send("\r\n".encode())
            
            self.sock.send("               Type option and press [Enter]:".encode())
        except:
            print("Connection, error refreshing menu")
        

    def __init__(self,s=None, motorControl = None):
        self.sock = s
        self.sock.settimeout(0.2) # timeout for listening
        self.motorControl = motorControl
        self.showMenu()   
        self.loop_active = True
        threading.Thread.__init__(self)
        self.start()

    #
    # closes the current server socket
    def closeSocket(self):
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
            self.sock.close()
            print("connection socket closed")
        except:
            print("error closing connetion socket")
    
    def run(self):
        while self.loop_active:
            try:
                data = self.sock.recv(1024).decode()
            except socket.timeout:
                pass
            except:
                print ("unhandle exception in connection")
                self.terminate()
            else:
                if (len(data) >= 1):
                    if (data[0] == "F" or data[0] == "f"):
                       self.motorControl.setReference()
                    if (data[0] == "0"):
                       self.terminate()
                    if (data[0] == "1"):
                        self.motorControl.moveTo(0)
                    if (data[0] == "2"):
                        self.motorControl.moveTo(45)
                    if (data[0] == "3"):
                        self.motorControl.moveTo(90)
                    if (data[0] == "4"):
                        self.motorControl.moveTo(135)
                    if (data[0] == "5"):
                        self.motorControl.moveTo(180)
                    if (data[0] == "S" or data[0] == "s"):
                        self.motorControl.lookForReference()
                    if (data[0] == "A" or data[0] == "a"):
                        self.motorControl.advanceOneDegree()

                    self.showMenu();
                    
            
    #
    # collaboative method to terminale
    def terminate(self):
        self.loop_active = False
        try:
            self.sock.send("\r\n".encode())
            self.sock.send("Connection Closed\r\n".encode())
            self.sock.send("\r\n".encode())
            self.closeSocket()
        except:
            print ("Unhandle terminating Connection")
            

class motorControlTerminalServer(threading.Thread):
    """ TCP/IP socket server class that admit connections of 12345
          on connection a motorControlTerminalConnection is created to
          process command to control de step motor """
    
    loop_active = True
    TCP_IP = '0.0.0.0'
    TCP_PORT = 12345
    BUFFER_SIZE = 1024  # Normally 1024, but we want fast response
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((TCP_IP, TCP_PORT))
    s.listen(1)
    client = None
    motorControl = None

    def __init__(self, motorControl):
        self.motorControl= motorControl
        self.loop_active = True
        threading.Thread.__init__(self)
        self.start()

    #
    # closes the current server socket
    def closeSocket(self):
        try:
            self.s.close()
            print("server socket closed")
        except:
            print("error closing server socket")
    
    def run(self):
        while self.loop_active:
            try:
                self.s.settimeout(0.2) # timeout for listening
                self.s.listen(1)
                (conn, (ip, port)) = self.s.accept()
            except socket.timeout:
                pass
            except:
                print ("Unhandle exception ControlTerminal")
                self.terminate()
            else:
                # work with the connection, create a thread etc.
                print("connection!")
                self.client = motorControlTerminalConnection(conn,self.motorControl)
                   
    #
    # collaboative method to terminale
    def terminate(self):
        self.loop_active = False
        try:
            if (not self.client == None):
                print ("Finishing client ...")
                self.client.terminate()
        except:
            print ("Unhandle terminating ControlTerminal")

        self.closeSocket()
        
#
# create the plate control thread 
motor_control = stepMotorDriver8825()

#
# create TCP-IP server to build remote control connections
control_terminal = motorControlTerminalServer(motor_control)

#
# create GUI
win = Tk()
winFont = font.Font(family="Helvetica", size = 15, weight = "bold")
   

def exitProgram():
    print("Exit button pressed!")
    win.destroy()

def goToPosition():
    print("demand of plate movement")
    motor_control.moveTo(positionScale.get())

def goToListPosition():
    print("demand of plate movement")
    angle = float(posList.get(ACTIVE))
    motor_control.moveTo(int(angle))
    positionScale.set(int(angle))

def setRefPosition():
    print("Set ref ")
    motor_control.setReference()

    

win.title("UHF TAG test setup - plate management V1.0")
win.geometry("800x400+0+0")


exitButton = Button(win, text = "Exit",  font = winFont , command = exitProgram, height = 2, width = 6)
exitButton.pack(side=BOTTOM)

setRefButton = Button(win, text = "Fix as reference",  font = winFont , command = setRefPosition, height = 2, width = 14)
setRefButton.pack(side=LEFT)


positionScale = Scale(win, from_=0, to=360, length =  400, font = winFont,  orient=HORIZONTAL)
positionScale.pack()
positionScale.set(motor_control.currPlatePosition)

setPosButton = Button(win, text = "Go Scale position",  font = winFont , command = goToPosition, height = 2, width = 14)
setPosButton.pack()

posList = Listbox(win)
posList.pack()

for item in ["0", "45", "90", "135","180"]:
    posList.insert(END, item)

#
# init list
posList.selection_set( first = 0 )

setPosListButton = Button(win, text = "Go to List position",  font = winFont , command = goToListPosition, height = 2, width = 14)
setPosListButton.pack()


#
# capture window events
win.mainloop()


#
# kill plate control terminal
control_terminal.terminate()

#
# kill  plate control thread
motor_control.terminate()

