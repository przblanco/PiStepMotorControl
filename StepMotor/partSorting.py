""" Implementation of a  APP to accept and reject part based on step motor driver DRV8825

Description:
    The behavior of the station is managed through a TCP-IP connection on port 12345

    * When the sation starts it moves the platform until "origin" is found
    * The PC can issue the command "?" to chek if a part is present, the station will answer
    with "Y<cr><lf>" or "N<cr><lf>" depending if a part is present or not
    * The PC checks the parts:
       * if part is accepted the control PC sends a "A" message, the station moves
       the motor in ACEPTATION_DIR until the platform returns to "origin". In this moment the station
       returns the mesage "OK<cr><lf>"
       * if part is rejected the control PC sends a "R" message, the station moves
       the motor in REJECTION_DIR until the platform returns to "origin". In this moment the station
       returns the mesage "OK<cr><lf>"
    * Other messages:
       * "D"  to change the part aceptation direction, the station performs a 360 round and answers with
       "OK<cr><fl>"
       * "+": increments speed, it is answered with "OK<cr><lf>"
       * "-": increments speed, it is answered with "OK<cr><lf>"
       * "0"  Set microstep full
          "1" Set microstep 1/2
          "2" Set microstep 1/4
          "3" Set resolution 1/8
          "4" Set microstep 1/16
          "5" Set microstep 1/32

          All are anwered with "OK<cr><lf>"
          
       * "S" to order the station to save the configuration, the answer is "OK<cr><lf>"
       * "H"  A menu with the opions and current cfg is shown
       * "C" to close the connection

       Incorrect commands are answered with "KO<cr><lf>"
        
Author:
    Pablo Rodriguez-2018-06-30
    
'""" 
#!/usr/bin/python
# Import required libraries

import time
import sys
import RPi.GPIO as GPIO
import  socket
import threading
from  stepMotorDRV8825 import stepMotorDriver8825 

