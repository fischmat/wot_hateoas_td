from os.path import abspath, dirname

BCM = "BCM"

PUD_UP = "PULL UP"

IN = "IN"

def setmode(mode):
    print("GPIO mode set to " + str(mode))

def setup(gpio_num, mode, pull_up_down):
    print("Set GPIO %s to mode %s (PUD: %s)" % (gpio_num, mode, pull_up_down))

def input(gpio_num):
    try:
        return open(abspath(dirname(__file__) + "/../../%d.gpio" % gpio_num)).readline() == '1'
    except IOError:
        return False