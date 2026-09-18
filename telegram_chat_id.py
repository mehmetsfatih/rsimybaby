"""Read chat IDs locally without writing the bot token to a file or command history."""
from getpass import getpass
import json
from urllib.request import urlopen

try:
    token = getpass('BotFather token (gizli giris): ').strip()
    with urlopen(f'https://api.telegram.org/bot{token}/getUpdates', timeout=20) as response:
        data = json.load(response)
    chats = {}
    for update in data.get('result', []):
        msg = update.get('message', update.get('channel_post', {}))
        chat = msg.get('chat', {})
        if 'id' in chat:
            chats[chat['id']] = chat.get('title', chat.get('first_name', chat.get('type', '')))
    for chat_id, name in chats.items():
        print(f'{name}: {chat_id}')
    if not chats:
        print('Telegramda botuna /start gonderip tekrar calistir. Bu bot baska uygulamada kullanilmamali.')
except Exception:
    print('Telegram bilgileri okunamadi. Token ve internet baglantisini kontrol et.')
