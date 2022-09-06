from torrent.main import TorrentClient
from flask import Flask, render_template, redirect, send_from_directory, request
from werkzeug.utils import secure_filename
from uuid import uuid4
import os
from flask_socketio import SocketIO, emit

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
        # torrent.on_start = 
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
    def on_progress(progress):
        print(progress)
        
        with socket.test_request_context("/downloading"):
            emit("download_update", {"data": str(progress)})
    def on_finish():
        del app.config["downloading"][message["data"]]
        with app.test_request_context("/downloading"):
            emit("download_finish")
    torrent = app.config["downloading"][message["data"]]
    torrent.set_on_progress(on_progress)
    torrent.set_on_finish(on_finish)

if __name__ == "__main__":
    app.run(port=8080, debug=True)