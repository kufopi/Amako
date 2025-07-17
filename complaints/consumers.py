import json
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        if self.scope['user'] == AnonymousUser():
            await self.close()
            return

        self.user_id = str(self.scope['user'].id)
        self.group_name = f'user_{self.user_id}'
        
        # Join user group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        # Leave user group
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def notification_message(self, event):
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'message': event['message'],
            'complaint_id': event.get('complaint_id')
        }))