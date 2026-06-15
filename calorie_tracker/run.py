"""Start CalTrack web server."""
import os
import uvicorn

if __name__ == "__main__":
    print("""
  ██████╗ █████╗ ██╗  ████████╗██████╗  █████╗  ██████╗██╗  ██╗
 ██╔════╝██╔══██╗██║  ╚══██╔══╝██╔══██╗██╔══██╗██╔════╝██║ ██╔╝
 ██║     ███████║██║     ██║   ██████╔╝███████║██║     █████╔╝
 ██║     ██╔══██║██║     ██║   ██╔══██╗██╔══██║██║     ██╔═██╗
 ╚██████╗██║  ██║███████╗██║   ██║  ██║██║  ██║╚██████╗██║  ██╗
  ╚═════╝╚═╝  ╚═╝╚══════╝╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝
  Your Personal Calorie Tracker  —  http://localhost:8001
    """)
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    uvicorn.run("app:app", host="0.0.0.0", port=8001, reload=True)
