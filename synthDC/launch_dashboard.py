#!/usr/bin/env python3
"""
Launch Wally Interactive Dashboard
"""

import sys

from interactive_dashboard import WallyInteractiveDashboard


def main():
    print("🚀 Launching Wally Synthesis Interactive Dashboard...")
    print()

    try:
        dashboard = WallyInteractiveDashboard(port=8052)
        dashboard.run(debug=False, host='0.0.0.0')
    except KeyboardInterrupt:
        print("\n👋 Dashboard stopped by user")
    except Exception as e:
        print(f"❌ Error starting dashboard: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
