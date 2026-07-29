import os
import base64
import requests
import cv2

class RemoteInferenceClient:
	def __init__(
			self,
			server="http://192.168.31.5:8000",
			token=""
		):

		self.predict_url = server + "/v1/predict"

		self.headers = {

			"Content-Type":"application/json",

			"Token":token

		}

		self.model="yolo11"
		self.conf=0.25
		self.iou=0.45

	def encode_image(self, image_file):
		with open(image_file, "rb") as f:
			img64 = base64.b64encode(f.read()).decode()

		suffix = os.path.splitext(image_file)[1].lower()
		mime={
			".jpg":"image/jpeg",
			".png":"image/png",
			".bmp":"image/bmp"
		}.get(suffix,"image/jpeg")

		return f"data:{mime};base64,{img64}"

	def predict(self,image_file):
		img=self.encode_image(image_file)
		payload={
			"model":self.model,
			"image":img,
			"params":{
				"conf_threshold":self.conf,
				"iou_threshold":self.iou
			}
		}

		r=requests.post(
			self.predict_url,
			json=payload,
			headers=self.headers,
			timeout=30
		)
		r.raise_for_status()
		return r.json()

	def loadResult(self,result):
		data=result["data"]
		for item in data["shapes"]:
			shape = Shape(item["label"])
			pts=item["points"]
			for p in pts:
				shape.addPoint(QPointF(p[0], p[1]))
			self.canvas.loadShapes(self.canvas.shapes+[shape])