class partSortingTerminalConnection(threading.Thread):
    """ Connection instance from TCP/IP terminal to control de motor """
    loop_active = True
    sock = None
    motorControl = None
    inOrigin = None
    partDetectionPin = None
    
    
    #
    # direction accept and reject parts
    acceptDirection = None
    rejectDirection = None
    

    def showMenu(self):
        try:
            self.sock.send("\r\n".encode())
            self.sock.send("=================  Plate control menu ===============\r\n".encode())
            self.sock.send("\r\n".encode())
            self.sock.send("                 A.-  Accept part\r\n".encode())
            self.sock.send("                 R.-  Reject part\r\n".encode())
            self.sock.send("                 E.-  End current movement\r\n".encode())
            self.sock.send("                 ?.-  Is part present or not\r\n".encode())
            self.sock.send("\r\n".encode())
            self.sock.send("                 D.-  Change Direction of part aceptation\r\n".encode())
            self.sock.send("                 +.-  Increase Speed \r\n".encode())
            self.sock.send("                  -.-  Decrease Speed \r\n".encode())
            self.sock.send("                  S.-  Record configuration \r\n".encode())
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


    def detectedOrigin(self,channel):
        self.inOrigin  = True
      

    
    def __init__(self,s=None, motorControl = None, acceptDirection = None):
        self.sock = s
        self.sock.settimeout(0.001) # timeout for listening
        self.motorControl = motorControl
        self.acceptDirection = acceptDirection
        #
        # setup de part detection pin
        self.partDetectionPin = 12
        GPIO.setup(self.partDetectionPin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        
        #
        # calculate reject direction in base to accept direction value
        self.rejectDirection = 1
        if (acceptDirection == 1):
            self.rejectDirection = 0

        self.inOrigin = False
        
        #
        # capture motor_control referencePin RISING events to start/stop the motor
        GPIO.add_event_detect(motorControl.referencePIN,GPIO.RISING,callback=self.detectedOrigin)
    
        
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
    
    def waitOrigin(self):
        endDemmandArrives = False
        """ waits until origin is found """
        #
        # wait 200 ms
        time.sleep(0.2)
        self.inOrigin = False

        while (not self.inOrigin) and not endDemmandArrives:
            #
            # if something is received we stop
            try:
                data = self.sock.recv(1024).decode()
                if (data[0] == "E" or data[0] == "e"):       
                    endDemmandArrives = True
            except socket.timeout:
                pass
            except:
                print ("unhandle exception in connection")
                self.terminate()
            
    def isPartPresent(self):
        """ check if a part is present a small filter of 0.2 s is used"""
        retVal = False

        if (GPIO.input(self.partDetectionPin) == 1):
            time.sleep(0.2)
            if (GPIO.input(self.partDetectionPin) == 1):
                retVal = True

        return retVal

    def searchOrigin(self):
        """ similates a rejection to search the origin"""
        self.motorControl.moveDirection = int(self.rejectDirection)
        self.motorControl.startMovement()
        self.waitOrigin()
        #
        # after the origin is found we clean PC input buffer
        try:
            data = self.sock.recv(1024).decode()
        except socket.timeout:
            pass
        except:
            print ("unhandle exception in connection")
            self.terminate()
   
    def run(self):
        #
        # if an answer has to be sent back
        sendAnswer = False
        #
        # search origin
        #self.searchOrigin()
        
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
                    answerOK = False
                    sendAnswer = True
                    
                    if (data[0] == "C" or data[0] == "c"):
                       self.terminate()
                       #
                       # the connection sockect is closed,we can't answer
                       sendAnswer = False
                       
                       
                    if (data[0] == "S" or data[0] == "s"):
                        try:
                            currRPM = int(self.motorControl.getCurrRPM())
                            currMicrostepCfg = self.motorControl.getCurrMicrostepCfg()
                            
                            cfgFile = open(CFG_FILE_NAME, "w")
                            cfgFile.write(str(self.acceptDirection)+"\n")
                            cfgFile.write(str(currRPM)+"\n")
                            cfgFile.write(str(currMicrostepCfg)+"\n")
                           
                            cfgFile.close()

                            answerOK = True
                            
                        except:
                            print("Imposible to save configuration file!")

                    #
                    # part is accepted
                    if (data[0] == "A" or data[0] == "a"):
                        self.motorControl.moveDirection = int(self.acceptDirection)
                        self.motorControl.startMovement()
                        self.waitOrigin()
                        self.motorControl.stopMovement()
                        answerOK = True

                    #
                    # reject movement
                    if (data[0] == "R" or data[0] == "r"):
                        self.motorControl.moveDirection = int(self.rejectDirection)
                        self.motorControl.startMovement()
                        self.waitOrigin()
                        self.motorControl.stopMovement()
                        answerOK = True

                    #
                    # reject movement
                    if (data[0] == "?"):
                        if (self.isPartPresent()):
                            self.sock.send("Y\r\n".encode())
                            sendAnswer = False
                        else:
                            self.sock.send("N\r\n".encode())
                            sendAnswer = False

                    #
                    # switch acceptance direction
                    if (data[0] == "D" or data[0] == "d"):
                        if (self.acceptDirection == 1):
                            self.acceptDirection = 0
                            self.rejectDirection = 1
                        else:
                            self.acceptDirection = 1
                            self.rejectDirection = 0
                        answerOK = True

                      #
                      # changes on  microstep relation
                    if (data[0] == "0"):
                        self.motorControl.setMicrostepCfg(self.motorControl.MICROSTEP_RELATION_1)
                        answerOK = True
                        
                    if (data[0] == "1"):
                        self.motorControl.setMicrostepCfg(self.motorControl.MICROSTEP_RELATION_2)
                        answerOK = True
                        
                    if (data[0] == "2"):
                        self.motorControl.setMicrostepCfg(self.motorControl.MICROSTEP_RELATION_4)
                        answerOK = True
                        
                    if (data[0] == "3"):
                        self.motorControl.setMicrostepCfg(self.motorControl.MICROSTEP_RELATION_8)
                        answerOK = True
                        
                    if (data[0] == "4"):
                        self.motorControl.setMicrostepCfg(self.motorControl.MICROSTEP_RELATION_16)
                        answerOK = True
                        
                    if (data[0] == "5"):
                        self.motorControl.setMicrostepCfg(self.motorControl.MICROSTEP_RELATION_32)
                        answerOK = True
                        
                    #
                    # speed up and down
                    if (data[0] == "+"):
                        #
                        # maximun of 44-45 RPM
                        if (self.motorControl.getCurrRPM() < 88):
                            newRPM = int(round(self.motorControl.getCurrRPM())) + 1
                            self.motorControl.changeSpeed(newRPM)
                        answerOK = True
                        
                    if (data[0] == "-"):
                        #
                        # minimum of 1-2 RPM
                        if (self.motorControl.getCurrRPM() > 2):
                            newRPM = int(round(self.motorControl.getCurrRPM())) - 1
                            self.motorControl.changeSpeed(newRPM)
                        answerOK = True

                    #
                    # show help menu
                    if (data[0] == "H" or data[0] == "h"):
                        self.showMenu();
                        answerOK = True

                    #
                    # in case an answer is needed
                    if (sendAnswer):
                        sendAnswer = False
                        print ("sending answer: ", answerOK)
                        if (answerOK):
                            self.sock.send("OK\r\n".encode())
                        else:
                            self.sock.send("KO\r\n".encode())
                        
            
    #
    # collaboative method to terminale
    def terminate(self):
        self.loop_active = False
        try:
            GPIO.remove_event_detect(self.motorControl.referencePIN)
            self.sock.send("\r\n".encode())
            self.sock.send("Connection Closed\r\n".encode())
            self.sock.send("\r\n".encode())
            self.closeSocket()
        except:
            print ("Unhandle terminating Connection")
            

class partSortingTerminalServer(threading.Thread):
    """ TCP/IP socket server class that admit connections of 12345
          on connection a partSortingTerminalConnection is created to
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
    #
    # part aceptance rotation direction
    acceptDirection = None

    def isActive(self):
        return self.loop_active
    

    def __init__(self, motorControl = None, acceptDirection = None):
        self.motorControl= motorControl
        self.loop_active = True
        self.acceptDirection = acceptDirection
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
                self.s.settimeout(1) # timeout for listening
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
                #
                # if a previous connection exits, drop it
                if (not self.client == None):
                    print ("Finishing previous clonnection...")
                    self.client.terminate()
                    time.sleep(1)
                    self.client = None
                    
                self.client = partSortingTerminalConnection(conn,self.motorControl, self.acceptDirection)                   
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
CFG_FILE_NAME = "partSorting.cfg"

#
# create the plate control thread 
motor_control = stepMotorDriver8825()

#
# direction to accept the parts
acceptDirection = None

#
# load ans set configuration
try:
    cfgFile = open(CFG_FILE_NAME, "r")
    acceptDirection = cfgFile.readline()
    speedRMP = cfgFile.readline()
    microstripCfg = cfgFile.readline()
    cfgFile.close()

    motor_control.moveDirection = int(acceptDirection)
    motor_control.setMicrostepCfg(int(microstripCfg))
    motor_control.changeSpeed(int(speedRMP))
except:
    print("imposible to load cfg file, using defaults")
    acceptDirection = 1
    

def helicopterStartStop(channel):
    """ start or stop helicopter depending on current status"""
    if (motor_control.inMovement):
        motor_control.stopMovement()
    else:
        motor_control.startMovement()

#
# capture motor_control referencePin RISING events to start/stop the motor
#GPIO.add_event_detect(motor_control.referencePIN,GPIO.RISING,callback=helicopterStartStop)

#
# create TCP-IP server to build remote control connections
control_terminal = partSortingTerminalServer(motor_control,int(acceptDirection))


while (control_terminal.isActive()):
    time.sleep(0.5)

#
# kill plate control terminal
control_terminal.terminate()

#
# kill  plate control thread
motor_control.terminate()

