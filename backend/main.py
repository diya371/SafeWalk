from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from services.route_service import get_routes
import os

app = FastAPI(
    title="SafeWalk API",
    description="AI-powered safe route recommendation system",
    version="1.0.0"
)

# CORS Configuration - Allow frontend domains
allowed_origins = [
    "http://localhost:3000",      # Local React dev
    "http://localhost:5173",      # Local Vite dev
    "http://localhost:5174",      # Local Vite dev (alternate port)
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",

    "https://safe-walk-seven.vercel.app",
]

# Add production domain if available
production_domain = os.getenv("FRONTEND_URL")
if production_domain:
    allowed_origins.append(production_domain)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Returns both safest and shortest routes with distance, time and safety scor
@app.get("/")
def home():
    return {
        "message": "SafeWalk Backend Running 🚀",
        "status": "healthy",
        "version": "1.0.0"
    }

@app.get("/health")
def health_check():
    return {"status": "ok"}

# MAIN API
@app.get("/route")
def route(start_lat: float, start_lon: float, end_lat: float, end_lon: float):
    
    result = get_routes(start_lat, start_lon, end_lat, end_lon)

    return result

