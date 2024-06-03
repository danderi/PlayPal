"""
This module takes care of starting the API Server, Loading the DB and Adding the endpoints
"""
import os
from flask import Flask, request, jsonify, url_for, send_from_directory
from flask_migrate import Migrate
from flask_swagger import swagger
from api.utils import APIException, generate_sitemap
from api.models import db, Room
from api.routes import api
from api.admin import setup_admin
from api.commands import setup_commands

from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import logging


from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager

from flask_mail import Mail

ENV = "development" if os.getenv("FLASK_DEBUG") == "1" else "production"
static_file_dir = os.path.join(os.path.dirname(
    os.path.realpath(__file__)), '../public/')
app = Flask(__name__)

app.url_map.strict_slashes = False

jwt = JWTManager(app)

# database condiguration
db_url = os.getenv("DATABASE_URL")
if db_url is not None:
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url.replace(
        "postgres://", "postgresql://")
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:////tmp/test.db"

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
MIGRATE = Migrate(app, db, compare_type=True)
db.init_app(app)

# Configuración de Flask-Mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = 'babypractic@gmail.com'
app.config['MAIL_PASSWORD'] = 'ybzq vfld dege gzei'
app.config['MAIL_DEFAULT_SENDER'] = 'babypractic@gmail.com'

# app.config['FRONTEND_URL'] = os.getenv('FRONTEND_URL')

mail = Mail(app)

# Configuración de bcrypt
bcrypt = Bcrypt(app)

# Configurar el logging
logging.basicConfig(level=logging.INFO, filename='room_expiration_log.log', filemode='a', format='%(asctime)s - %(levelname)s - %(message)s')

# add the admin
setup_admin(app)

# add the admin
setup_commands(app)

# Add all endpoints form the API with a "api" prefix
app.register_blueprint(api, url_prefix='/api')

# Handle/serialize errors like a JSON object


@app.errorhandler(APIException)
def handle_invalid_usage(error):
    return jsonify(error.to_dict()), error.status_code

# generate sitemap with all your endpoints


@app.route('/')
def sitemap():
    if ENV == "development":
        return generate_sitemap(app)
    return send_from_directory(static_file_dir, 'index.html')

# any other endpoint will try to serve it like a static file


@app.route('/<path:path>', methods=['GET'])
def serve_any_other_file(path):
    if not os.path.isfile(os.path.join(static_file_dir, path)):
        path = 'index.html'
    response = send_from_directory(static_file_dir, path)
    response.cache_control.max_age = 0  # avoid cache memory
    return response

 #Función para verificar la expiración de los rooms
def check_rooms_expiration():
    with app.app_context():
        rooms = Room.query.filter(Room.is_deleted == False).all()
        logging.info(f"Checking expiration for {len(rooms)} rooms.")
        for room in rooms:
            if room.end_time and datetime.strptime(room.end_time, '%Y-%m-%d %H:%M') < datetime.now():
                logging.info(f"Expiring room {room.id} scheduled to end at {room.end_time}.")
                room.is_deleted = True
                db.session.commit()
            else:
                logging.info(f"Room {room.id} is not expired yet; scheduled to end at {room.end_time}.")

# Configurar el scheduler
def setup_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_rooms_expiration, 'interval', minutes=1)
    scheduler.start()
    logging.info("Scheduler started...")


# this only runs if `$ python src/main.py` is executed
if __name__ == '__main__':
    setup_scheduler()
    PORT = int(os.environ.get('PORT', 3001))
    app.run(host='0.0.0.0', port=PORT, debug=True)
