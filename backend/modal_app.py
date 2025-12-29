import modal
import os
import subprocess
import tempfile

app = modal.App("code-app")

# Define the sandbox image (matches sandbox/Dockerfile)
sandbox_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("rustc")
    .pip_install("numpy", "torch") # torch is pytorch
)

# Define the app image (matches backend/Dockerfile)
web_dist_path = os.path.join(os.path.dirname(__file__), "../frontend/dist")
backend_path = os.path.dirname(__file__)

app_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("fastapi[all]", "sqlmodel", "uvicorn", "uv", "python-jose[cryptography]", "passlib[bcrypt]", "python-multipart", "google-genai")
    .env({"EXECUTION_ENV": "modal"})
    .add_local_dir(web_dist_path, remote_path="/assets")
    .add_local_dir(backend_path, remote_path="/root")
)

@app.function(image=sandbox_image)
def run_in_sandbox(code: str, language: str):
    """
    Executes code in a secure Modal sandbox.
    """
    print(f"Running {language} code in sandbox...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        filename = "main.py"
        cmd = ["python", "main.py"]
        
        if language == "rust":
            filename = "main.rs"
            cmd = ["sh", "-c", "rustc main.rs && ./main"]

        code_path = os.path.join(temp_dir, filename)
        with open(code_path, "w") as f:
            f.write(code)
            
        try:
            # Run command with timeout
            result = subprocess.run(
                cmd,
                cwd=temp_dir,
                capture_output=True,
                text=True,
                timeout=5
            )
            
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {
                "stdout": "",
                "stderr": "Execution timed out",
                "exit_code": 124
            }
        except Exception as e:
            return {
                "stdout": "",
                "stderr": str(e),
                "exit_code": 1
            }

# Define the volume for database persistence
volume = modal.Volume.from_name("code-app-volume", create_if_missing=True)

@app.function(
    image=app_image, 
    secrets=[modal.Secret.from_name("code-app-secrets")],
    volumes={"/data": volume},
    # Set DATABASE_URL to verify we use the persistent volume
    timeout=600
)
@modal.asgi_app()
def fastapi_app():
    # Ensure DATABASE_URL is set to use the volume if not already in secrets
    if not os.environ.get("DATABASE_URL"):
        os.environ["DATABASE_URL"] = "sqlite:////data/database.db"
        
    from main import app as web_app
    return web_app
