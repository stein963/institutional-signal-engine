#collins ,kaiser,austine,janabi
# Task 5: Score to Letter Grade

score = float(input("Enter your numerical score (0-100): "))

if score < 0 or score > 100:
    print("Invalid score. Please enter a value between 0 and 100.")
elif score >= 90:
    grade = "A"
elif score >= 80:
    grade = "B"
elif score >= 70:
    grade = "C"
elif score >= 60:
    grade = "D"
else:
    grade = "F"

if 0 <= score <= 100:
    print(f"Score: {score}")
    print(f"Grade: {grade}")