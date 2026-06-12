import flet as ft
import requests
import threading
import time

# --- THE TERMINAL ENGINE ---
class MacroFriend:
    def __init__(self):
        self.news = [
            "Initializing Global Feeds...",
            "Connecting to Oil, Gold, and BTC data..."
        ]
        self.trump_posts = ["Awaiting latest posts from Truth Social..."]
        self.cftc = "Gold: +12k | Oil: -5k | BTC: +1.2k"

    def update_feeds(self):
        """This mimics the heartbeat of the bot"""
        # Simulated data for now
        self.news = [
            "OIL: OPEC+ considers supply cuts for April 2026.",
            "BTC: Institutional inflows hit record highs today.",
            "GOLD: Safe haven demand spikes on geopolitical news."
        ]
        self.trump_posts = [
            "MAGA 2026: The economy is booming like never before!",
            "America First Energy policy is working for OIL!"
        ]

def main(page: ft.Page):
    bot = MacroFriend()
    
    # UI Setup
    page.title = "Gemini's Macro Terminal"
    page.theme_mode = ft.ThemeMode.DARK
    page.window_width = 1000
    page.window_height = 700
    page.padding = 20

    # UI Components
    cftc_display = ft.Text(bot.cftc, size=20, color="amber", weight="bold")
    news_list = ft.Column(scroll=ft.ScrollMode.AUTO)
    social_list = ft.Column(scroll=ft.ScrollMode.AUTO)

    def refresh_ui():
        while True:
            bot.update_feeds()
            
            # Update News
            news_list.controls.clear()
            for n in bot.news:
                news_list.controls.append(
                    ft.ListTile(
                        title=ft.Text(n, size=14), 
                        leading=ft.Icon(ft.icons.NEW_RELEASES, color="red")
                    )
                )
            
            # Update Social
            social_list.controls.clear()
            for p in bot.trump_posts:
                social_list.controls.append(
                    ft.Card(content=ft.Container(content=ft.Text(p), padding=15))
                )
            
            page.update()
            time.sleep(30) # Refresh heartbeat every 30 seconds

    # Layout Construction
    # FIXED: Using string color names to prevent the 'attribute colors' error
    page.add(
        ft.Container(
            content=ft.Row([
                ft.Text("🚀 MACRO TERMINAL", size=32, weight="bold"),
                ft.Column([
                    ft.Text("CFTC NET CHANGE (LIVE)", size=12), 
                    cftc_display
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            padding=20, 
            bgcolor="bluegrey900", # Changed from ft.colors to a safe string
            border_radius=10
        ),
        ft.Divider(height=20, color="transparent"),
        ft.Row([
            # News Feed
            ft.Container(
                content=ft.Column([
                    ft.Text("🔴 RED FOLDER NEWS", size=20, color="red", weight="bold"), 
                    news_list
                ]),
                expand=2, padding=15, border=ft.border.all(1, "white24"), border_radius=10
            ),
            # Social Feed
            ft.Container(
                content=ft.Column([
                    ft.Text("📱 SOCIAL SENTIMENT", size=20, color="blue", weight="bold"), 
                    social_list
                ]),
                expand=1, padding=15, border=ft.border.all(1, "white24"), border_radius=10
            )
        ], expand=True)
    )

    # Start the background heartbeat
    threading.Thread(target=refresh_ui, daemon=True).start()

if __name__ == "__main__":
    ft.app(target=main)