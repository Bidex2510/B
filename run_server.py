"""Launch the Jarvis web server."""

import uvicorn
from dotenv import load_dotenv

load_dotenv()

if __name__ == "__main__":
    print("""
     ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
     ██║███████║██████╔╝██║   ██║██║███████╗
██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
 ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝
    Web Server v2.0 - Starting up...
    """)
    uvicorn.run(
        "jarvis.api.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
