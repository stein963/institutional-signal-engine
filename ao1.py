def temp(t):
    if(t<=15 and t>0):
        i="COLD"
    elif(t>15 and t<=25):
        i="WARM"
    elif(t>25 and t<=40):
         i="HOT"
    else:
        i="YOUR ARE NYAMA CHOMA"
    return i
def farh(t):
    f=((9/5)*t)+32
    print(f"temperature in farhnheit is: {f}")
get_t=float(input("pleaseinput value of temperature: "))
farh(get_t)
j=temp(get_t)
print(j)                