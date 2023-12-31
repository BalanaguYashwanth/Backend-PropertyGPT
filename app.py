import os
import json
import requests
from flask import Flask, request, jsonify
from config import chat_collection, pb, db
from functools import wraps
from firebase_admin import auth
from flask_cors import CORS
import google.generativeai as palm

# Initialize Flask App
app = Flask(__name__)
CORS(app)
palm.configure(api_key=os.environ['BARD_API_KEY'])

@app.route("/")
def home():
    return {'status': 200}

# todo items -
# keep validations like if email is not there then it should say "required email"
# email verification for signup
# better to go phonnumber verification

@app.route('/signup', methods=['POST'])
def signup():
    response = request.json
    email, password = response.values()
    try:
        auth.create_user(
            email=email,
            password=password
        )
        auth_response = pb.auth().sign_in_with_email_and_password(email, password)
        jwt = auth_response['idToken']
        return jsonify({'token': jwt}), 200
    except Exception as e:
        return f'{e}', 400


@app.route('/signin', methods=['POST'])
def signin():
    response = request.json
    email, password = response.values()
    try:
        user = pb.auth().sign_in_with_email_and_password(email, password)
        jwt = user['idToken']
        return jsonify({'token': jwt}), 200
    except Exception as e:
        return f'{e}', 400


