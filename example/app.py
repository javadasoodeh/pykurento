#!/usr/bin/env python

import uuid
import os
import sys
import logging

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
logging.getLogger().setLevel(logging.DEBUG)

import tornado.ioloop
import tornado.web

from pykurento import KurentoClient

kurento = KurentoClient("ws://localhost:8888/kurento")


class Participant:
  def __init__(self, room, offer):
    self.participant_id = str(uuid.uuid4())
    self.room = room
    self.offer = offer
    self.incoming = self.room.pipeline.createWebRtcEndpoint()
    self.outgoings = {}
    self.answer = None

  def get_answer(self):
    if not self.answer:
      self.answer = self.incoming.processOffer(self.offer)

    return self.answer

  def connect(self, participant, offer):
    if participant.participant_id not in self.outgoings:
      self.outgoings[participant.participant_id] = self.room.pipeline.createWebRtcEndpoint()
      self.incoming.connect(self.outgoings[participant.participant_id])

    outgoing = self.outgoings[participant.participant_id]
    return outgoing.processOffer(offer)


class Room:
  rooms = {}

  @classmethod
  def get(cls, room_id):
    if room_id not in cls.rooms:
      cls.rooms[room_id] = Room(room_id)
    return cls.rooms[room_id]

  def __init__(self, room_id):
    self.room_id = room_id
    self.participants = {}
    self.pipeline = kurento.createPipeline()

  def addParticipant(self, participant):
    self.participants[participant.participant_id] = participant
    return participant

  def getParticipant(self, participant_id):
    return self.participants[participant_id] if participant_id in self.participants else None


class RoomHandler(tornado.web.RequestHandler):
  def get(self, room_id=None):
    room = Room.get(room_id)
    self.finish({"participants": [k for k in room.participants]})

  def post(self, room_id):
    room = Room.get(room_id)
    sdp_offer = self.request.body
    participant = room.addParticipant(Participant(room, sdp_offer))
    sdp_answer = participant.get_answer()

    self.finish({
      "participant_id": participant.participant_id,
      "answer": sdp_answer
    })


class SubscribeToParticipantHandler(tornado.web.RequestHandler):
  def post(self, room_id, from_participant_id, to_participant_id):
    room = Room.get(room_id)
    sdp_offer = self.request.body
    from_participant = room.getParticipant(from_participant_id)
    to_participant = room.getParticipant(to_participant_id)

    if from_participant and to_participant:
      sdp_answer = from_participant.connect(to_participant, sdp_offer)
      self.finish({ "answer": sdp_answer })
      return
    else:
      self.set_status(409)
      self.finish({ "error": sdp_answer })
    

class IndexHandler(tornado.web.RequestHandler):
  def get(self):
    with open("index.html","r") as f:
      self.finish(f.read())


class RoomIndexHandler(tornado.web.RequestHandler):
  def get(self, room_id=None):
    with open("room.html","r") as f:
      self.finish(f.read())


class LoopbackHandler(tornado.web.RequestHandler):
  def get(self):
    with open("loopback.html","r") as f:
      self.finish(f.read())

  def post(self):
    sdp_offer = self.request.body
    pipeline = kurento.createPipeline()
    wrtc_pub = pipeline.createWebRtcEndpoint()
    sdp_answer = wrtc_pub.processOffer(sdp_offer)
    wrtc_pub.connect(wrtc_pub)
    self.finish(str(sdp_answer))


application = tornado.web.Application([
  (r"/", IndexHandler),
  (r"/loopback", LoopbackHandler),
  (r"/room", RoomIndexHandler),
  (r"/room/(?P<room_id>\d*)", RoomHandler),
  (r"/room/(?P<room_id>[^/]*)/subscribe/(?P<from_participant_id>[^/]*)/(?P<to_participant_id>[^/]*)", SubscribeToParticipantHandler),
  (r'/static/(.*)', tornado.web.StaticFileHandler, {'path': os.path.join(os.path.dirname(__file__), "static")}),
  #(r"/join/{room_id}", JoinRoomHandler),
], debug=True) #, autoreload=False)

if __name__ == "__main__":
  application.listen(8080)
  print "Webserver now listening on port 8080"
  tornado.ioloop.IOLoop.instance().start()
  kurento.close()
