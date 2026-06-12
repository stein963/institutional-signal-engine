import os
import time
import math

def generate_donut():
    A = 0
    B = 0
    # Precompute sines and cosines for speed
    while True:
        z = [0] * 1760
        b = [' '] * 1760
        
        j = 0
        while j < 6.28:
            j += 0.07
            i = 0
            while i < 6.28:
                i += 0.02
                
                sinA = math.sin(A)
                cosA = math.cos(A)
                sinB = math.sin(B)
                cosB = math.cos(B)
                sini = math.sin(i)
                cosi = math.cos(i)
                sinj = math.sin(j)
                cosj = math.cos(j)
                
                h = cosj + 2
                D = 1 / (sini * h * sinA + sinj * cosA + 5)
                t = sini * h * cosA - sinj * sinA
                
                # Projecting 3D to 2D
                x = int(40 + 30 * D * (cosi * h * cosB - t * sinB))
                y = int(12 + 15 * D * (cosi * h * sinB + t * cosB))
                o = int(x + 80 * y)
                N = int(8 * ((sinj * sinA - sini * cosj * cosA) * cosB - sini * cosj * sinA - sinj * cosA - cosi * cosj * sinB))
                
                if 22 > y > 0 and 80 > x > 0 and D > z[o]:
                    z[o] = D
                    b[o] = ".,-~:;=!*#$@"[N if N > 0 else 0]
        
        # Clear terminal and print frame
        print('\x1b[H', end='')
        for k in range(1761):
            print(b[k] if k % 80 else '\n', end='')
        
        A += 0.04
        B += 0.02
        time.sleep(0.01)

if __name__ == "__main__":
    # Clear screen initially
    os.system('cls' if os.name == 'nt' else 'clear')
    generate_donut()