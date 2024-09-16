import json

from channels.generic.websocket import AsyncWebsocketConsumer


class YourConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.group_name = "backend_updates"

        # Join group
        await self.channel_layer.group_add(self.group_name, self.channel_name)

        # Accept WebSocket connection
        await self.accept()

    async def disconnect(self, close_code):
        # Leave group
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    # Receive message from group
    async def send_update(self, event):
        print(f"Message {event}")
        message = event["message"]

        # Send message to WebSocket
        await self.send(text_data=json.dumps({"message": message}))
