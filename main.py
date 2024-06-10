import os
from typing import List, Sequence
import pandas as pd
from google.api_core.client_options import ClientOptions
from google.api_core.exceptions import *
from google.cloud import documentai_v1beta3 as documentai
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "windy-fortress-384110-a7ca97a5cfde.json"
#client = documentai.DocumentProcessorServiceClient()

#gcs_source = documentai.GcsSource(uri='https://www.fbcinc.com/source/virtualhall_images/Convergence/Google_Cloud/Copy_of_Document_AI_Solution_Brief_for_DoD.pdf')
#input_config = documentai.InputConfig(gcs_source=gcs_source, mime_type='application/pdf')

PROJECT_ID = "windy-fortress-384110"
LOCATION = "us"
PROCESSOR_ID = "OCR_PROCESSOR"

FILE_PATH = "test.pdf"
MIME_TYPE = "application/pdf"

def list_processors(project_id: str, location: str) -> None:
    opts = ClientOptions(api_endpoint=f"{location}-documentai.googleapis.com")
    client = documentai.DocumentProcessorServiceClient(client_options=opts)
    parent = client.common_location_path(project_id, location)
    processor_list = client.list_processors(parent=parent)
    for processor in processor_list:
        print(f"Processor Name: {processor.name}")
        print(f"Processor Display Name: {processor.display_name}")
        print(f"Processor Type: {processor.type_}")
        print("")

def get_processor_id(project_id: str, location: str, processor_type: str):
    opts = ClientOptions(api_endpoint=f"{location}-documentai.googleapis.com")
    client = documentai.DocumentProcessorServiceClient(client_options=opts)
    parent = client.common_location_path(project_id, location)
    processor_list = client.list_processors(parent=parent)
    for processor in processor_list:
        if processor_type == processor.type_:
            return processor.name.split('/')[-1]

def fetch_processor_types(project_id: str, location: str) -> None:
    opts = ClientOptions(api_endpoint=f"{location}-documentai.googleapis.com")
    client = documentai.DocumentProcessorServiceClient(client_options=opts)
    parent = client.common_location_path(project_id, location)
    response = client.fetch_processor_types(parent=parent)
    print("Processor types:")
    for processor_type in response.processor_types:
        if processor_type.allow_creation:
            print(processor_type.type_)

def create_processor(
    project_id: str, location: str, processor_display_name: str, processor_type: str
) -> None:
    try:
        opts = ClientOptions(api_endpoint=f"{location}-documentai.googleapis.com")
        client = documentai.DocumentProcessorServiceClient(client_options=opts)
        parent = client.common_location_path(project_id, location)
        processor = client.create_processor(
            parent=parent,
            processor=documentai.Processor(
                display_name=processor_display_name, type_=processor_type
            ),
        )
        print(f"Processor Name: {processor.name}")
        print(f"Processor Display Name: {processor.display_name}")
        print(f"Processor Type: {processor.type_}")
    except AlreadyExists:
        pass

def get_table_data(
    rows: Sequence[documentai.Document.Page.Table.TableRow], text: str
) -> List[List[str]]:
    """
    Get Text data from table rows
    """
    all_values: List[List[str]] = []
    for row in rows:
        current_row_values: List[str] = []
        for cell in row.cells:
            current_row_values.append(
                text_anchor_to_text(cell.layout.text_anchor, text)
            )
        all_values.append(current_row_values)
    return all_values


def text_anchor_to_text(text_anchor: documentai.Document.TextAnchor, text: str) -> str:
    """
    Document AI identifies table data by their offsets in the entirety of the
    document's text. This function converts offsets to a string.
    """
    response = ""
    # If a text segment spans several lines, it will
    # be stored in different text segments.
    for segment in text_anchor.text_segments:
        start_index = int(segment.start_index)
        end_index = int(segment.end_index)
        response += text[start_index:end_index]
    return response.strip().replace("\n", " ")

def process_image(img_content, resource_name):
    raw_document = documentai.RawDocument(content=img_content, mime_type=MIME_TYPE)
    request = documentai.ProcessRequest(name=resource_name, raw_document=raw_document)
    return docai_client.process_document(request=request).document

