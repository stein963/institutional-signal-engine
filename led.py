from machine import Pin, I2C
import ssd1306
import time

# Create the connection (I2C)
# D1 is usually SCL (Pin 5), D2 is usually SDA (Pin 4)
i2c = I2C(0, scl=Pin(5), sda=Pin(4))

# Try to start the screen
try:
    oled = ssd1306.SSD1306_I2C(128, 64, i2c)
    
    while True:
        oled.fill(0) # Clear screen
        oled.text("SCREEN ACTIVE!", 0, 0)
        oled.text("ESP32 Connected", 0, 20)
        oled.show()
        time.sleep(1)
        oled.invert(True)
        time.sleep(1)
        oled.invert(False)
        
except Exception as e:
    print("Screen not found. Check your wiring!")
    print("Error details:", e)