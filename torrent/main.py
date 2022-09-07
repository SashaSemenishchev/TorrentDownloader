
import sys
from .block import State
import zipfile
import os

__author__ = 'alexisgallepe'

import time
from . import peers_manager
from . import pieces_manager
from . import torrent
from . import tracker
import logging
from threading import Thread
from . import message
import math

def on_progress_dummy(p):
    pass

def on_finish_dummy():
    pass

class TorrentClient:
    percentage_completed = -1
    last_log_line = ""

    def __init__(self, file, uuid):
        try:
            torrent_file = file
        except IndexError:
            logging.error("No torrent file provided!")
            sys.exit(0)
        self.torrent = torrent.Torrent().load_from_path(torrent_file)
        self.tracker = tracker.Tracker(self.torrent)

        self.pieces_manager = pieces_manager.PiecesManager(self.torrent)
        self.peers_manager = peers_manager.PeersManager(self.torrent, self.pieces_manager)
        self.uuid = uuid
        self.peers_manager.start()
        self.on_progress = on_progress_dummy
        self.on_finish = on_finish_dummy
        self.on_start = None
        self.old_percentage = 0

    def set_on_progress(self, func):
        self.on_progress = func

    def set_on_finish(self, func):
        self.on_finish = func
    def set_on_start(self, func):
        self.on_start = func
    def run(self):
        peers_dict = self.tracker.get_peers_from_trackers()
        self.peers_manager.add_peers(peers_dict.values())
        if(self.on_start):
            try:
                self.on_start(self)
            except: pass
        while not self.pieces_manager.all_pieces_completed():
            if not self.peers_manager.has_unchoked_peers():
                time.sleep(1)
                continue

            for piece in self.pieces_manager.pieces:
                index = piece.piece_index

                if self.pieces_manager.pieces[index].is_full:
                    continue

                peer = self.peers_manager.get_random_peer_having_piece(index)
                if not peer:
                    continue

                self.pieces_manager.pieces[index].update_block_status()

                data = self.pieces_manager.pieces[index].get_empty_block()
                if not data:
                    continue

                piece_index, block_offset, block_length = data
                piece_data = message.Request(piece_index, block_offset, block_length).to_bytes()
                peer.send_to_peer(piece_data)

            self.display_progression()

            time.sleep(0.1)
        self.display_progression()
        try:
            files = self.pieces_manager.torrent.file_names
            with zipfile.ZipFile(f"runs/downloads/{self.uuid}.zip", "w") as zip:
                for piece in files:
                    file_path = piece['path']
                    print(file_path)
                    zip.write(file_path, file_path.replace("temp/", "", 1))
            for piece in files:
                os.remove(piece['path'])
        except: pass
        self.on_finish(self)
        self._exit_threads()
    def start(self):
        
        thread = Thread(daemon=True, target=self.run)
        thread.start()

    def display_progression(self):
        new_progression = 0

        for i in range(self.pieces_manager.number_of_pieces):
            for j in range(self.pieces_manager.pieces[i].number_of_blocks):
                if self.pieces_manager.pieces[i].blocks[j].state == State.FULL:
                    new_progression += len(self.pieces_manager.pieces[i].blocks[j].data)

        if new_progression == self.percentage_completed:
            return

        # number_of_peers = self.peers_manager.unchoked_peers_count()
        percentage_completed = float((float(new_progression) / self.torrent.total_length) * 100)
        rounded = math.floor(percentage_completed)
        if(rounded == self.old_percentage):
            return
        self.old_percentage = rounded
        self.on_progress(self, rounded)

        # current_log_line = "Connected peers: {} - {}% completed | {}/{} pieces".format(number_of_peers,
        #                                                                                  round(percentage_completed, 2),
        #                                                                                  self.pieces_manager.complete_pieces,
        #                                                                                  self.pieces_manager.number_of_pieces)
        # if current_log_line != self.last_log_line:
        #     print(current_log_line)

        # self.last_log_line = current_log_line
        self.percentage_completed = new_progression

    def _exit_threads(self):
        self.peers_manager.is_active = False

