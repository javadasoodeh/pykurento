import tornado.web
from pykurento import media


class MultiResHandler(tornado.web.RequestHandler):
    low_res = None
    med_res = None
    high_res = None
    incoming = None

    async def get(self):
        res = self.get_argument("res", None)
        if res and MultiResHandler.incoming:
            if res == "high":
                MultiResHandler.high_res.connect(MultiResHandler.incoming)
            elif res == "med":
                MultiResHandler.med_res.connect(MultiResHandler.incoming)
            elif res == "low":
                MultiResHandler.low_res.connect(MultiResHandler.incoming)
        else:
            await self.render("multires.html")

    async def post(self):
        sdp_offer = self.request.body
        pipeline = self.application.kurento.create_pipeline()
        MultiResHandler.incoming = media.WebRtcEndpoint(pipeline)
        MultiResHandler.high_res = MultiResHandler.incoming
        MultiResHandler.low_res = media.GStreamerFilter(pipeline,
                                                        command="capsfilter caps=video/x-raw,width=160,height=120",
                                                        filterType="VIDEO")
        MultiResHandler.med_res = media.GStreamerFilter(pipeline,
                                                        command="capsfilter caps=video/x-raw,width=320,height=240",
                                                        filterType="VIDEO")

        sdp_answer = MultiResHandler.incoming.process_offer(sdp_offer)
        await self.finish(str(sdp_answer))

        await MultiResHandler.high_res.connect(MultiResHandler.incoming)
        await MultiResHandler.incoming.connect(MultiResHandler.low_res)
        await MultiResHandler.incoming.connect(MultiResHandler.med_res)
