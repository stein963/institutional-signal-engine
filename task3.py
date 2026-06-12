# Task 3: Button Counter with LED
# Button → GPIO 17 (internal pull-up)
# LED    → GPIO 2

from machine import Pin
import time

button = Pin(17, Pin.IN, Pin.PULL_UP)
led = Pin(2, Pin.OUT)

count = 0
button_was_pressed = False  # tracks previous state

while True:
    button_state = button.value()  # LOW (0) when pressed (pull-up)

    if button_state == 0 and not button_was_pressed:
        # Button just pressed
        led.on()
        count += 1
        print(f"Button pressed! Total count: {count}")
        button_was_pressed = True
        time.sleep_ms(200)  # debounce delay

    elif button_state == 1 and button_was_pressed:
        # Button released
        led.off()
        button_was_pressed = False

    time.sleep_ms(10)  # small polling delay