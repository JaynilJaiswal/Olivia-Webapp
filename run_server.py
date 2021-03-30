from flask import Flask,render_template,request,redirect,url_for,session,jsonify,send_file
# from deepcorrect import DeepCorrect
import os
import requests
from scipy.io.wavfile import read,write
import io
import json

import numpy as np
import librosa
from timezonefinder import TimezoneFinder
from geopy.geocoders import Nominatim
geolocator = Nominatim(user_agent="geoapiExercises") 

from Models.generic_sound_classifier.audio_detect import *

from features.time import getTime
from features.date import getDate
from features.weather import getWeather
from features.location import getLocation
STT_href = "http://a925e532ca56.ngrok.io/"
TTS_href = "http://6adef9c89477.ngrok.io/"
NLU_href = "http://3620f9d95c56.ngrok.io/"
audio_classifier = AudioClassifier()
preprocess_href = "http://127.0.0.1:5040/"

base_inp_dir = "Audio_input_files/"
base_out_dir = "Audio_output_files/"

app = Flask(__name__)
app.secret_key = 'random'
data=[]
# corrector = DeepCorrect('Models/DeepCorrect_PunctuationModel/deeppunct_params_en', 'Models/DeepCorrect_PunctuationModel/deeppunct_checkpoint_google_news')
# FEATURE_LIST= ["time","date","location","weather","alarm reminder","schedule","music","find information","message","email","call","features","translation"]

def select_feature(name,user_data):
    if name=="time":
        return getTime(user_data["timezone"])
    if name=='date':
        return getDate(user_data["timezone"])
    if name=='weather':
        return getWeather(user_data['address']['city'])
    if name=='location':
        return getLocation(user_data['address'])


def backend_pipeline(filename,user_data):
    
    #STT
    payload={'file':open(base_inp_dir + filename,'rb')}
    r = requests.post(STT_href,files=payload)
    input_str=json.loads(r.text)['text'][0]
    print (input_str)

    #preprocess   
    text = input_str    
    if 'olivia' in text:
        text = text.split('olivia')[1].strip()
    if 'alivia' in text:
        text = text.split('olivia')[1].strip()
    if 'olvia' in text:
        text = text.split('olvia')[1].strip()
    if 'oliva' in text:
        text = text.split('oliva')[1].strip()
    if 'holivia' in text:
        text = text.split('holivia')[1].strip()

    input_str = text + "?"
    # NEED to figure out punctuation issue.
    # input_str = corrector.correct(text)[0]['sequence']
    print("Preprocessed text: " + input_str)

    #NLU
    r = requests.get(NLU_href,json={"sentence":text}).json()
    print("Most related feature : "+str(r['Most related feature'][0][0]))
    print("\n")
    print("====================================================================")
    print("=========================Complete result============================")
    print(str(r['Most related feature']))
    print("====================================================================")
    print("====================================================================")
    print("\n")
    
    #Feature
    input_str = select_feature(r['Most related feature'][0][0],user_data)
    #TTS        
    payload={"input_str": input_str }
    r = requests.get(TTS_href, params=payload).json()

    bytes_wav = bytes()

    byte_io = io.BytesIO(bytes_wav)
    write(byte_io, r['rate'], np.array(r['data'],np.int16))
    
    output_wav = byte_io.read() 
    
    if os.path.exists(base_out_dir + 'result.wav'):
        os.remove(base_out_dir + 'result.wav')
        
    with open(base_out_dir + 'result.wav','bx') as f:
        f.write(output_wav)



@app.route('/',methods=['GET','POST'])
def home():
    if request.method=='GET':
        return render_template('index.html')
    if request.method=="POST":
        user_location =json.loads(request.form['data'])
        tf = TimezoneFinder()
        user_timezone = tf.timezone_at(lng=user_location['long'],lat=user_location['lat'])
        user_address = geolocator.reverse(str(user_location['lat'])+','+str(user_location['long'])).raw['address']
        session['user_data']= {'location':user_location,'timezone':user_timezone,'address':user_address}
        session['command_in_progress']=False
        print (session['user_data'])
        return "saved"

@app.route('/process',methods=['GET','POST'])
def process():
    if request.method=='POST':
        global data
        filename = request.files['audio_data'].filename
        audio,sr = librosa.load(request.files['audio_data'])
        labels = audio_classifier.detect(audio)
        if labels[0]=="Finger snapping":
            session['command_in_progress'] = True
            print(session['command_in_progress'])
            return {"continue":"YES"}
        else:
            if session['command_in_progress']:
                if labels[0]=='Speech':
                    data = np.append(data,audio)
                    print(session['command_in_progress'])
                    return {"continue":"YES"}
                else:
                    librosa.output.write_wav(base_inp_dir + filename,data,sr)
                    data=[]
                    session['command_in_progress'] = False
                    print(session['command_in_progress'])
                    backend_pipeline(filename,session['user_data'])
                    return {"continue":"NO"}
            else:
                print(session['command_in_progress'])
                return {"continue":"YES"}


# @app.route('/check_audio_available', methods=['GET'])
# def check_audio_available():
#     if request.method=="GET":
#             return output_audio_ready

@app.route('/fetch_output_audio', methods=['POST','GET'])
def fetch_output_audio():
        if request.method=="POST":
            return send_file(base_out_dir + 'result.wav',mimetype="audio/wav",as_attachment=True,attachment_filename='result.wav')

        if request.method=="GET":
            if os.path.exists(base_out_dir + 'result.wav'):
                os.remove(base_out_dir + 'result.wav')
            return "output file removed"


if __name__ == "__main__":
    app.run(debug=True)
