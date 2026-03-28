@echo off
echo Building Coach Carter Backend with PyInstaller...
cd backend
pip install pyinstaller
pyinstaller --onefile --name CoachCarter-Backend ^
  --add-data "assets;assets" ^
  --hidden-import uvicorn.logging ^
  --hidden-import uvicorn.loops ^
  --hidden-import uvicorn.loops.auto ^
  --hidden-import uvicorn.protocols ^
  --hidden-import uvicorn.protocols.http ^
  --hidden-import uvicorn.protocols.http.auto ^
  --hidden-import uvicorn.protocols.websockets ^
  --hidden-import uvicorn.protocols.websockets.auto ^
  --hidden-import uvicorn.lifespan ^
  --hidden-import uvicorn.lifespan.on ^
  main.py
echo Done! Executable at backend/dist/CoachCarter-Backend.exe
cd ..
