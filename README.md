# PiStepMotorControl

Control of NEMA 17 step motor using 8825 driver developed in PYHTON for RASPBERRY PI

The control class uses pigpio to generate an accurated square signal. Due to this, pigiod have to running on the PI. (sudo pigiod)

A TCP-IP service has been developed to remotely control de motor movement via telnet on the port 12345.
