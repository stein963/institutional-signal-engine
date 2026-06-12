#collins,kaiser,janabi,austine
#celsius to fahrenheit
celsius=float(input("enter temperature celsius:"))
fahrenheit=(celsius*9/5)+32
print(f"{celsius}degrees is {fahrenheit:.2f}degrees fahrenheit")
if fahrenheit>100:
    print("warning: high temperature")
else:
    print("temperature normal")