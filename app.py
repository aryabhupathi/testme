from flask import Flask
import os
app = create_app()
@app.route("/")
def home():
    return "Railway Flask App Working!"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
