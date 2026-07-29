from fastapi import FastAPI

app = FastAPI(title = "PulseBoard")

@app.get("/health")
def health_check():
    return {"status": "ok"}