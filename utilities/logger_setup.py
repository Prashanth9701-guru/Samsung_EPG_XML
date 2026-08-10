import os.path
import logging

def set_up_log():
    os.makedirs("logs", exist_ok=True)
    file_path = os.path.join("logs", "execution.log")
    print(f"Path: {file_path}")

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(file_path, mode="w"),
            logging.StreamHandler()]
    )


