import turtle
import time
import random

# --- Configuration ---
delay = 0.1
score = 0
high_score = 0

# --- Screen Setup ---
screen = turtle.Screen()
screen.title("Python Pro: Realistic Scale Edition")
screen.bgcolor("#0a0a0a") # Near total black
screen.setup(width=600, height=600)
screen.tracer(0) 

# --- Snake Head (Elongated with Eyes) ---
head = turtle.Turtle()
head.speed(0)
head.shape("square") # We stretch this into a snout
head.color("#228B22") # Forest Green
head.pencolor("#003300") # Dark Green Scale Border
head.shapesize(1.2, 1.6, 3) # (Width, Length, Border Thickness)
head.penup()
head.goto(0, 0)
head.direction = "stop"

# --- Snake Tongue ---
tongue = turtle.Turtle()
tongue.speed(0)
tongue.shape("triangle")
tongue.color("#FF4500") # Red-Orange
tongue.shapesize(0.2, 0.7)
tongue.penup()
tongue.hideturtle()

# --- Luminous Food ---
food = turtle.Turtle()
food.speed(0)
food.shape("circle")
food.color("#FFD700") 
food.shapesize(0.7, 0.7)
food.penup()
food.goto(0, 100)

segments = []

# --- Scoreboard ---
pen = turtle.Turtle()
pen.speed(0)
pen.color("white")
pen.penup()
pen.hideturtle()
pen.goto(0, 260)
pen.write("Earnings: $0  Best: $0", align="center", font=("Arial", 16, "bold"))

# --- Functions ---
def go_up():
    if head.direction != "down": head.direction = "up"
def go_down():
    if head.direction != "up": head.direction = "down"
def go_left():
    if head.direction != "right": head.direction = "left"
def go_right():
    if head.direction != "left": head.direction = "right"

def move():
    if head.direction == "up":
        head.setheading(90)
        head.sety(head.ycor() + 20)
    if head.direction == "down":
        head.setheading(270)
        head.sety(head.ycor() - 20)
    if head.direction == "left":
        head.setheading(180)
        head.setx(head.xcor() - 20)
    if head.direction == "right":
        head.setheading(0)
        head.setx(head.xcor() + 20)

def reset_game():
    global score
    time.sleep(1)
    head.goto(0, 0)
    head.direction = "stop"
    for segment in segments:
        segment.goto(1000, 1000)
    segments.clear()
    score = 0
    update_scoreboard()

def update_scoreboard():
    pen.clear()
    pen.write(f"Earnings: ${score}  Best: ${high_score}", align="center", font=("Arial", 16, "bold"))

# --- Control Bindings ---
screen.listen()
for key in ["w", "Up"]: screen.onkeypress(go_up, key)
for key in ["s", "Down"]: screen.onkeypress(go_down, key)
for key in ["a", "Left"]: screen.onkeypress(go_left, key)
for key in ["d", "Right"]: screen.onkeypress(go_right, key)

# --- Main Game Loop ---
while True:
    screen.update()

    # Border & Body Collision
    if abs(head.xcor()) > 290 or abs(head.ycor()) > 290:
        reset_game()
    
    for segment in segments:
        if segment.distance(head) < 20:
            reset_game()

    # Food Collision (The $5 Logic)
    if head.distance(food) < 20:
        # Move Food
        food.goto(random.randint(-270, 270), random.randint(-270, 270))
        
        # Tongue Flick Animation
        tongue.goto(head.xcor(), head.ycor())
        tongue.setheading(head.heading())
        tongue.forward(25)
        tongue.showturtle()
        
        # Add "Scale" Segment
        new_segment = turtle.Turtle()
        new_segment.speed(0)
        new_segment.shape("square")
        # Creating a 'Patch' effect with random greens/browns
        base_color = random.choice(["#2E8B57", "#3CB371", "#556B2F"])
        new_segment.color(base_color)
        new_segment.pencolor("#1a3300") # Scale outline
        new_segment.shapesize(0.9, 0.9, 2) # Slightly smaller than head for tapering
        new_segment.penup()
        segments.append(new_segment)

        score += 5
        if score > high_score: high_score = score
        update_scoreboard()
        
        screen.update()
        time.sleep(0.05) # Brief pause for tongue visibility
        tongue.hideturtle()

    # Move segments
    for index in range(len(segments)-1, 0, -1):
        segments[index].goto(segments[index-1].xcor(), segments[index-1].ycor())

    if len(segments) > 0:
        segments[0].goto(head.xcor(), head.ycor())

    move()
    time.sleep(delay)