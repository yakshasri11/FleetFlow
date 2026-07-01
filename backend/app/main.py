from fastapi import FastAPI

app = FastAPI(title="FleetFlow API")

@app.get("/")
def home():
    return {
        "message": "FleetFlow Backend Running Successfully"
    }
