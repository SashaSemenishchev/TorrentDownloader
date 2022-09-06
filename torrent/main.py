
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
        logging.info("PeersManager Started")
        logging.info("PiecesManager Started")

    def set_on_progress(self, func):
        self.on_progress = func

    def set_on_finish(self, func):
        self.on_finish = func
    def run(self):
        peers_dict = self.tracker.get_peers_from_trackers()
        self.peers_manager.add_peers(peers_dict.values())
        while not self.pieces_manager.all_pieces_completed():
            if not self.peers_manager.has_unchoked_peers():
                time.sleep(1)
                logging.info("No unchocked peers")
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
        with zipfile.ZipFile(f"../runs/downloads/{self.uuid}.zip", "w") as zip:
            for piece in self.pieces_manager.files:
                zip.write(piece)
        for piece in self.pieces_manager.files:
            os.remove(piece)
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
        self.on_progress(percentage_completed)

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
        self.on_finish()

