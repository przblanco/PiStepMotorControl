""" Control of monopolar step motor 28BYJ-48

Description:
    This module implementa a class to control monopolar 28BYJ-48 step motor
    
Author:
    Pablo Rodriguez-2018
    
'""" 
#!/usr/bin/python
# Import required libraries
import sys
import time
import RPi.GPIO as GPIO
 
# Use BCM GPIO references
# instead of physical pin numbers
GPIO.setmode(GPIO.BCM)
 
# Define GPIO signals to use
# Physical pins 11,15,16,18
# GPIO17,GPIO22,GPIO23,GPIO24
StepPins = [17,22,23,24]
 
# Set all pins as output
for pin in StepPins:
  print("Setup pins")
  GPIO.setup(pin,GPIO.OUT)
  GPIO.output(pin, False)
 
# Define advanced sequence
# as shown in manufacturers datasheet

#half step mehotd
#Seq = [[1,0,0,1],
 #     [1,0,0,0],
   #  [1,1,0,0],
    # [0,1,0,0],
     #  [0,1,1,0],
      # [0,0,1,0],
      # [0,0,1,1],
      # [0,0,0,1]]

#step method
Seq = [[1,1,0,0],
           [0,1,1,0],
            [0,0, 1,1],
           [1,0,0,1]]

    
StepCount = len(Seq)
StepDir = 1 # Set to 1 or 2 for clockwise
                   # Set to -1 or -2 for anti-clockwise

Debug = 0 # set to 1 to print debug values 
 
# Read wait time from command line
if len(sys.argv)>1:
    WaitTime = int(sys.argv[1])/float(1000)
else:
    #max freq = 333HzzZ (333 steps per second) = <12s / turnz
    WaitTime = 3/float(1000)
 
# Initialise variables
StepCounter = 0
TotalStepCounter = 0
 
# Start main loop
while True:
    if Debug ==  1:
      print(StepCounter)
      print (Seq[StepCounter])

    for pin in range(0, 4):
        xpin = StepPins[pin]
        if Seq[StepCounter][pin]!=0:
            if Debug == 1:
                print(" Enable GPIO:",xpin)
            GPIO.output(xpin, True)
        else:
            GPIO.output(xpin, False)

    TotalStepCounter = TotalStepCounter + 1
    if TotalStepCounter % 100 == 0 and Debug == 1:
        print("TotalCounter:",TotalStepCounter)
        
    StepCounter += StepDir
    # If we reach the end of the sequence
    # start again
    
    if (StepCounter>=StepCount):
        StepCounter = 0
    if (StepCounter<0):
        StepCounter = StepCount+StepDir
    
    # Wait before moving on
    time.sleep(WaitTime)
