from torrent.main import TorrentClient
from flask import Flask, render_template, redirect, send_from_directory, request
from werkzeug.utils import secure_filename
from uuid import uuid4
import os
from flask_socketio import SocketIO, emit, socketio

UPLOAD_FOLDER = 'runs/'
os.makedirs("runs/uploads", exist_ok=True)
os.makedirs("runs/downloads", exist_ok=True)
os.makedirs("temp", exist_ok=True)
ALLOWED_EXTENSIONS = {'torrent', "bittorrent"}
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

app = Flask("TorrentDownloader")
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config["downloading"] = {}
app.config["active"] = {}
socket = SocketIO(app)

@app.route("/")
@app.route("/index")
def upload():
    return render_template("index.html")
# def on_start():
#     with app.test_request_context("/downloading"):
#         emit()
@app.route("/download-start/", methods=["POST"])
def start_download():
    uuid = str(uuid4())
    if "file" not in request.files:
        return "No file"
    file = request.files["file"]
    if file.filename == '':
            return redirect("/")
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        path = os.path.join(app.config['UPLOAD_FOLDER'] + "uploads/", f"{uuid}.torrent")
        file.save(path)

        torrent = TorrentClient(path, uuid)
        def on_start(torrent):
            socket.emit("download_status", {"data": "Загрузка"}, to=app.config["active"][torrent])
        torrent.on_start = on_start
        torrent.start()
        app.config["downloading"][uuid] = torrent
    return redirect(f"/downloading?download_id={uuid}&filename={filename}")

@app.route("/downloading")
def upload_status():
    return render_template("downloading.html", downloading=request.args.get("filename"), download_id=request.args.get("download_id"))

@app.route("/download/<path:filename>")
def download(filename):
    uploads = app.config['UPLOAD_FOLDER'] + "downloads/"
    return send_from_directory(directory=uploads, filename=filename + ".zip")

@socket.on("connection_data")
def on_connection(message):
    def on_progress(torrent, progress):
        socket.emit("download_update", {"data": str(progress)}, to=app.config["active"][torrent])
    def on_finish(torrent):
        del app.config["downloading"][message["data"]]
        socket.emit("download_finish", to=app.config["active"][torrent])
        del app.config["active"][torrent]
    torrent = app.config["downloading"][message["data"]]
    app.config["active"][torrent] = request.sid
    torrent.set_on_progress(on_progress)
    torrent.set_on_finish(on_finish)
    socket.emit("download_status", {"data": "Поиск пиров"}, to=request.sid)

if __name__ == "__main__":
    app.run(port=8080, debug=True)