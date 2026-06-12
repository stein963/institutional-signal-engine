#collins,janabi,austine,kaisers
# Task 2: FizzBuzz Function

def fizzbuzz(limit):
    for i in range(1, limit + 1):
        if i % 3 == 0 and i % 5 == 0:
            print("FizzBuzz")
        elif i % 3 == 0:
            print("Fizz")
        elif i % 5 == 0:
            print("Buzz")
        else:
            print(i)

# Call the function with a limit of 20
fizzbuzz(20)