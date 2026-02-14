import asyncio
import os
import json
import shutil
import html
from datetime import datetime
from telethon import TelegramClient
from telethon.tl.types import (
    MessageMediaPhoto, MessageMediaDocument, Document,
    MessageService, DocumentAttributeFilename
)


'''
https://my.telegram.org/apps - тут взять API_HASH и API_ID, PHONE_NUMBER свой вводите
'''

API_ID = 'xxxxx'  # Замените на ваш API ID
API_HASH = 'xxxxxxxx'  # Замените на ваш API Hash
PHONE_NUMBER = '+123456789'  # Ваш номер телефона



# вставьте полный путь до папки sessions и backups
BACKUP_DIR = '/backups' #
SESSION_FILE = 'sessions/backup_bot.session'

# Настройки логирования
LOG_LEVEL = 'INFO'
LOG_FILE = 'backup.log'
import logging


# Настройка логирования - убираем шум Telethon
logging.getLogger('telethon').setLevel(logging.WARNING)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Создаем клиент
client = TelegramClient(SESSION_FILE, API_ID, API_HASH)


class TelegramBackup:
    def __init__(self, client, backup_dir):
        self.client = client
        self.backup_dir = backup_dir
        self.processed_messages = set()

        # Создаем основную папку для бэкапов
        os.makedirs(backup_dir, exist_ok=True)

    def get_next_backup_folder(self):
        existing_backups = []
        for item in os.listdir(self.backup_dir):
            if item.startswith('backup_') and os.path.isdir(os.path.join(self.backup_dir, item)):
                try:
                    num = int(item.replace('backup_', ''))
                    existing_backups.append(num)
                except ValueError:
                    continue

        next_num = max(existing_backups) + 1 if existing_backups else 1
        backup_folder = os.path.join(self.backup_dir, f'backup_{next_num}')
        os.makedirs(backup_folder, exist_ok=True)
        return backup_folder

    def ask_backup_mode(self):
        """Спрашиваем режим бэкапа у пользователя"""
        print("\n" + "=" * 50)
        print("🎯 Выберите режим бэкапа:")
        print("1. 📥 Полный бэкап (удалить существующие и сохранить всё заново)")
        print("2. 🔄 Обновить существующие (добавить только новые сообщения)")
        print("=" * 50)

        while True:
            choice = input("Введите номер режима (1 или 2): ").strip()
            if choice == '1':
                return 'full'
            elif choice == '2':
                return 'update'
            else:
                print("❌ Неверный выбор. Введите 1 или 2.")

    async def ask_chats_to_backup(self, dialogs):
        """Спрашиваем какие чаты сохранять"""
        print("\n" + "=" * 50)
        print("💬 Выберите какие чаты сохранять:")
        print("1. 👤 Личные чаты")
        print("2. 📢 Каналы")
        print("3. 👥 Группы")
        print("4. 🤖 Боты")
        print("5. 📚 Всё вместе")
        print("6. 🔢 Выбрать конкретные чаты")
        print("=" * 50)

        while True:
            choice = input("Ваш выбор: ").strip()

            if choice == '1':
                return [dialog for dialog in dialogs if dialog.is_user and not getattr(dialog.entity, 'bot', False)]
            elif choice == '2':
                return [dialog for dialog in dialogs if dialog.is_channel]
            elif choice == '3':
                return [dialog for dialog in dialogs if dialog.is_group]
            elif choice == '4':
                return [dialog for dialog in dialogs if getattr(dialog.entity, 'bot', False)]
            elif choice == '5':
                return dialogs
            elif choice == '6':
                return await self.select_specific_chats(dialogs)
            else:
                print("❌ Неверный выбор. Введите номер от 1 до 6.")

    async def select_specific_chats(self, dialogs):
        """Показываем список всех чатов для выбора"""
        print("\n" + "=" * 50)
        print("📋 Список всех чатов:")
        print("=" * 50)

        for i, dialog in enumerate(dialogs, 1):
            chat_type = ""
            if dialog.is_user:
                chat_type = "👤 Личный"
                if getattr(dialog.entity, 'bot', False):
                    chat_type = "🤖 Бот"
            elif dialog.is_channel:
                chat_type = "📢 Канал"
            elif dialog.is_group:
                chat_type = "👥 Группа"

            chat_name = self.get_chat_display_name(dialog.entity)
            print(f"{i:3d}. {chat_type}: {chat_name}")

        print("=" * 50)
        print("💡 Введите номера чатов через пробел (например: 1 3 5 7)")
        print("💡 Или введите 'all' для выбора всех чатов")
        print("=" * 50)

        while True:
            choice = input("Ваш выбор: ").strip().lower()

            if choice == 'all':
                return dialogs

            try:
                selected_numbers = [int(num.strip()) for num in choice.split()]
                selected_dialogs = []

                for num in selected_numbers:
                    if 1 <= num <= len(dialogs):
                        selected_dialogs.append(dialogs[num - 1])
                    else:
                        print(f"❌ Неверный номер: {num}. Доступно от 1 до {len(dialogs)}")
                        break
                else:
                    if not selected_dialogs:
                        print("❌ Выберите хотя бы один чат")
                        continue

                    print(f"✅ Выбрано чатов: {len(selected_dialogs)}")
                    return selected_dialogs

            except ValueError:
                print("❌ Введите номера через пробел (например: 1 3 5)")

    def ask_content_types(self):
        """Спрашиваем какие типы контента сохранять"""
        print("\n" + "=" * 50)
        print("📦 Что сохраняем:")
        print("1. 📝 Messages (сообщения)")
        print("2. 🎥 Videos (видео)")
        print("3. 📎 Documents (документы)")
        print("4. 🎵 Audios (аудио)")
        print("5. 📸 Photos (фото)")
        print("6. 🖼️ Images (изображения)")
        print("7. 🎤 Voice messages (голосовые сообщения)")
        print("8. 📄 Экспорт истории чата (как в Telegram Lite)")
        print("=" * 50)
        print("💡 Введите номера через пробел (например: 1 2 5 7 8)")
        print("💡 Или введите 'all' для сохранения всего")
        print("=" * 50)

        content_map = {
            '1': 'messages',
            '2': 'videos',
            '3': 'documents',
            '4': 'audios',
            '5': 'photos',
            '6': 'images',
            '7': 'voice_messages',
            '8': 'chat_export'
        }

        while True:
            choice = input("Ваш выбор: ").strip().lower()

            if choice == 'all':
                return list(content_map.values())

            try:
                selected_numbers = choice.split()
                selected_types = []

                for num in selected_numbers:
                    if num in content_map:
                        selected_types.append(content_map[num])
                    else:
                        print(f"❌ Неверный номер: {num}")
                        break
                else:
                    if not selected_types:
                        print("❌ Выберите хотя бы один тип контента")
                        continue

                    print("✅ Выбранные типы:", ", ".join(selected_types))
                    return selected_types

            except Exception as e:
                print("❌ Ошибка ввода. Попробуйте снова.")

    async def get_all_dialogs(self):
        """Получаем все диалоги"""
        dialogs = await self.client.get_dialogs()
        logger.info(f"📂 Загружено диалогов: {len(dialogs)}")
        return dialogs

    def get_chat_display_name(self, chat):
        """Получаем отображаемое имя чата"""
        if hasattr(chat, 'title'):
            return chat.title
        elif hasattr(chat, 'first_name'):
            first_name = getattr(chat, 'first_name', '')
            last_name = getattr(chat, 'last_name', '')
            name = f"{first_name} {last_name}".strip()
            return name if name else str(chat.id)
        return str(chat.id)

    def get_chat_username(self, chat):
        """Получаем username чата или имя"""
        if hasattr(chat, 'username') and chat.username:
            return f"@{chat.username}"
        else:
            return self.get_chat_display_name(chat)

    def get_chat_folder_name(self, chat):
        """Генерируем безопасное имя папки для чата"""
        if hasattr(chat, 'username') and chat.username:
            safe_name = f"chat_{chat.username}"
        elif hasattr(chat, 'title'):
            safe_name = f"chat_{chat.title}"
        else:
            first_name = getattr(chat, 'first_name', '')
            last_name = getattr(chat, 'last_name', '')
            name = f"{first_name}_{last_name}".strip()
            if not name:
                name = str(chat.id)
            safe_name = f"chat_{name}"

        # Заменяем небезопасные символы и ограничиваем длину
        safe_name = "".join(c for c in safe_name if c.isalnum() or c in ('_', '-')).rstrip()
        safe_name = safe_name[:100]  # Ограничиваем длину
        return safe_name

    def log_with_chat(self, message, chat_name, emoji="📝"):
        """Логирует сообщение с указанием чата"""
        logger.info(f"{emoji} {message} (чат: {chat_name})")

    def should_save_media_type(self, media_type, content_types):
        """Проверяем, нужно ли сохранять данный тип медиа"""
        if media_type == 'photo' and 'photos' in content_types:
            return True
        elif media_type == 'video' and 'videos' in content_types:
            return True
        elif media_type == 'document' and 'documents' in content_types:
            return True
        elif media_type == 'audio' and 'audios' in content_types:
            return True
        elif media_type == 'image' and 'images' in content_types:
            return True
        elif media_type == 'voice' and 'voice_messages' in content_types:
            return True
        return False

    async def export_chat_history(self, chat, chat_folder, chat_name):
        """Экспортирует историю чата в формате, похожем на Telegram Lite"""
        try:
            export_folder = os.path.join(chat_folder, 'chat_export')
            os.makedirs(export_folder, exist_ok=True)

            self.log_with_chat("Начинаем экспорт истории чата...", chat_name, "📄")

            # Создаем HTML файл с красивым оформлением
            html_file = os.path.join(export_folder, 'chat_history.html')
            css_file = os.path.join(export_folder, 'style.css')

            # CSS стили для красивого отображения
            css_content = """
            <style>
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    margin: 0;
                    padding: 20px;
                    background-color: #f5f5f5;
                    line-height: 1.6;
                }
                .chat-container {
                    max-width: 1000px;
                    margin: 0 auto;
                    background: white;
                    border-radius: 12px;
                    box-shadow: 0 2px 20px rgba(0,0,0,0.1);
                    overflow: hidden;
                }
                .chat-header {
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 30px;
                    text-align: center;
                }
                .chat-title {
                    font-size: 28px;
                    font-weight: bold;
                    margin-bottom: 10px;
                }
                .chat-info {
                    font-size: 14px;
                    opacity: 0.9;
                }
                .messages-container {
                    padding: 20px;
                    max-height: 80vh;
                    overflow-y: auto;
                }
                .message {
                    margin-bottom: 20px;
                    padding: 15px;
                    border-radius: 12px;
                    background: #f8f9fa;
                    border-left: 4px solid #667eea;
                }
                .message.outgoing {
                    background: #e3f2fd;
                    border-left-color: #2196f3;
                    margin-left: 50px;
                }
                .message-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 8px;
                }
                .sender {
                    font-weight: bold;
                    color: #2c3e50;
                }
                .date {
                    color: #7f8c8d;
                    font-size: 12px;
                }
                .message-content {
                    color: #34495e;
                }
                .media-indicator {
                    display: inline-block;
                    background: #667eea;
                    color: white;
                    padding: 2px 8px;
                    border-radius: 12px;
                    font-size: 12px;
                    margin-left: 10px;
                }
                .search-box {
                    width: 100%;
                    padding: 12px;
                    border: none;
                    border-bottom: 2px solid #ddd;
                    font-size: 16px;
                    margin-bottom: 20px;
                }
                .search-box:focus {
                    outline: none;
                    border-bottom-color: #667eea;
                }
                .stats {
                    background: #f8f9fa;
                    padding: 15px;
                    border-radius: 8px;
                    margin-bottom: 20px;
                    text-align: center;
                }
            </style>
            """

            with open(css_file, 'w', encoding='utf-8') as f:
                f.write(css_content)

            # HTML шаблон
            html_template = f"""
            <!DOCTYPE html>
            <html lang="ru">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>История чата: {html.escape(chat_name)}</title>
                {css_content}
            </head>
            <body>
                <div class="chat-container">
                    <div class="chat-header">
                        <h1 class="chat-title">{html.escape(chat_name)}</h1>
                        <div class="chat-info">
                            Экспорт от {datetime.now().strftime('%d.%m.%Y %H:%M')} | 
                            Всего сообщений: <span id="message-count">0</span>
                        </div>
                    </div>

                    <div class="stats">
                        <input type="text" id="search" class="search-box" placeholder="🔍 Поиск по сообщениям...">
                        <div>Для поиска начните вводить текст в поле выше</div>
                    </div>

                    <div class="messages-container" id="messages">
            """

            # Собираем информацию об участниках
            participants = {}
            try:
                if hasattr(chat, 'participants'):
                    async for user in self.client.iter_participants(chat):
                        name = self.get_chat_display_name(user)
                        participants[user.id] = name
            except Exception as e:
                self.log_with_chat(f"Не удалось получить участников: {e}", chat_name, "⚠️")

            # Записываем сообщения в HTML
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(html_template)

                message_count = 0
                # Получаем все сообщения (можно ограничить для очень больших чатов)
                async for message in self.client.iter_messages(chat, limit=50000):
                    if isinstance(message, MessageService):
                        continue

                    # Определяем отправителя
                    sender_name = "Unknown"
                    if message.sender_id:
                        sender_name = participants.get(message.sender_id, f"User {message.sender_id}")

                    # Форматируем дату
                    date_str = message.date.strftime("%d.%m.%Y %H:%M") if message.date else "Unknown"

                    # Форматируем текст
                    text = html.escape(message.text or "").replace('\n', '<br>')

                    # Добавляем индикатор медиа
                    media_indicator = ""
                    if message.media:
                        if isinstance(message.media, MessageMediaPhoto):
                            media_indicator = '<span class="media-indicator">📷 Фото</span>'
                        elif isinstance(message.media, MessageMediaDocument):
                            document = message.media.document
                            if isinstance(document, Document):
                                mime_type = document.mime_type or ''
                                if 'video' in mime_type:
                                    media_indicator = '<span class="media-indicator">🎥 Видео</span>'
                                elif 'audio' in mime_type:
                                    if 'voice' in mime_type:
                                        media_indicator = '<span class="media-indicator">🎤 Голосовое</span>'
                                    else:
                                        media_indicator = '<span class="media-indicator">🎵 Аудио</span>'
                                else:
                                    media_indicator = '<span class="media-indicator">📎 Документ</span>'

                    # Определяем класс для исходящих/входящих сообщений
                    message_class = "outgoing" if message.out else ""

                    message_html = f"""
                    <div class="message {message_class}">
                        <div class="message-header">
                            <span class="sender">{html.escape(sender_name)}</span>
                            <span class="date">{date_str}</span>
                        </div>
                        <div class="message-content">
                            {text}
                            {media_indicator}
                        </div>
                    </div>
                    """

                    f.write(message_html)
                    message_count += 1

                    if message_count % 1000 == 0:
                        self.log_with_chat(f"Экспортировано {message_count} сообщений", chat_name, "📄")

                # Закрываем HTML
                f.write(f"""
                    </div>
                </div>

                <script>
                    // Поиск по сообщениям
                    document.getElementById('search').addEventListener('input', function(e) {{
                        const searchTerm = e.target.value.toLowerCase();
                        const messages = document.querySelectorAll('.message');
                        let visibleCount = 0;

                        messages.forEach(message => {{
                            const text = message.textContent.toLowerCase();
                            if (text.includes(searchTerm)) {{
                                message.style.display = 'block';
                                visibleCount++;
                            }} else {{
                                message.style.display = 'none';
                            }}
                        }});

                        document.getElementById('message-count').textContent = visibleCount + ' (отфильтровано)';
                    }});

                    // Подсчет сообщений
                    document.getElementById('message-count').textContent = {message_count};
                </script>
                </body>
                </html>
                """)

            # Создаем текстовую версию
            txt_file = os.path.join(export_folder, 'chat_history.txt')
            with open(txt_file, 'w', encoding='utf-8') as f:
                f.write(f"{'=' * 60}\n")
                f.write(f"ИСТОРИЯ ЧАТА: {chat_name}\n")
                f.write(f"ДАТА ЭКСПОРТА: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n")
                f.write(f"ВСЕГО СООБЩЕНИЙ: {message_count}\n")
                f.write(f"{'=' * 60}\n\n")

                async for message in self.client.iter_messages(chat, limit=20000):
                    if isinstance(message, MessageService):
                        continue

                    date_str = message.date.strftime("%d.%m.%Y %H:%M") if message.date else "Unknown"
                    sender_name = "Unknown"
                    if message.sender_id:
                        sender_name = participants.get(message.sender_id, f"User {message.sender_id}")

                    text = message.text or ""
                    media_info = ""
                    if message.media:
                        if isinstance(message.media, MessageMediaPhoto):
                            media_info = " [ФОТО]"
                        elif isinstance(message.media, MessageMediaDocument):
                            media_info = " [ДОКУМЕНТ]"

                    f.write(f"[{date_str}] {sender_name}: {text}{media_info}\n")

            # Создаем файл с метаданными
            metadata = {
                'chat_name': chat_name,
                'chat_id': chat.id,
                'export_date': datetime.now().isoformat(),
                'total_messages': message_count,
                'participants_count': len(participants),
                'participants': {str(k): v for k, v in participants.items()}
            }

            with open(os.path.join(export_folder, 'metadata.json'), 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)

            self.log_with_chat(
                f"Экспорт завершен! Сообщений: {message_count}, файлы: chat_history.html, chat_history.txt", chat_name,
                "✅")
            return message_count

        except Exception as e:
            self.log_with_chat(f"Ошибка при экспорте истории: {e}", chat_name, "❌")
            return 0

    async def save_messages_only(self, chat, chat_folder, chat_name, backup_mode, content_types):
        """Сохраняем только сообщения (без медиа)"""
        try:
            messages_file = os.path.join(chat_folder, 'messages.json')

            if backup_mode == 'full' and os.path.exists(messages_file):
                os.remove(messages_file)  # Удаляем старые сообщения

            existing_messages = []
            existing_ids = set()

            # Загружаем существующие сообщения (если режим обновления)
            if backup_mode == 'update' and os.path.exists(messages_file):
                try:
                    with open(messages_file, 'r', encoding='utf-8') as f:
                        existing_messages = json.load(f)
                    existing_ids = {msg['id'] for msg in existing_messages}
                    self.log_with_chat(f"Загружено {len(existing_messages)} существующих сообщений", chat_name, "📊")
                except Exception as e:
                    self.log_with_chat(f"Ошибка загрузки сообщений: {e}", chat_name, "❌")
                    existing_ids = set()

            new_messages = []
            total_processed = 0

            # Получаем ВСЕ сообщения (limit=None)
            async for message in self.client.iter_messages(chat, limit=None):
                if isinstance(message, MessageService):
                    continue  # Пропускаем сервисные сообщения

                if message.id in existing_ids:
                    continue  # Пропускаем уже сохраненные

                message_data = {
                    'id': message.id,
                    'date': message.date.isoformat() if message.date else None,
                    'from_id': message.sender_id,
                    'text': message.text or '',
                    'has_media': bool(message.media),
                    'media_info': None
                }

                # Сохраняем информацию о медиа (но не скачиваем)
                if message.media and 'messages' in content_types:
                    message_data['media_info'] = await self.get_media_info(message)

                new_messages.append(message_data)
                total_processed += 1

                # Логируем прогресс каждые 100 сообщений
                if total_processed % 100 == 0:
                    self.log_with_chat(f"Сохранено {total_processed} сообщений", chat_name, "📨")

                # Делаем небольшую паузу между сообщениями
                await asyncio.sleep(0.01)

            # Сохраняем все сообщения
            if new_messages or existing_messages:
                all_messages = existing_messages + new_messages
                # Сортируем по ID (временной метке)
                all_messages.sort(key=lambda x: x['id'])

                with open(messages_file, 'w', encoding='utf-8') as f:
                    json.dump(all_messages, f, ensure_ascii=False, indent=2)

                self.log_with_chat(f"Сохранено сообщений: {len(new_messages)} новых, всего: {len(all_messages)}",
                                   chat_name, "💾")

            return len(new_messages), total_processed

        except Exception as e:
            self.log_with_chat(f"Ошибка при сохранении сообщений: {e}", chat_name, "❌")
            return 0, 0

    async def get_media_info(self, message):
        """Получаем информацию о медиа без скачивания"""
        if not message.media:
            return None

        media_info = {
            'type': None,
            'file_name': None,
            'file_size': None,
            'mime_type': None
        }

        try:
            if isinstance(message.media, MessageMediaPhoto):
                media_info['type'] = 'photo'
                media_info['file_name'] = f"photo_{message.id}.jpg"

            elif isinstance(message.media, MessageMediaDocument):
                document = message.media.document
                if isinstance(document, Document):
                    media_info['file_size'] = document.size
                    media_info['mime_type'] = document.mime_type

                    # Получаем имя файла
                    file_name = f"document_{message.id}"
                    for attr in document.attributes:
                        if isinstance(attr, DocumentAttributeFilename):
                            file_name = attr.file_name
                            break

                    media_info['file_name'] = file_name

                    mime_type = document.mime_type or ''
                    if 'video' in mime_type:
                        media_info['type'] = 'video'
                    elif 'audio' in mime_type:
                        if 'voice' in mime_type:
                            media_info['type'] = 'voice'
                        else:
                            media_info['type'] = 'audio'
                    elif 'image' in mime_type:
                        media_info['type'] = 'image'
                    else:
                        media_info['type'] = 'document'

        except Exception as e:
            media_info['error'] = str(e)

        return media_info

    async def download_media_files(self, chat, chat_folder, chat_name, content_types):
        """Скачиваем медиафайлы на основе сохраненных сообщений"""
        try:
            messages_file = os.path.join(chat_folder, 'messages.json')
            if not os.path.exists(messages_file):
                self.log_with_chat("Файл сообщений не найден", chat_name, "❌")
                return 0, 0

            # Загружаем сообщения
            with open(messages_file, 'r', encoding='utf-8') as f:
                messages = json.load(f)

            # Создаем папки для выбранных типов медиа
            media_folders = []
            if 'photos' in content_types: media_folders.append('photos')
            if 'videos' in content_types: media_folders.append('videos')
            if 'voice_messages' in content_types: media_folders.append('voice_messages')
            if 'audios' in content_types: media_folders.append('audios')
            if 'images' in content_types: media_folders.append('images')
            if 'documents' in content_types: media_folders.append('documents')

            for folder in media_folders:
                os.makedirs(os.path.join(chat_folder, folder), exist_ok=True)

            total_to_download = sum(1 for msg in messages if
                                    msg.get('has_media') and msg.get('media_info') and self.should_save_media_type(
                                        msg['media_info'].get('type'), content_types))
            downloaded_count = 0
            skipped_count = 0

            self.log_with_chat(f"Найдено {total_to_download} сообщений с медиа для скачивания", chat_name, "📊")

            # Скачиваем медиа для каждого сообщения
            for i, msg in enumerate(messages):
                if not msg.get('has_media') or not msg.get('media_info'):
                    continue

                media_info = msg['media_info']
                media_type = media_info.get('type')

                if not media_type or not self.should_save_media_type(media_type, content_types):
                    continue

                file_name = media_info.get('file_name', f'{media_type}_{msg["id"]}')
                media_folder = os.path.join(chat_folder, media_type + 's')
                file_path = os.path.join(media_folder, file_name)

                # Проверяем существование файла
                if os.path.exists(file_path):
                    skipped_count += 1
                    if skipped_count % 50 == 0:
                        self.log_with_chat(f"Пропущено {skipped_count} файлов (уже существуют)", chat_name, "📁")
                    continue

                # Скачиваем файл
                try:
                    # Получаем сообщение по ID
                    message = await self.client.get_messages(chat, ids=msg['id'])
                    if message and message.media:
                        self.log_with_chat(f"Скачиваем {media_type}: {file_name}", chat_name, "⏬")

                        downloaded_path = await asyncio.wait_for(
                            message.download_media(file=file_path),
                            timeout=120  # 2 минуты на файл
                        )

                        downloaded_count += 1
                        file_size = os.path.getsize(downloaded_path) if os.path.exists(downloaded_path) else 0
                        size_mb = file_size / (1024 * 1024)

                        self.log_with_chat(f"Успешно скачан {media_type}: {file_name} ({size_mb:.1f} MB)", chat_name,
                                           "✅")

                        # Прогресс каждые 10 файлов
                        if downloaded_count % 10 == 0:
                            self.log_with_chat(f"Скачано {downloaded_count}/{total_to_download} файлов", chat_name, "📊")

                except asyncio.TimeoutError:
                    self.log_with_chat(f"Таймаут скачивания {media_type}: {file_name}", chat_name, "⏰")
                except Exception as e:
                    self.log_with_chat(f"Ошибка скачивания {media_type}: {file_name} - {e}", chat_name, "❌")

                # Пауза между файлами
                await asyncio.sleep(0.1)

            return downloaded_count, skipped_count

        except Exception as e:
            self.log_with_chat(f"Ошибка при скачивании медиа: {e}", chat_name, "❌")
            return 0, 0

    async def backup_chat(self, chat, backup_folder, backup_mode, content_types):
        """Создаем бэкап для одного чата"""
        chat_name = self.get_chat_username(chat)
        chat_folder_name = self.get_chat_folder_name(chat)
        chat_folder = os.path.join(backup_folder, chat_folder_name)

        try:
            # Создаем папку чата
            if backup_mode == 'full' and os.path.exists(chat_folder):
                shutil.rmtree(chat_folder)  # Удаляем старую папку

            os.makedirs(chat_folder, exist_ok=True)

            # Сохраняем информацию о чате
            chat_info = {
                'id': chat.id,
                'name': self.get_chat_display_name(chat),
                'username': getattr(chat, 'username', None),
                'first_name': getattr(chat, 'first_name', None),
                'last_name': getattr(chat, 'last_name', None),
                'backup_date': datetime.now().isoformat(),
                'backup_mode': backup_mode,
                'content_types': content_types
            }

            with open(os.path.join(chat_folder, 'chat_info.json'), 'w', encoding='utf-8') as f:
                json.dump(chat_info, f, ensure_ascii=False, indent=2)

            # Сохраняем сообщения (если выбран этот тип)
            new_messages_count, total_messages = 0, 0
            if 'messages' in content_types:
                self.log_with_chat("ШАГ 1: Сохраняем сообщения...", chat_name, "📝")
                new_messages_count, total_messages = await self.save_messages_only(chat, chat_folder, chat_name,
                                                                                   backup_mode, content_types)
            else:
                self.log_with_chat("Пропускаем сохранение сообщений", chat_name, "⏭️")

            # Скачиваем медиафайлы
            downloaded_count, skipped_count = 0, 0
            media_types = [t for t in content_types if t != 'messages' and t != 'chat_export']
            if media_types:
                self.log_with_chat("ШАГ 2: Скачиваем медиафайлы...", chat_name, "📁")
                downloaded_count, skipped_count = await self.download_media_files(chat, chat_folder, chat_name,
                                                                                  content_types)
            else:
                self.log_with_chat("Пропускаем скачивание медиа", chat_name, "⏭️")

            # Экспортируем историю чата (если выбран этот тип)
            exported_count = 0
            if 'chat_export' in content_types:
                self.log_with_chat("ШАГ 3: Экспортируем историю чата...", chat_name, "📄")
                exported_count = await self.export_chat_history(chat, chat_folder, chat_name)
            else:
                self.log_with_chat("Пропускаем экспорт истории", chat_name, "⏭️")

            # Финальное сообщение
            self.log_with_chat(
                f"Чат сохранён! Сообщений: {total_messages}, "
                f"Файлов: {downloaded_count} скачано, {skipped_count} пропущено, "
                f"Экспорт: {exported_count} сообщений",
                chat_name, "🎉"
            )

        except Exception as e:
            self.log_with_chat(f"Критическая ошибка при бэкапе: {e}", chat_name, "💥")

    async def run_single_backup(self):
        """Запускаем однократный бэкап"""
        try:
            # Запрашиваем режим бэкапа
            backup_mode = self.ask_backup_mode()

            # Получаем все диалоги
            dialogs = await self.get_all_dialogs()

            # Запрашиваем какие чаты сохранять
            selected_dialogs = await self.ask_chats_to_backup(dialogs)

            # Запрашиваем какие типы контента сохранять
            content_types = self.ask_content_types()

            # Создаем папку для этого бэкапа
            backup_folder = self.get_next_backup_folder()

            logger.info(f"📂 Создана папка для бэкапа: {os.path.basename(backup_folder)}")
            logger.info(f"🎯 Режим бэкапа: {'📥 Полный' if backup_mode == 'full' else '🔄 Обновление'}")
            logger.info(f"💬 Выбрано чатов: {len(selected_dialogs)}")
            logger.info(f"📦 Выбранные типы: {', '.join(content_types)}")

            if not selected_dialogs:
                logger.warning("⚠️ Чаты не выбраны!")
                return

            # Создаем бэкап для каждого выбранного чата
            for i, dialog in enumerate(selected_dialogs, 1):
                chat_name = self.get_chat_username(dialog.entity)
                chat_type = "👤 Личный" if dialog.is_user else "📢 Канал" if dialog.is_channel else "👥 Группа" if dialog.is_group else "🤖 Бот"
                logger.info(f"🔹 Обрабатываем чат {i}/{len(selected_dialogs)}: {chat_type} {chat_name}")
                await self.backup_chat(dialog.entity, backup_folder, backup_mode, content_types)
                # Пауза между чатами
                await asyncio.sleep(1)

            logger.info(f"✅ Бэкап завершен! Папка: {os.path.basename(backup_folder)}")
            logger.info(f"📊 Итоги: {len(selected_dialogs)} чатов обработано")

        except Exception as e:
            logger.error(f"❌ Ошибка в процессе бэкапа: {e}")

        async def run_daily_backup(self):
            """Запускаем ежедневный бэкап"""
            while True:
                try:
                    await self.run_single_backup()
                    logger.info("⏰ Ждем 24 часа до следующего бэкапа...")
                    await asyncio.sleep(24 * 60 * 60)  # 24 часа
                except Exception as e:
                    logger.error(f"❌ Ошибка в ежедневном бэкапе: {e}")
                    await asyncio.sleep(60 * 60)  # Ждем 1 час при ошибке

async def main():
    """Основная функция"""
    await client.start(phone=PHONE_NUMBER)
    logger.info("✅ Клиент запущен успешно!")

    # Создаем экземпляр бэкапера
    backup_bot = TelegramBackup(client, BACKUP_DIR)

    # Запускаем однократный бэкап
    await backup_bot.run_single_backup()

    # Или ежедневный бэкап (раскомментируйте для использования)
    # await backup_bot.run_daily_backup()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⏹️ Бэкап остановлен пользователем")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")