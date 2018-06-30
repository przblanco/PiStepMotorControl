""" Control of bipolar step motor using 8825 driver

Description:
    This module implements a class to control bipolar step motor using 8825 driver
    Also some samples have been implemented
       "class to implement TPC/IP remote control of the motor"
        (the user can connect with hyperterminal or telnet and control trhe motor through a remote menu
       "GUI to APP"

       to be used as idependent APP drv8825RunMain must be set to True,  by doeing this the
       samples are run
        
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

#
# set to True to run the module main APP
drv8825RunMain = False

def lostStep(channel):
    print("lostStep" )


class stepMotorDriver8825(threading.Thread):
    """ Class to control  step motor movements using a 8825 driver """
    #
    # defult tag plate position respect the reader (the attack angle from the TAG)
    DEFAULT_PLATE_POSITION = 90

    #
    # DRV8825 microstep configurations
    MICROSTEP_RELATION_1 = 0
    MICROSTEP_RELATION_2  = 1
    MICROSTEP_RELATION_4  = 2
    MICROSTEP_RELATION_8  = 3
    MICROSTEP_RELATION_16  = 4
    MICROSTEP_RELATION_32  = 5
    
    #
    # holds the pins to use to set microstep configuration of DRV8825
    MICROSTEP_PINS  = [14,15,18]

    #
    # holds the values to use for each microstep configuration of the DRV8825
    # as well as the  step mode: full-step, 1/2-step, 1/4-step, 1/8-step, 1/16-step, 1/32
    MICROSTEP_PINS_SETUP  = [[0,0,0,1,100],[0,0,1,2,100*2],[0,1,0,4,100*4],[0,1,1,8,100*8],[1,0,0,16,100*16],[1,0,1,32,100*32],[1,1,0,32,100*32],[1,1,1,32,100*32]]

    #
    # microstrep relation
    currMicrostepCfg =   None
   
    
    #
    # how many degress in each motor step
    # i.e: stepResolution = 360 / (200) when relsoltion is full
    stepResolution = None
        
    #
    # step motor frequency in pigiod   17        16     15      14      13      12  11  10      9
    #                                                   (8000  4000  2000 1600 1000  800  500  400  320)
    #                                                       8           7       6       5       4       3       2   1       0
    #                                                   (250       200    160   100    80     50     40  20     10 )
    stepMotorFreq =  200
    
        
    #
    # back direction
    MOVE_BACKWARD = 0
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
    # pint to count steps
    stepCountPin = 4

    #
    # if the plate is currently in movement, if it is, we can not demand a new movement until the current is ended
    inMovement = False

    #
    # we are looking for reference
    lookingForReference = False

    #
    # we are moven to a predefined possition
    moveToDemanded = False

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

    def stepDetection(self,g,b,t):
        """ on each step detected we decrement the number of pending movements """
        self.pendingMovements = self.pendingMovements - 1
        if (self.updatePosition):
            #
            # update curr plate position
            if (self.moveDirection == self.MOVE_BACKWARD):
                self.currPlatePosition = self.currPlatePosition - self.stepResolution
            else:
                self.currPlatePosition = self.currPlatePosition + self.stepResolution
        
    
    #
    # on construction the thread starts
    def __init__(self):
        self.loop_active = True
        threading.Thread.__init__(self)
        self.setupPins()
        self.start()

    def setMicrostepCfg(self,microstepCfg):
        """ set the DRV8825 microstep configuration"""
        if (not self.inMovement):
            #
            # check it  is a valid configuration
            if (microstepCfg >= self.MICROSTEP_RELATION_1 and microstepCfg <= self.MICROSTEP_RELATION_32):

                self.currMicrostepCfg =  microstepCfg
                #
                # set pins values
                GPIO.output(self.MICROSTEP_PINS[0],self.MICROSTEP_PINS_SETUP[self.currMicrostepCfg][0])
                GPIO.output(self.MICROSTEP_PINS[1],self.MICROSTEP_PINS_SETUP[self.currMicrostepCfg][1])
                GPIO.output(self.MICROSTEP_PINS[2],self.MICROSTEP_PINS_SETUP[self.currMicrostepCfg][2])

                #
                # adjust resolution (numer of sdegres in each step)
                self.stepResolution= 360 / (200 *  self.MICROSTEP_PINS_SETUP[self.currMicrostepCfg][3])

                #
                # set frequency to defult value for the resolution
                self.stepMotorFreq = self.MICROSTEP_PINS_SETUP[self.currMicrostepCfg][4]
    

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
        self.gpioControl.set_PWM_frequency(self.stepPin,self.stepMotorFreq)
        #
        # step detection
        GPIO.setup(self.stepCountPin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        self.gpioControl.callback(self.stepCountPin,pigpio.RISING_EDGE,self.stepDetection)
        
        GPIO.setup(self.dirPin,GPIO.OUT)
        GPIO.output(self.dirPin,self.moveDirection)

        #
        # set reference pin as input
        GPIO.setup(self.referencePIN,GPIO.IN,GPIO.PUD_DOWN)

        #
        # setup microstep control pins as output
        GPIO.setup(self.MICROSTEP_PINS[0],GPIO.OUT)
        GPIO.setup(self.MICROSTEP_PINS[1],GPIO.OUT)
        GPIO.setup(self.MICROSTEP_PINS[2],GPIO.OUT)

        #
        # by default max resolution (more steps and minimum vibration
        self.setMicrostepCfg(self.MICROSTEP_RELATION_32)

    
    def lookForReference(self):
        """look for the plate initial posiition (DEFAULT_PLATE_POSITION)"""
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

    def getCurrRPM(self):
        """ return curr RPM of the motor """
        return (self.stepResolution*self.stepMotorFreq*60)/360           

    def getCurrPlatePosition(self):
        """ return curr plate position """
        return self.currPlatePosition

    def getCurrMicrostepCfg(self):
        """ return curr microstep configuration """
        return self.currMicrostepCfg

    def getCurrParams(self):
        """ return curr plate position and speed in string"""
        return "Pos: " + str(int( self.currPlatePosition)) + " --- Microstep : " + str(self.getCurrMicrostepCfg()) + "  --- Speed (RPM): " + str(self.getCurrRPM()) + " --- Freq: " + str(self.stepMotorFreq) + " --- Dir: "+str(self.moveDirection)

    def startMovement(self):
        """ just starts moving the motor with current parameters"""
        if (not  self.inMovement):
            print("start movement demanded")
            self.inMovement = True
            #
            # update direction before start movement
            GPIO.output(self.dirPin,self.moveDirection)
            #
            # update motor frequency
            self.gpioControl.set_PWM_frequency(self.stepPin,self.stepMotorFreq)
            #
            # start pulses on step pin
            self.gpioControl.set_PWM_dutycycle(self.stepPin,128)
            
    def stopMovement(self):
        """ just stop moving the motor"""
        if (self.inMovement):
            self.gpioControl.set_PWM_dutycycle(self.stepPin,0)
            self.inMovement = False
    
    def  moveTo(self,position):
        """ start movement of plate to demanded position"""
        #
        # by default we return that the movement is not possible
        retVal = False
        if (not  self.inMovement):
            retVal = True
            #
            # check if we have to move (if we are more than one step away of the desired position
            if (abs(position - self.currPlatePosition) >= self.stepResolution):
                #
                #   how far how we have to move and in what direction
                self.pendingMovements =  int(abs(position - self.currPlatePosition) /self.stepResolution)
                
                if (self.currPlatePosition >  position):
                    self.moveDirection = self.MOVE_BACKWARD
                else:
                    self.moveDirection = self.MOVE_FORWARD
                self.updatePosition = True
                self.moveToDemanded = True
                self.startMovement()
                
                    
        return retVal

    def  advanceOneDegree(self):
        """ moves one degree or the minimum current resolution """
        destination = self.currPlatePosition + 1
        
        if (self.stepResolution > 1):
            destination = self.currPlatePosition + self.stepResolution + 1

        self.moveTo(destination)

    def setReference(self):
        """ marks curr possition as reference and stop movement """
        self.stopMovement()
        self.currPlatePosition = self.DEFAULT_PLATE_POSITION
        print("reference found")
        self.lookingForReference = False

    def switchDirection(self):
        """ change current motor direction """
        if (self.moveDirection == self.MOVE_FORWARD):
            self.moveDirection = self.MOVE_BACKWARD
        else:
            self.moveDirection = self.MOVE_FORWARD
        #
        # if we are in movement stop and re-start
        if (self.inMovement):
            self.stopMovement()
            time.sleep(0.1)
            self.startMovement()
            
    def changeSpeed(self, newRPM):
        """ change the motor frequency according to the new RPM value """
        self.stepMotorFreq = int(round((360 * newRPM)/(self.stepResolution*60)))
        #
        # if we are in movement stop and re-start
        if (self.inMovement):
            self.stopMovement()
            time.sleep(0.01)
            self.startMovement()


    #
    # infinite loop of the thread
    def run(self):
        count = 0
        while self.loop_active:
            time.sleep(0.0001)
       
            #
            # the motor is moving  due to lookingForReference or moveTo demand
            if (self.inMovement):
                if (self.lookingForReference):
                    if (GPIO.input(self.referencePIN) == 1):
                        #
                        # stop pulses on step pin
                        self.stopMovement()
                        self.currPlatePosition = self.DEFAULT_PLATE_POSITION
                        print("reference found")
                        self.lookingForReference = False
                else:
                    if (self.moveToDemanded):
                        if (self.pendingMovements <= 0):
                            self.stopMovement()
                            self.updatePosition = False
                            self.moveToDemanded = False
                            
                        count = count + 1
                        if (count % 100 == 0):
                            if (appDebug):
                                print("curr position:", int(self.currPlatePosition) , " - In movement: ", self.inMovement, " - Pending steps: ", self.pendingMovements)

    #
    # collaboative method to terminale
    def terminate(self):
        #
        # stop pulses on step pin and close connection
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
            self.sock.send("                 R.-  Search reference\r\n".encode())
            self.sock.send("                 A.-  Advance One step\r\n".encode())
            self.sock.send("\r\n".encode())
            self.sock.send("                 S.-  Start\r\n".encode())
            self.sock.send("                 H.-  Halt\r\n".encode())
            self.sock.send("\r\n".encode())
            self.sock.send("                 D.-  Change Direction\r\n".encode())
            self.sock.send("                 +.-  Increase Speed \r\n".encode())
            self.sock.send("                  -.-  Decrease Speed \r\n".encode())
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
                    if (data[0] == "R" or data[0] == "r"):
                        self.motorControl.lookForReference()
                    if (data[0] == "A" or data[0] == "a"):
                        self.motorControl.advanceOneDegree()
                    if (data[0] == "S" or data[0] == "s"):
                        self.motorControl.startMovement()
                    if (data[0] == "H" or data[0] == "h"):
                        self.motorControl.stopMovement()
                    if (data[0] == "D" or data[0] == "d"):
                        self.motorControl.switchDirection()
                    if (data[0] == "+"):
                        #
                        # maximun of 44-45 RPM
                        if (self.motorControl.getCurrRPM() < 44):
                            newRPM = int(round(self.motorControl.getCurrRPM())) + 1
                            self.motorControl.changeSpeed(newRPM)
                    if (data[0] == "-"):
                        #
                        # minimum of 1-2 RPM
                        if (self.motorControl.getCurrRPM() > 2):
                            newRPM = int(round(self.motorControl.getCurrRPM())) - 1
                            self.motorControl.changeSpeed(newRPM)
                    
                        

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
    
    client = None
    motorControl = None
    TCP_IP = '0.0.0.0'
    TCP_PORT = 12345
    BUFFER_SIZE = 1024  # Normally 1024, but we want fast response
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def __init__(self, motorControl):
        self.s.bind((self.TCP_IP, self.TCP_PORT))
        self.s.listen(1)
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
# if we are not using it as a library
if (drv8825RunMain):
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

