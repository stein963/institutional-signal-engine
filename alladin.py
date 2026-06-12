import random

class Aladdin:
    def __init__(self):
        self.name = "Aladdin"
        self.home = "Agrabah"
        self.friends = ["Abu", "Genie", "Jasmine"]
        self.has_lamp = True

    def greet(self):
        print(f"Hello! I am {self.name} from the streets of {self.home}.")

    def call_friend(self):
        friend = random.choice(self.friends)
        print(f"Hey {friend}, come help me out!")

    def rub_lamp(self):
        if self.has_lamp:
            print("✨ BOOM! The Genie appears! 'You have three wishes, Master!' ✨")
        else:
            print("Oh no, I lost the lamp!")

# --- This is how you "turn on" Aladdin ---
my_aladdin = Aladdin()

my_aladdin.greet()
my_aladdin.call_friend()
my_aladdin.rub_lamp()