import sys
import logging
import time
import tipiports
import RPi.GPIO as GPIO

logger = logging.getLogger(__name__)


class TipiPorts(object):
    def __init__(self):
        logger.info("Using libtipi wiringPi GPIO")
        tipiports.initGpio()
        self.setRD(0)
        self.setRC(0)
        logger.info("GPIO initialized.")

    # Read TI_DATA
    def getTD(self):
        return tipiports.getTD()

    # Read TI_CONTROL
    def getTC(self):
        return tipiports.getTC()

    # Write RPI_DATA
    def setRD(self, value):
        tipiports.setRD(value)

    # Write RPI_CONTROL
    def setRC(self, value):
        tipiports.setRC(value)

    # Use this method to make sure we only
    @staticmethod
    def getInstance():
        return singleton


singleton = TipiPorts()

if __name__ == "__main__":
    singleton.setRC(0x55)
    singleton.setRD(0xAA)
    print("test set M5FF9 = 0x55, M5FFB = 0xAA")
    while True:
        print("M5FFD = " + hex(singleton.getTC()) + " M5FFF = " + hex(singleton.getTD()))
        time.sleep(5)
