#!/usr/bin/env python3
"""
Quick launcher for Wally Synthesis Dashboard
Opens the interactive dashboard in your default browser
"""

import webbrowser


def main():
    print("🚀 Opening Wally Synthesis Interactive Dashboard...")

    # URL for the dashboard
    dashboard_url = "http://localhost:8051"

    print(f"🌐 Dashboard URL: {dashboard_url}")
    print("📊 Features:")
    print("   • Sweep Campaign dropdown selection")
    print("   • Interactive filtering and drill-down")
    print("   • Real-time data refresh")
    print("   • Publication-quality plots")
    print()

    # Open in browser
    try:
        webbrowser.open(dashboard_url)
        print("✅ Dashboard opened in your default browser")
        print()
        print("If the dashboard doesn't open automatically:")
        print("   1. Ensure the dashboard is running (python3 launch_dashboard.py)")
        print(f"   2. Manually navigate to: {dashboard_url}")
    except Exception as e:
        print(f"❌ Could not open browser: {e}")
        print(f"   Please manually navigate to: {dashboard_url}")

if __name__ == "__main__":
    main()
