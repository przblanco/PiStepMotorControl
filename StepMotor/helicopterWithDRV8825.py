""" Implementation of helicopter APP based on step motor driver DRV8825

Description:
    This module implements a class to manage a helicopter station based on DRV8825
    
    The behavior of the moror can be managed by connection a TCP-IP server socked that is at the 12345  port
        
Author:
    Pablo Rodriguez-2018-06-16
    
'""" 
#!/usr/bin/python
# Import required libraries

import time
import sys
import RPi.GPIO as GPIO
import  socket
import threading
from  stepMotorDRV8825 import stepMotorDriver8825 

class helicopterTerminalConnection(threading.Thread):
    """ Connection instance from TCP/IP terminal to control de motor """
    loop_active = True
    sock = None
    motorControl = None

    def showMenu(self):
        try:
            self.sock.send("\r\n".encode())
            self.sock.send("=================  Plate control menu ===============\r\n".encode())
            self.sock.send("\r\n".encode())
            self.sock.send("                 S.-  Start\r\n".encode())
            self.sock.send("                 H.-  Halt\r\n".encode())
            self.sock.send("\r\n".encode())
            self.sock.send("                 D.-  Change Direction\r\n".encode())
            self.sock.send("                 +.-  Increase Speed \r\n".encode())
            self.sock.send("                  -.-  Decrease Speed \r\n".encode())
            self.sock.send("                  R.-  Record configuration \r\n".encode())
            self.sock.send("\r\n".encode())
            self.sock.send("                 0.- Set microstep full\r\n".encode())
            self.sock.send("                 1.- Set microstep 1/2\r\n".encode())
            self.sock.send("                 2.- Set microstep 1/4\r\n".encode())
            self.sock.send("                 3.- Set resolution 1/8\r\n".encode())
            self.sock.send("                 4.- Set microstep 1/16\r\n".encode())
            self.sock.send("                 5.- Set microstep 1/32\r\n".encode())
            self.sock.send("\r\n".encode())
            self.sock.send("                 C.-  Close connection\r\n".encode())
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
                    if (data[0] == "C" or data[0] == "c"):
                       self.terminate()
                    if (data[0] == "R" or data[0] == "r"):
                        try:
                            currRPM = int(self.motorControl.getCurrRPM())
                            currDirection = self.motorControl.moveDirection
                            currMicrostepCfg = self.motorControl.getCurrMicrostepCfg()
                            
                            cfgFile = open(CFG_FILE_NAME, "w")
                            cfgFile.write(str(currDirection)+"\n")
                            cfgFile.write(str(currRPM)+"\n")
                            cfgFile.write(str(currMicrostepCfg)+"\n")
                           
                            cfgFile.close()
                        except:
                            print("Imposible to save configuration file!")

                    if (data[0] == "A" or data[0] == "a"):
                        self.motorControl.advanceOneDegree()
                    if (data[0] == "S" or data[0] == "s"):
                        self.motorControl.startMovement()
                    if (data[0] == "H" or data[0] == "h"):
                        self.motorControl.stopMovement()
                    if (data[0] == "D" or data[0] == "d"):
                        self.motorControl.switchDirection()

                    if (data[0] == "0"):
                        self.motorControl.setMicrostepCfg(self.motorControl.MICROSTEP_RELATION_1)
                    if (data[0] == "1"):
                        self.motorControl.setMicrostepCfg(self.motorControl.MICROSTEP_RELATION_2)
                    if (data[0] == "2"):
                        self.motorControl.setMicrostepCfg(self.motorControl.MICROSTEP_RELATION_4)
                    if (data[0] == "3"):
                        self.motorControl.setMicrostepCfg(self.motorControl.MICROSTEP_RELATION_8)
                    if (data[0] == "4"):
                        self.motorControl.setMicrostepCfg(self.motorControl.MICROSTEP_RELATION_16)
                    if (data[0] == "5"):
                        self.motorControl.setMicrostepCfg(self.motorControl.MICROSTEP_RELATION_32)
                        
                        
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
            

class helicopterTerminalServer(threading.Thread):
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

    def isActive(self):
        return self.loop_active
    

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
        print("Wating client ...")
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
                self.client = helicopterTerminalConnection(conn,self.motorControl)
                   
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

""" *****************************  MAIN APP *******************************************  """
CFG_FILE_NAME = "helicopter.cfg"

#
# create the plate control thread 
motor_control = stepMotorDriver8825()

#
# load ans set configuration
try:
    cfgFile = open(CFG_FILE_NAME, "r")
    direction = cfgFile.readline()
    speedRMP = cfgFile.readline()
    microstripCfg = cfgFile.readline()
    cfgFile.close()

    motor_control.moveDirection = int(direction)
    motor_control.changeSpeed(int(speedRMP))
    motor_control.setMicrostepCfg(int(microstripCfg))
except:
    print("imposible to load cfg file, using defaults")
    

def helicopterStartStop(channel):
    """ start or stop helicopter depending on current status"""
    if (motor_control.inMovement):
        motor_control.stopMovement()
    else:
        motor_control.startMovement()

#
# capture motor_control referencePin RISING events to start/stop the motor
GPIO.add_event_detect(motor_control.referencePIN,GPIO.RISING,callback=helicopterStartStop)

#
# create TCP-IP server to build remote control connections
control_terminal = helicopterTerminalServer(motor_control)


while (control_terminal.isActive()):
    time.sleep(0.5)

#
# kill plate control terminal
control_terminal.terminate()

#
# kill  plate control thread
motor_control.terminate()

