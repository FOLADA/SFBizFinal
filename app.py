from flask import Flask, send_from_directory
from flask_cors import CORS
from db import init_db
from routes import bp as business_routes
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app, origins="*", supports_credentials=True)
init_db()

app.register_blueprint(business_routes)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory('uploads', filename)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000)) 
    app.run(debug=True, host="0.0.0.0", port=port)  
