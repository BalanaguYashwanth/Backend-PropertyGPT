import os
import json
import requests
from flask import Flask, request, jsonify
from config import chat_collection, pb, db, chatv2_collection

from functools import wraps
from firebase_admin import auth
from flask_cors import CORS

# Initialize Flask App
app = Flask(__name__)
CORS(app)


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


@app.route('/userinfo', methods=['GET'])
@check_token
def userInfo():
    try:
        return jsonify({'userInfo': request.user['email']}), 200
    except Exception as e:
        return f'{e}', 400
    
@app.route('/get', methods=['GET'])
def getData():
    try:
        if chatv2_collection:
            print('hello')
            # here document is UID 
            chats = db.collection('chat_v2').document('wOtArbf5bTZlvaBis1El').collection('messages').document('chat1').get()
            print('chats----', chats.to_dict())
            # for chat in chats:
            #     print('chats----', chat.to_dict())
            return jsonify({"message": 'success'}), 200
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

        uid =  request.user['uid']
        userData = userRequest['messages'][0]['content']

        jsonResponse = json.dumps(userRequest)
        response = requests.post(f'{open_ai_url}/v1/chat/completions', jsonResponse, headers=OpenAIHeaders)
        content = response.json()
        
        chatGPTResponse = content['choices'][0]['message']['content']
        message = create(uid=uid,user=userData,chatgpt=chatGPTResponse, collection_type=collection_type)

        # message = create(uid=uid, user='what is Stack', chatgpt='Stack is related to data structures', collection_type=collection_type)
        return jsonify({"message": message}), 200
    except Exception as e:
        return f'Error Occured: {e}', 400

def create(uid,user,chatgpt,collection_type):
    try:
        message = {}
        titleData={}
  
        title_collection_length = 0
        chat_collection_length = 0

        if db.collection(str(uid)):
            chat_collection = db.collection(str(uid)).document('messages').collection(collection_type).count().get()
            chat_collection_length = chat_collection[0][0].value
          
                
        message['id'] = chat_collection_length
        message['user'] = user
        message['chatgpt'] = chatgpt

        titleData['title'] = user[:25]


        db.collection(str(uid)).document('messages').collection(collection_type).document(str(chat_collection_length)).set(message)

        if not db.collection(str(uid)).document('title').collection(collection_type).document(str(title_collection_length)).get().exists:
            db.collection(str(uid)).document('title').collection(collection_type).document(str(title_collection_length)).set(titleData)

        return message
    except Exception as e:
        return f'Error Occured: {e}', 400


if __name__ == '__main__':
    app.run()