def process_ocr(image_content):
    id = get_processor_id(PROJECT_ID, LOCATION, "OCR_PROCESSOR")
    res_name = docai_client.processor_path(PROJECT_ID, LOCATION, id)
    return process_image(image_content, res_name)

def process_table(image_content):
    id = get_processor_id(PROJECT_ID, LOCATION, "FORM_PARSER_PROCESSOR")
    res_name = docai_client.processor_path(PROJECT_ID, LOCATION, id)
    return process_image(image_content, res_name)

def get_summary(image_content):
    id = get_processor_id(PROJECT_ID, LOCATION, "SUMMARY_PROCESSOR")
    res_name = docai_client.processor_path(PROJECT_ID, LOCATION, id)
    return process_image(image_content, res_name)

def doc_table_to_str(document):
    all_tables = ''
    for page in document.pages:
        for index, table in enumerate(page.tables):
            header_row_values = get_table_data(table.header_rows, document.text)
            body_row_values = get_table_data(table.body_rows, document.text)
            df = pd.DataFrame(
                data=body_row_values,
                columns=pd.MultiIndex.from_arrays(header_row_values),
            )
            all_tables += df.to_string()
    return all_tables

def summary_to_str(document):
    all_text = ''
    for entity in document.entities:
        all_text += entity.mention_text
    return all_text

docai_client = documentai.DocumentProcessorServiceClient(
    client_options=ClientOptions(api_endpoint=f"{LOCATION}-documentai.googleapis.com")
)

list_processors(PROJECT_ID, LOCATION)
fetch_processor_types(PROJECT_ID, LOCATION)
create_processor(PROJECT_ID, LOCATION, "proc1", "OCR_PROCESSOR")
create_processor(PROJECT_ID, LOCATION, "proc3", "FORM_PARSER_PROCESSOR")
create_processor(PROJECT_ID, LOCATION, "proc4", "SUMMARY_PROCESSOR")

CHOOSE_TYPE, UPLOAD_PDF = range(2)
PDF_TYPES = ["OCR", "Table Extract", "Summary"]

def start(update: Update, context):
    reply_keyboard = [PDF_TYPES]
    update.message.reply_text(
        "Welcome! Please choose a type of PDF processing:",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
    )
    return CHOOSE_TYPE

def choose_type(update: Update, context):
    # user = update.effective_user
    context.user_data["pdf_type"] = update.message.text
    update.message.reply_text(
        f"You chose: {context.user_data['pdf_type']}. Please upload a PDF file now.",
        reply_markup=ReplyKeyboardRemove()
    )
    return UPLOAD_PDF

def process_pdf(update: Update, context):
    user = update.effective_user
    pdf_file = update.message.document.get_file()
    image_content = bytes(pdf_file.download_as_bytearray())
    chosen_type = context.user_data.get("pdf_type", "Unknown")

    content = 'invalid'
    print(context.user_data, )
    if chosen_type == PDF_TYPES[0]:
        content = process_ocr(image_content).text
    elif chosen_type == PDF_TYPES[1]:
        document = process_table(image_content)
        content = doc_table_to_str(document)
    elif chosen_type == PDF_TYPES[2]:
        document = get_summary(image_content)
        content = summary_to_str(document)

    txt_filename = f"{user.id}_result.txt"
    with open(txt_filename, "w", encoding="utf-8") as f:
        f.write(content)

    with open(txt_filename, "rb") as f:
        update.message.reply_document(document=f)

    os.remove(txt_filename)
    return ConversationHandler.END

def cancel(update: Update, context):
    user = update.effective_user
    update.message.reply_text(
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


def main():
    with open('token', "r") as file: token=file.read()
    updater = Updater(token, use_context=True)
    dp = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSE_TYPE: [MessageHandler(Filters.regex(f"^({'|'.join(PDF_TYPES)})$"), choose_type)],
            UPLOAD_PDF: [MessageHandler(Filters.document.pdf, process_pdf)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    dp.add_handler(conv_handler)

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()