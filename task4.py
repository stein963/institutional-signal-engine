# Task 4: Potentiometer controls LED brightness via PWM
# Potentiometer → GPIO 26 (ADC)
# LED           → GPIO 2  (PWM)

from machine import Pin, ADC, PWM
import time

# ADC setup — attenuation set for 0–3.3V range
adc = ADC(Pin(26))
adc.atten(ADC.ATTN_11DB)   # allows reading up to 3.3V
adc.width(ADC.WIDTH_12BIT) # 12-bit resolution: 0–4095

# PWM setup on LED pin
led_pwm = PWM(Pin(2), freq=1000)  # 1kHz frequency

while True:
    pot_value = adc.read()          # read 0–4095
    
    # Map 0–4095 (ADC) → 0–1023 (PWM duty cycle)
    duty = int(pot_value * 1023 / 4095)
    
    led_pwm.duty(duty)
    
    print(f"ADC: {pot_value}  |  PWM Duty: {duty}")
    time.sleep_ms(100)