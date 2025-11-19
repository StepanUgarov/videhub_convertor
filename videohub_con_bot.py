import os
import tempfile
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import xml.etree.ElementTree as ET
import csv
from datetime import timedelta

# Загружаем переменные из .env файла
from dotenv import load_dotenv
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def simple_xml_to_csv_converter(xml_file, csv_file):
    """
    Конвертер XML в CSV с RGB кодами
    """
    tree = ET.parse(xml_file)
    root = tree.getroot()
    
    # Создаем словарь для хранения цветов
    color_map = {}
    for row in root.findall('.//row'):
        code = row.find('code').text if row.find('code') is not None else ""
        r = int(row.find('R').text) if row.find('R') is not None else 32767
        g = int(row.find('G').text) if row.find('G') is not None else 32767
        b = int(row.find('B').text) if row.find('B') is not None else 32767
        
        # Конвертируем 16-битные значения в 8-битные (0-255)
        r_8bit = min(255, r // 256)
        g_8bit = min(255, g // 256)
        b_8bit = min(255, b // 256)
        
        color_map[code] = f"rgb({r_8bit},{g_8bit},{b_8bit})"
    
    with open(csv_file, 'w', newline='', encoding='utf-8') as csvfile:
        csvwriter = csv.writer(csvfile)
        
        # Заголовки с RGB колонкой
        headers = [
            "Session Start Date", "Event", "Session Name", "Session Start", 
            "Session End", "Tag Description", "Tag Notes", "Tag Start", 
            "Tag End", "Tag Duration (secs)", "Attribute №1", "Attribute №2", 
            "Attribute №3", "RGB Color", "Optional Column"
        ]
        csvwriter.writerow(headers)
        
        # Обрабатываем все события
        for instance in root.findall('.//instance'):
            code = instance.find('code').text if instance.find('code') is not None else ""
            start = float(instance.find('start').text) if instance.find('start') is not None else 0
            end = float(instance.find('end').text) if instance.find('end') is not None else 0
            
            # Получаем RGB код
            rgb_color = color_map.get(code, "rgb(128,128,128)")
            
            # Конвертация времени
            def sec_to_time(sec):
                return str(timedelta(seconds=int(sec)))
            
            # Игроки из labels
            players = []
            for label in instance.findall('label'):
                group = label.find('group').text if label.find('group') is not None else ""
                name = label.find('text').text if label.find('text') is not None else ""
                players.append(f"{group}: {name}")
            
            # Формируем строку
            row = [
                "2025/11/12",      # Session Start Date
                code,              # Event
                "Тренировка 1",    # Session Name
                "00:00:00",       # Session Start
                "01:30:00",       # Session End
                code,              # Tag Description
                "",               # Tag Notes
                sec_to_time(start), # Tag Start
                sec_to_time(end),  # Tag End
                int(end - start),  # Tag Duration
                players[0] if len(players) > 0 else "",  # Attribute 1
                players[1] if len(players) > 1 else "",  # Attribute 2
                players[2] if len(players) > 2 else "",  # Attribute 3
                rgb_color,         # RGB Color
                ""                # Optional Column
            ]
            
            csvwriter.writerow(row)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    welcome_text = """
🤖 Конвертер XML в CSV с RGB кодами

Как использовать:
1. Отправьте мне XML файл
2. Я автоматически конвертирую его в CSV
3. Вы получите файл с добавленными RGB кодами

Просто отправьте XML файл и я сделаю всё остальное! 🚀
    """
    await update.message.reply_text(welcome_text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = """
📖 Помощь по использованию бота

Команды:
/start - начать работу с ботом
/help - показать эту справку

Процесс работы:
1. Подготовьте XML файл с данными
2. Отправьте файл как документ в этот чат
3. Дождитесь обработки
4. Получите CSV файл с результатом
    """
    await update.message.reply_text(help_text)

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик загружаемых документов"""
    try:
        document = update.message.document
        
        # Проверяем что это XML файл
        if not (document.file_name and document.file_name.lower().endswith('.xml')):
            await update.message.reply_text(
                "❌ Пожалуйста, отправьте файл с расширением .xml"
            )
            return
        
        # Отправляем сообщение о начале обработки
        processing_msg = await update.message.reply_text(
            "🔄 Начинаю обработку файла... Это займет несколько секунд."
        )
        
        # Создаем временную директорию
        with tempfile.TemporaryDirectory() as tmp_dir:
            xml_path = os.path.join(tmp_dir, "input.xml")
            csv_path = os.path.join(tmp_dir, "result.csv")
            
            # Скачиваем файл
            file = await context.bot.get_file(document.file_id)
            await file.download_to_drive(xml_path)
            
            # Конвертируем
            simple_xml_to_csv_converter(xml_path, csv_path)
            
            # Проверяем что файл создан
            if not os.path.exists(csv_path):
                await processing_msg.edit_text("❌ Ошибка: CSV файл не был создан")
                return
            
            # Отправляем результат
            await update.message.reply_document(
                document=open(csv_path, 'rb'),
                filename=f"converted_{document.file_name.replace('.xml', '.csv')}",
                caption="✅ Конвертация завершена! Ваш CSV файл с RGB кодами готов."
            )
            
            # Удаляем сообщение о обработке
            await processing_msg.delete()
            
            logger.info(f"Успешная конвертация файла: {document.file_name}")
            
    except Exception as e:
        logger.error(f"Ошибка при обработке файла: {str(e)}")
        await update.message.reply_text(
            f"❌ Произошла ошибка при конвертации:\n{str(e)}"
        )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(f"Ошибка: {context.error}")

def main():
    """Основная функция запуска бота"""
    # Получаем токен из .env файла
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN не найден в .env файле")
        return
    
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    
    # Обработчик ошибок
    application.add_error_handler(error_handler)
    
    # Запускаем бота
    logger.info("Бот запускается...")
    application.run_polling()

if __name__ == "__main__":
    main()