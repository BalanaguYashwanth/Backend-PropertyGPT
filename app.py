import os, ast
import re
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

@app.route("/askHouzz",methods=['POST'])
def bardAPI():
    response = request.json
    message = response['message']
    try:
        if message:
            updated_user_prompt = prompt(message)
            # updated_user_prompt ='looking for properties and builders in Gurgaon that have flat configurations within my budget of 1 crore. Could you please provide me with information about the builders, their ongoing projects, flat configurations, builder details and project location also retrive text in json format '
            response = palm.generate_text(prompt=updated_user_prompt,max_output_tokens=2000)
            jsonResponse = response.result
            cleanedJSONResponse = cleanJSON(jsonResponse)
     
            # return json.loads(cleanedJSONResponse), 200
            # return jsonify(cleanedJSONResponse),200,
            return jsonResponse
        else:
            return jsonify({'response': 'please provide valid information'}), 200
    except Exception as e:
      return f'{e}', 400

def prompt(user_input):
    # prompt_message = f'Please search properties and builders of Project Size, here are the data needed for Flat Configurations: About builder, Website link , Price list, amenities, how many units availabile, photo links, locations, google map location link and landmarks, and {user_input}. Also retrive text data in json format'
    prompt_message = f'looking for properties and builders - f{user_input}. Could you please provide me with information about the builders, their ongoing projects, flat configurations also retrive response in json format'
    return prompt_message

def cleanJSON(jsonResponse):
    regex1 = '```json'
    regex2 = '```'
    regex_list = [regex1,regex2]
    for regex in regex_list:
        if re.search(regex,jsonResponse):
            jsonResponse = re.sub(regex,'',jsonResponse)
    # indentedJSON = json.dumps(json.loads(jsonResponse), indent=2)
    # result = ast.literal_eval(indentedJSON)
    return jsonResponse

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
        collection_type = request.json['collection_type']

        uid = request.user['uid']
        userData = userRequest['messages'][0]['content']

        jsonResponse = json.dumps(userRequest)
        response = requests.post(
            f'{open_ai_url}/v1/chat/completions', jsonResponse, headers=OpenAIHeaders)
        content = response.json()

        chatGPTResponse = content['choices'][0]['message']['content']

        createdResponse = create(
            uid=uid, user=userData, chatgpt=chatGPTResponse, collection_type=collection_type)

        # message = create(uid=uid, user='what is Stack', chatgpt='Stack is related to data structures', collection_type=collection_type)
        return jsonify({"response": createdResponse}), 200
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


if __name__ == '__main__':
    app.run()
