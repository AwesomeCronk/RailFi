from machine import Pin, PWM
io10 = Pin(10, Pin.OUT, Pin.PULL_DOWN, value=0)
io27 = Pin(27, Pin.OUT, Pin.PULL_DOWN, value=0)
m0 = PWM(io27, duty=0, freq=500)
m1 = PWM(io10, duty=0, freq=500)