def check_token(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if not request.headers.get('authorization'):
            return {'message': 'Please signin'}, 400
        try:
            user = auth.verify_id_token(request.headers['authorization'])
            request.user = user
        except:
            return {'message': 'Invalid User, Please signin'}, 400
        return f(*args, **kwargs)
    return wrap


@app.route("/train", methods=['POST'])
@check_token
def train():
    response = request.json
    message = response['message']
    try:
        if message:
            response = palm.chat(messages=message)
            return jsonify(response.last)
        else:
            return jsonify({'response': 'please provide valid information'}), 200
    except Exception as e:
        return f'{e}', 400


@app.route("/askHouzz", methods=['POST'])
@check_token
def bardAPI():
    response = request.json
    message = response['message']
    try:
        if message:
            modified_message = prompt(message)
            response = palm.chat(messages=modified_message)
            return jsonify(response.last)
        else:
            return jsonify({'response': 'please provide valid information'}), 200
    except Exception as e:
        return f'{e}', 400


def prompt(user_input):
    # prompt_message = f'Please search properties and builders of Project Size, here are the data needed for Flat Configurations: About builder, Website link , Price list, amenities, how many units availabile, photo links, locations, google map location link and landmarks, and {user_input}. Also retrive text data in json format'
    data = "{\"builders\":[{\"name\":\"FtanukuBuilders\",\"ongoing_projects\":[{\"cityname\":\"Mumbai\",\"name\":\"ThePalms\",\"placename\":\"Mumbai\",\"units_available\":100},]}]}"
    # prompt_message = f'I am looking for properties and builders information - f{user_input}. Could you please provide me with information about the builders details, their ongoing projects,how many units availabile, cityname and retrive response in json format also include all these places longitude and latitude in this json object'
    prompt_message = f'Please provide me with accurate information about builders and properties in {user_input}. I am looking for details regarding the project size, flat configurations, price list for budget, floor plans, brochure, amenities, locations and landmarks, information about the builder, and frequently asked questions (FAQs)'
    # prompt_message = user_input
    return prompt_message


@app.route('/userinfo', methods=['GET'])
@check_token
def userInfo():
    try:
        return jsonify({'userInfo': request.user['email']}), 200
    except Exception as e:
        return f'{e}', 400


@app.route('/fetchMessagesByChatId', methods=['POST'])
@check_token
def getMessagesData():
    uid = request.user['uid']
    chat_id = request.json['chat_id']
    type = request.json['type']
    try:
        if chat_collection:
            collectionData = db.collection(str(uid)).document(
                type).collection(chat_id).stream()
            all_messages = [message.to_dict() for message in collectionData]
            return jsonify({'response': all_messages}), 200

            # return jsonify({"message": 'tyes'}), 200
    except Exception as e:
        return f'{e}'


@app.route('/fetchTitleByUser', methods=['POST'])
@check_token
def getDataByTitle():
    titlesArray = []
    titles = {}
    id = 0
    uid = request.user['uid']
    type = request.json['type']
    try:
        if chat_collection:
            collectionData = db.collection(uid).document('title').collections()
            for collection in collectionData:
                titles = {}
                for index, doc in enumerate(collection.stream()):
                    titles['type'] = doc.id
                    titles['id'] = id
                    # titles['id']=doc.id
                    titles['text'] = doc.to_dict()['title']
                    titlesArray.append(titles)
                    id = id+1

            return jsonify({'response': titlesArray}), 200

            # return jsonify({"message": 'tyes'}), 200
    except Exception as e:
        return f'{e}'


@app.route('/v1/chat/completions', methods=['POST'])
@check_token
def ask():
    open_ai_key = os.environ['OPENAI_API_KEY']
    open_ai_url = os.environ['OPENAI_API_URL']

    OpenAIHeaders = {
        "Content-Type": "application/json",
        "Authorization":  f'Bearer {open_ai_key}',
    }

    try:
        userRequest = request.json['data']
        userData = userRequest['messages'][0]['content']

        jsonResponse = json.dumps(userRequest)
        response = requests.post(
            f'{open_ai_url}/v1/chat/completions', jsonResponse, headers=OpenAIHeaders)
        content = response.json()

        chatGPTResponse = content['choices'][0]['message']['content']
        # message = create(uid=uid, user='what is Stack', chatgpt='Stack is related to data structures', collection_type=collection_type)
        return jsonify({"response": chatGPTResponse}), 200
    except Exception as e:
        return f'Error Occured: {e}', 400


def create(uid, user, chatgpt, collection_type):
    try:
        message = {}
        titleData = {}

        title_collection_length = 0
        chat_collection_length = 0

        if db.collection(str(uid)):
            chat_collection = db.collection(str(uid)).document(
                'messages').collection(collection_type).count().get()
            chat_collection_length = chat_collection[0][0].value

        message['id'] = chat_collection_length
        message['user'] = user
        message['chatgpt'] = chatgpt

        titleData['title'] = user[:25]

        db.collection(str(uid)).document('messages').collection(
            collection_type).document(str(chat_collection_length)).set(message)

        if not db.collection(str(uid)).document('title').collection(collection_type).document(collection_type).get().exists:
            db.collection(str(uid)).document('title').collection(
                collection_type).document(collection_type).set(titleData)

        return message
    except Exception as e:
        return f'Error Occured: {e}', 400


@app.route('/createCompany', methods=['POST'])
@check_token
def create_company():
    try:
        collection_name = 'companies'
        companies_count = 0

        companies_count = get_collection_length(collection_name)

        uid = request.user['uid']
        email = request.user['email']
        request.json['uid'] = uid
        request.json['email'] = email

        db.collection(collection_name).document(
            str(companies_count)).set(request.json)
        return request.json

    except Exception as e:
        return f"{e}", 400


@app.route('/getCompanyDetail', methods=['GET'])
@check_token
def get_company_detail():
    try:
        empty_companydata = {
            "name": "",
            "meetingURL": ""
        }
        collection_name = 'companies'
        uid = request.user['uid']
        all_companies = [doc.to_dict()
                         for doc in db.collection(collection_name).stream()]
        for company in all_companies:
            if company['uid'] == uid:
                return company
        return empty_companydata
    except Exception as e:
        return f"{e}", 400


def get_collection_length(collection_name: str):
    if db.collection(collection_name):
        collection_length_ref = db.collection(collection_name).count().get()
        companies_count = collection_length_ref[0][0].value
    return companies_count


if __name__ == '__main__':
    app.run()
